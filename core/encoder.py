import subprocess
import threading
import time

from core.applog import ffmpeg_log_file, setup, tail
from core.ffmpeg_bin import NO_WINDOW

CHANNELS = {"original": None, "mono": 1, "stereo": 2}


class AudioEncoder(threading.Thread):
    def __init__(
        self,
        ffmpeg: str,
        device: str,
        bitrate: str = "128k",
        samplerate: int = 44100,
        channels: str = "original",
        rtbufsize_mb: int = 4,
        nobuffer: bool = True,
        on_audio=None,
        on_error=None,
        on_finished=None,
    ) -> None:
        super().__init__(daemon=True, name="encoder")
        self.ffmpeg = ffmpeg
        self.device = device
        self.bitrate = bitrate
        self.samplerate = int(samplerate)
        self.channels = channels
        self.rtbufsize_mb = int(rtbufsize_mb)
        self.nobuffer = bool(nobuffer)
        self.on_audio = on_audio
        self.on_error = on_error
        self.on_finished = on_finished
        self.log = setup()
        self.process: subprocess.Popen | None = None
        self.bytes_total = 0
        self.kbps = 0.0
        self.running = False
        self._stopping = False
        self._error_shown = False
        self._lock = threading.Lock()
        self._rate_lock = threading.Lock()
        self._rate_window: list[tuple[float, int]] = []

    def build_command(self) -> list[str]:
        cmd = [
            self.ffmpeg,
            "-hide_banner",
            "-loglevel", "warning",
            "-thread_queue_size", "512",
        ]
        if self.nobuffer:
            cmd += ["-fflags", "nobuffer"]
        cmd += [
            "-f", "dshow",
            "-rtbufsize", str(self.rtbufsize_mb * 1024 * 1024),
            "-i", f"audio={self.device}",
        ]
        force_channels = CHANNELS.get(self.channels)
        if force_channels:
            cmd += ["-ac", str(force_channels)]
        cmd += [
            "-vn",
            "-ar", str(self.samplerate),
            "-c:a", "libmp3lame",
            "-b:a", self.bitrate,
            "-write_xing", "0",
            "-muxdelay", "0",
            "-f", "mp3",
            "pipe:1",
        ]
        return cmd

    def _track_rate(self, size: int) -> None:
        now = time.monotonic()
        with self._rate_lock:
            self._rate_window.append((now, size))
            cutoff = now - 1.0
            while self._rate_window and self._rate_window[0][0] < cutoff:
                self._rate_window.pop(0)
            self.kbps = sum(item[1] for item in self._rate_window) * 8 / 1000.0

    def _fail(self, message: str) -> None:
        with self._lock:
            if self._error_shown:
                return
            self._error_shown = True
        self.log.error(message)
        if self.on_error:
            self.on_error(message)

    def run(self) -> None:
        cmd = self.build_command()
        self.log.info("Comando: %s", " ".join(cmd))
        log_file = ffmpeg_log_file()
        try:
            err_handle = open(log_file, "wb", buffering=0)
        except OSError as exc:
            self._fail(f"No se pudo abrir el log de ffmpeg: {exc}")
            return

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=err_handle,
                bufsize=0,
                creationflags=NO_WINDOW,
            )
        except OSError as exc:
            err_handle.close()
            self._fail(f"No se pudo iniciar ffmpeg: {exc}")
            self._notify_finished(-1)
            return

        self.running = True
        started = time.monotonic()
        try:
            while True:
                chunk = self.process.stdout.read(16384)
                if not chunk:
                    break
                self.bytes_total += len(chunk)
                self._track_rate(len(chunk))
                if self.on_audio:
                    self.on_audio(chunk)
        except (OSError, ValueError) as exc:
            if not self._stopping:
                self._fail(f"Se perdió la lectura del audio: {exc}")
        finally:
            self.running = False
            code = self.process.wait()
            elapsed = time.monotonic() - started
            err_handle.close()
            if not self._stopping and code not in (0, 255):
                detail = tail(log_file, 4)
                self._fail(f"ffmpeg terminó con código {code}. {detail}".strip())
            elif not self._stopping:
                self.log.info("ffmpeg terminó solo tras %.1fs (código %s)", elapsed, code)
            self._notify_finished(code)

    def _notify_finished(self, code: int) -> None:
        if self.on_finished:
            self.on_finished(code)

    def stop(self) -> None:
        self._stopping = True
        proc = self.process
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass
            watchdog = threading.Thread(target=self._kill_later, args=(proc,), daemon=True)
            watchdog.start()

    @staticmethod
    def _kill_later(proc: subprocess.Popen) -> None:
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except OSError:
                pass
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass
