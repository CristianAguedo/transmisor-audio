import json
import queue
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

CLIENT_QUEUE_LIMIT = 64
MAX_BURST_BYTES = 32 * 1024  # 32 KB pre-roll buffer para MP3


def is_mp3_header(b0: int, b1: int, b2: int) -> bool:
    """Verifica si los 3 bytes corresponden al inicio de una cabecera válida MPEG Audio Layer III (MP3)."""
    if b0 != 0xFF:
        return False
    if (b1 & 0xE0) != 0xE0:
        return False
    if (b1 & 0x18) == 0x08:  # Versión MPEG reservada
        return False
    if (b1 & 0x06) != 0x02:  # Debe ser Layer III (MP3)
        return False
    if (b2 & 0xF0) in (0x00, 0xF0):  # Bitrate inválido / libre
        return False
    if (b2 & 0x0C) == 0x0C:  # Frecuencia de muestreo reservada
        return False
    return True


def find_first_mp3_frame(buf: bytes | bytearray) -> int:
    """Busca el offset del primer encabezado válido de cuadro MP3."""
    for i in range(len(buf) - 3):
        if is_mp3_header(buf[i], buf[i + 1], buf[i + 2]):
            return i
    return -1


class StreamClient:
    def __init__(self, handler: "StreamHandler", is_pcm: bool = False) -> None:
        self.handler = handler
        self.is_pcm = is_pcm
        # Para PCM en tiempo real, cola de 10 bloques (~210ms) para tolerar fluctuaciones de Wi-Fi sin cortes
        q_limit = 10 if is_pcm else CLIENT_QUEUE_LIMIT
        self.queue: queue.Queue = queue.Queue(maxsize=q_limit)
        self.connected_at = time.time()
        self.bytes_sent = 0
        self.primed = is_pcm  # PCM no requiere sincronización de cabecera MP3
        self._closed = threading.Event()

    @property
    def closed(self) -> bool:
        return self._closed.is_set()

    def push(self, chunk: bytes) -> bool:
        if self._closed.is_set():
            return False

        if not self.primed:
            offset = find_first_mp3_frame(chunk)
            if offset >= 0:
                chunk = chunk[offset:]
                self.primed = True
            else:
                return False

        if not chunk:
            return True

        # En redes lentas o pausas breves, descartar el bloque más viejo para mantener el audio en vivo
        if self.queue.full():
            try:
                self.queue.get_nowait()
            except queue.Empty:
                pass

        try:
            self.queue.put_nowait(chunk)
            return True
        except queue.Full:
            return False

    def close(self) -> None:
        self._closed.set()
        try:
            self.queue.put_nowait(None)
        except Exception:
            pass


class StreamHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    server_version = "TransmisorAudio"
    sys_version = ""

    def log_message(self, fmt, *args) -> None:
        return

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Expose-Headers", "X-Audio-Rate, X-Audio-Channels")
        self.send_header("Content-Length", "0")
        self.send_header("Connection", "close")
        self.end_headers()

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path in ("/", "/index.html"):
            self._serve_page()
        elif path == "/stream.mp3":
            self._serve_stream()
        elif path == "/stream.pcm":
            self._serve_pcm()
        elif path == "/api/status":
            self._serve_status()
        elif path == "/favicon.ico":
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.send_header("Connection", "close")
            self.end_headers()
        else:
            self._send(404, b"No encontrado", "text/plain; charset=utf-8")

    def _send(self, code: int, payload: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            self.wfile.write(payload)
            self.wfile.flush()
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
        """Flujo HTTP MP3 estándar y universal (ideal para Smart TVs y modo Estabilidad)."""
        app = self.server.app
        query = urlsplit(self.path).query
        is_low_latency = ("lowlatency=1" in query or "burst=0" in query)

        self.send_response(200)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("Connection", "close")
        self.send_header("Accept-Ranges", "none")
        self.send_header("icy-name", "Transmisor Audio LAN")
        self.send_header("icy-pub", "1")
        self.end_headers()
        self.close_connection = True

        try:
            self.connection.settimeout(10.0)
        except OSError:
            pass

        client = StreamClient(self, is_pcm=False)
        app.add_client(client, low_latency=is_low_latency)
        try:
            while not app.halt.is_set() and not client.closed:
                try:
                    chunk = client.queue.get(timeout=0.25)
                except queue.Empty:
                    continue
                if chunk is None:
                    break
                try:
                    self.wfile.write(chunk)
                    self.wfile.flush()
                    client.bytes_sent += len(chunk)
                except (OSError, ValueError):
                    break
        finally:
            app.remove_client(client)
            client.close()

    def _serve_pcm(self) -> None:
        """Flujo PCM directo en tiempo real (~40-60 ms de latencia absoluta para celulares)."""
        app = self.server.app
        rate = app.pcm_rate or 48000
        channels = app.pcm_channels or 2

        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Expose-Headers", "X-Audio-Rate, X-Audio-Channels")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("Connection", "close")
        self.send_header("X-Audio-Rate", str(rate))
        self.send_header("X-Audio-Channels", str(channels))
        self.end_headers()
        self.close_connection = True

        try:
            self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 16384)
            self.connection.settimeout(10.0)
        except OSError:
            pass

        client = StreamClient(self, is_pcm=True)
        app.add_pcm_client(client)
        try:
            while not app.halt.is_set() and not client.closed:
                try:
                    chunk = client.queue.get(timeout=0.25)
                except queue.Empty:
                    continue
                if chunk is None:
                    break
                try:
                    self.wfile.write(chunk)
                    self.wfile.flush()
                    client.bytes_sent += len(chunk)
                except (OSError, ValueError):
                    break
        finally:
            app.remove_pcm_client(client)
            client.close()


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 64


class StreamServer:
    def __init__(self, host: str, port: int, web_root: Path, status_provider=None) -> None:
        self.host = host
        self.port = port
        self.web_root = Path(web_root)
        self.status_provider = status_provider
        self.live = threading.Event()
        self.halt = threading.Event()
        self._clients: list[StreamClient] = []
        self._pcm_clients: list[StreamClient] = []
        self._lock = threading.Lock()
        self._burst_buffer = bytearray()
        self._max_burst = MAX_BURST_BYTES
        self._httpd = None
        self.started_at = 0.0
        self.pcm_rate = 48000
        self.pcm_channels = 2

    def start(self) -> None:
        with self._lock:
            self._burst_buffer.clear()
        self._httpd = _Server((self.host, self.port), StreamHandler)
        self._httpd.app = self
        self.started_at = time.time()
        self.halt.clear()
        self.live.set()
        threading.Thread(
            target=self._httpd.serve_forever,
            kwargs={"poll_interval": 0.2},
            daemon=True,
            name="http-server",
        ).start()

    def stop(self) -> None:
        self.live.clear()
        self.halt.set()
        with self._lock:
            self._burst_buffer.clear()
            clients = list(self._clients) + list(self._pcm_clients)
            self._clients.clear()
            self._pcm_clients.clear()
        for client in clients:
            client.close()
        httpd = self._httpd
        if httpd is not None:
            closer = threading.Thread(target=httpd.shutdown, daemon=True)
            closer.start()
            closer.join(timeout=2.0)
            try:
                httpd.server_close()
            except OSError:
                pass
            self._httpd = None

    def add_client(self, client: StreamClient, low_latency: bool = False) -> None:
        target_burst = (4 * 1024) if low_latency else (16 * 1024)
        with self._lock:
            self._clients.append(client)
            if len(self._burst_buffer) > target_burst:
                burst = bytes(self._burst_buffer[-target_burst:])
            else:
                burst = bytes(self._burst_buffer)
        if burst:
            offset = find_first_mp3_frame(burst)
            if offset >= 0:
                client.primed = True
                client.push(burst[offset:])
            else:
                client.push(burst)

    def remove_client(self, client: StreamClient) -> None:
        with self._lock:
            if client in self._clients:
                self._clients.remove(client)

    def add_pcm_client(self, client: StreamClient) -> None:
        with self._lock:
            self._pcm_clients.append(client)

    def remove_pcm_client(self, client: StreamClient) -> None:
        with self._lock:
            if client in self._pcm_clients:
                self._pcm_clients.remove(client)

    def broadcast_pcm(self, chunk: bytes, rate: int, channels: int) -> None:
        self.pcm_rate = rate
        self.pcm_channels = channels
        with self._lock:
            targets = list(self._pcm_clients)
        for client in targets:
            client.push(chunk)

    def broadcast(self, chunk: bytes) -> None:
        with self._lock:
            self._burst_buffer.extend(chunk)
            if len(self._burst_buffer) > self._max_burst:
                trimmed = self._burst_buffer[-self._max_burst:]
                offset = find_first_mp3_frame(trimmed)
                if offset >= 0:
                    self._burst_buffer = bytearray(trimmed[offset:])
                else:
                    self._burst_buffer = bytearray(trimmed)
            targets = list(self._clients)
        for client in targets:
            client.push(chunk)

    def client_count(self) -> int:
        with self._lock:
            return len(self._clients) + len(self._pcm_clients)

    def client_details(self) -> list[dict]:
        with self._lock:
            all_clients = list(self._clients) + list(self._pcm_clients)
            return [
                {
                    "address": client.handler.client_address[0],
                    "seconds": round(time.time() - client.connected_at, 1),
                    "kbps": round(client.bytes_sent * 8 / max(time.time() - client.connected_at, 0.1) / 1000, 1),
                    "type": "PCM (Baja latencia)" if client.is_pcm else "MP3 (Estabilidad)",
                }
                for client in all_clients
            ]

    def status(self) -> dict:
        base = {
            "transmitting": self.live.is_set(),
            "clients": self.client_count(),
            "listeners": self.client_details(),
            "uptime": round(time.time() - self.started_at, 1) if self.started_at else 0,
        }
        if self.status_provider:
            base.update(self.status_provider())
        return base
