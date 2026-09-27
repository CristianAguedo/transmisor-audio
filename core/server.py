import json
import queue
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

CHUNK_TERMINATOR = b"0\r\n\r\n"
SYNC_LIMIT = 16384
CLIENT_QUEUE_LIMIT = 96


def find_mp3_sync(buffer: bytearray) -> int:
    for index in range(len(buffer) - 1):
        if buffer[index] == 0xFF and buffer[index + 1] & 0xE0 == 0xE0:
            return index
    return -1


class StreamClient:
    def __init__(self, handler: "StreamHandler") -> None:
        self.handler = handler
        self.queue: queue.Queue = queue.Queue(maxsize=CLIENT_QUEUE_LIMIT)
        self.connected_at = time.time()
        self.bytes_sent = 0
        self.dropped = False
        self.primed = False
        self._pre = bytearray()
        self._closed = threading.Event()
        self._thread = threading.Thread(target=self._pump, daemon=True, name="client-writer")

    def start(self) -> None:
        self._thread.start()

    @property
    def closed(self) -> bool:
        return self._closed.is_set() or self.dropped

    def push(self, chunk: bytes) -> bool:
        if self.closed:
            return False
        try:
            self.queue.put_nowait(chunk)
            return True
        except queue.Full:
            self.dropped = True
            self._closed.set()
            return False

    def _ready_chunk(self, chunk: bytes) -> bytes:
        if self.primed:
            return chunk
        self._pre.extend(chunk)
        if len(self._pre) > SYNC_LIMIT:
            self.primed = True
            data = bytes(self._pre)
            self._pre.clear()
            return data
        index = find_mp3_sync(self._pre)
        if index < 0:
            return b""
        self.primed = True
        data = bytes(self._pre[index:])
        self._pre.clear()
        return data

    def _pump(self) -> None:
        while not self._closed.is_set():
            try:
                chunk = self.queue.get(timeout=0.3)
            except queue.Empty:
                continue
            if chunk is None:
                return
            data = self._ready_chunk(chunk)
            if not data:
                continue
            try:
                self.handler.write_chunk(data)
                self.bytes_sent += len(data)
            except (OSError, ValueError):
                self._closed.set()
                return

    def close(self) -> None:
        self._closed.set()
        try:
            self.queue.put_nowait(None)
        except queue.Full:
            pass


class StreamHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "TransmisorAudio"
    sys_version = ""

    def log_message(self, fmt, *args) -> None:
        return

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path in ("/", "/index.html"):
            self._serve_page()
        elif path == "/stream.mp3":
            self._serve_stream()
        elif path == "/api/status":
            self._serve_status()
        elif path == "/favicon.ico":
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
        else:
            self._send(404, b"No encontrado", "text/plain; charset=utf-8")

    def _send(self, code: int, payload: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (OSError, ValueError):
            pass

    def _serve_page(self) -> None:
        page = self.server.app.web_root / "index.html"
        try:
            payload = page.read_bytes()
        except OSError:
            self._send(500, b"No se encontro assets/index.html", "text/plain; charset=utf-8")
            return
        self._send(200, payload, "text/html; charset=utf-8")

    def _serve_status(self) -> None:
        app = self.server.app
        payload = json.dumps(app.status(), ensure_ascii=False).encode("utf-8")
        self._send(200, payload, "application/json; charset=utf-8")

    def _serve_stream(self) -> None:
        app = self.server.app
        self.send_response(200)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        self.close_connection = True

        try:
            self.connection.settimeout(20)
        except OSError:
            pass

        client = StreamClient(self)
        app.add_client(client)
        client.start()
        try:
            while not app.halt.is_set() and not client.closed:
                app.halt.wait(0.25)
        finally:
            app.remove_client(client)
            client.close()
            self._finish_response()

    def write_chunk(self, payload: bytes) -> None:
        self.wfile.write(b"%X\r\n" % len(payload))
        self.wfile.write(payload)
        self.wfile.write(b"\r\n")
        self.wfile.flush()

    def _finish_response(self) -> None:
        try:
            self.wfile.write(CHUNK_TERMINATOR)
            self.wfile.flush()
        except (OSError, ValueError):
            pass


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 32


class StreamServer:
    def __init__(self, host: str, port: int, web_root: Path, status_provider=None) -> None:
        self.host = host
        self.port = port
        self.web_root = Path(web_root)
        self.status_provider = status_provider
        self.live = threading.Event()
        self.halt = threading.Event()
        self._clients: list[StreamClient] = []
        self._lock = threading.Lock()
        self._httpd = None
        self.started_at = 0.0

    def start(self) -> None:
        self._httpd = _Server((self.host, self.port), StreamHandler)
        self._httpd.app = self
        self.started_at = time.time()
        self.halt.clear()
        self.live.set()
        threading.Thread(target=self._httpd.serve_forever, kwargs={"poll_interval": 0.2},
                         daemon=True, name="http-server").start()

    def stop(self) -> None:
        self.live.clear()
        self.halt.set()
        httpd = self._httpd
        if httpd is not None:
            closer = threading.Thread(target=httpd.shutdown, daemon=True)
            closer.start()
            closer.join(timeout=3)
            try:
                httpd.server_close()
            except OSError:
                pass
            self._httpd = None
        with self._lock:
            clients = list(self._clients)
            self._clients.clear()
        for client in clients:
            client.close()

    def add_client(self, client: StreamClient) -> None:
        with self._lock:
            self._clients.append(client)

    def remove_client(self, client: StreamClient) -> None:
        with self._lock:
            if client in self._clients:
                self._clients.remove(client)

    def broadcast(self, chunk: bytes) -> None:
        with self._lock:
            targets = list(self._clients)
        for client in targets:
            client.push(chunk)

    def client_count(self) -> int:
        with self._lock:
            return len(self._clients)

    def client_details(self) -> list[dict]:
        with self._lock:
            return [
                {
                    "address": client.handler.client_address[0],
                    "seconds": round(time.time() - client.connected_at, 1),
                    "kbps": round(client.bytes_sent * 8 / max(time.time() - client.connected_at, 0.1) / 1000, 1),
                }
                for client in self._clients
            ]

    def status(self) -> dict:
        base = {"transmitting": self.live.is_set(), "clients": self.client_count(),
                "listeners": self.client_details(),
                "uptime": round(time.time() - self.started_at, 1) if self.started_at else 0}
        if self.status_provider:
            base.update(self.status_provider())
        return base
