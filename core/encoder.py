import queue
import subprocess
import threading
import time
from typing import Any

from core.applog import ffmpeg_log_file, setup, tail
from core.ffmpeg_bin import NO_WINDOW

try:
    import pyaudiowpatch as pyaudio
except ImportError:
    import pyaudio  # type: ignore

CHANNELS = {"original": None, "mono": 1, "stereo": 2}


def _find_wasapi_device(p: pyaudio.PyAudio, target_name: str) -> dict[str, Any] | None:
    try:
        wasapi = p.get_host_api_info_by_type(pyaudio.paWASAPI)
    except (KeyError, OSError):
        return None
    wasapi_idx = wasapi["index"]
    target_clean = target_name.strip().lower()
    candidates: list[dict[str, Any]] = []

    for i in range(p.get_device_count()):
        d = p.get_device_info_by_index(i)
        if d.get("hostApi") == wasapi_idx and d.get("maxInputChannels", 0) > 0:
            if d.get("name", "").strip().lower() == target_clean:
                return dict(d)
            candidates.append(dict(d))

    for d in candidates:
        d_name = d.get("name", "").strip().lower()
        if target_clean in d_name or d_name in target_clean:
            return d

    return candidates[0] if candidates else None


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
        on_pcm=None,
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
        self.on_pcm = on_pcm
        self.on_error = on_error
        self.on_finished = on_finished

        self.log = setup()
        self.process: subprocess.Popen | None = None
        self.p_audio: pyaudio.PyAudio | None = None
        self.pa_stream = None

        self.bytes_total = 0
        self.kbps = 0.0
        self.running = False
        self._stopping = False
        self._error_shown = False
        self._lock = threading.Lock()
        self._rate_lock = threading.Lock()
        self._rate_window: list[tuple[float, int]] = []

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
        try:
            self.p_audio = pyaudio.PyAudio()
        except Exception as exc:
            self._fail(f"No se pudo inicializar PortAudio/WASAPI: {exc}")
            self._notify_finished(-1)
            return

        dev_info = _find_wasapi_device(self.p_audio, self.device)
        if not dev_info:
            self._cleanup_audio()
            self._fail(f"No se encontró el dispositivo WASAPI '{self.device}'.")
            self._notify_finished(-1)
            return

        in_rate = int(dev_info["defaultSampleRate"])
        in_channels = int(dev_info["maxInputChannels"])
        is_loopback = bool(dev_info.get("isLoopbackDevice", False))

        cmd = [
            self.ffmpeg,
            "-hide_banner",
            "-loglevel", "warning",
        ]
        if self.nobuffer:
            cmd += ["-fflags", "nobuffer"]

        cmd += [
            "-f", "s16le",
            "-ar", str(in_rate),
            "-ac", str(in_channels),
            "-i", "pipe:0",
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
            "-flush_packets", "1",
            "-muxdelay", "0",
            "-f", "mp3",
            "pipe:1",
        ]

        self.log.info(
            "WASAPI activo: '%s' (in=%dHz, %d ch, loopback=%s) -> MP3 (%s, %dHz)",
            dev_info.get("name"),
            in_rate,
            in_channels,
            is_loopback,
            self.bitrate,
            self.samplerate,
        )

        log_file = ffmpeg_log_file()
        try:
            err_handle = open(log_file, "wb", buffering=0)
        except OSError as exc:
            self._cleanup_audio()
            self._fail(f"No se pudo abrir el log de ffmpeg: {exc}")
            self._notify_finished(-1)
            return

        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=err_handle,
                bufsize=0,
                creationflags=NO_WINDOW,
            )
        except OSError as exc:
            err_handle.close()
            self._cleanup_audio()
            self._fail(f"No se pudo iniciar ffmpeg: {exc}")
            self._notify_finished(-1)
            return

        chunk_frames = 1024
        bytes_per_chunk = chunk_frames * in_channels * 2
        max_q = max(20, (self.rtbufsize_mb * 1024 * 1024) // bytes_per_chunk)
        audio_q: queue.Queue[bytes] = queue.Queue(maxsize=max_q)
        pcm_q: queue.Queue[bytes] = queue.Queue(maxsize=12)
        silence_chunk = b"\x00" * bytes_per_chunk
        chunk_duration = float(chunk_frames) / float(in_rate)

        def audio_callback(in_data, frame_count, time_info, status):
            if self._stopping:
                return (None, pyaudio.paComplete)
            try:
                audio_q.put_nowait(in_data)
            except queue.Full:
                pass
            if self.on_pcm:
                try:
                    pcm_q.put_nowait(in_data)
                except queue.Full:
                    try:
                        pcm_q.get_nowait()
                        pcm_q.put_nowait(in_data)
                    except (queue.Empty, queue.Full):
                        pass
            return (in_data, pyaudio.paContinue)

        try:
            self.pa_stream = self.p_audio.open(
                format=pyaudio.paInt16,
                channels=in_channels,
                rate=in_rate,
                input=True,
                input_device_index=dev_info["index"],
                frames_per_buffer=chunk_frames,
                stream_callback=audio_callback,
            )
            self.pa_stream.start_stream()
        except Exception as exc:
            err_handle.close()
            self._cleanup_audio()
            self._fail(f"No se pudo abrir el dispositivo WASAPI '{self.device}': {exc}")
            if self.process and self.process.poll() is None:
                try:
                    self.process.terminate()
                except OSError:
                    pass
            self._notify_finished(-1)
            return

        def _pcm_worker():
            while not self._stopping:
                try:
                    data = pcm_q.get(timeout=0.1)
                except queue.Empty:
                    continue
                if self.on_pcm:
                    try:
                        self.on_pcm(data, in_rate, in_channels)
                    except Exception:
                        pass

        pcm_thread = threading.Thread(target=_pcm_worker, name="pcm_feeder", daemon=True)
        pcm_thread.start()

        def _feed_worker():
            while not self._stopping and self.process and self.process.poll() is None:
                try:
                    data = audio_q.get(timeout=chunk_duration * 1.5)
                except queue.Empty:
                    data = silence_chunk
                    time.sleep(chunk_duration * 0.8)

                try:
                    if self.process and self.process.stdin and not self.process.stdin.closed:
                        self.process.stdin.write(data)
                except (BrokenPipeError, OSError):
                    break

            try:
                if self.process and self.process.stdin and not self.process.stdin.closed:
                    self.process.stdin.close()
            except OSError:
                pass

        feeder_thread = threading.Thread(target=_feed_worker, name="wasapi_feeder", daemon=True)
        feeder_thread.start()

        self.running = True
        started = time.monotonic()
        try:
            while not self._stopping:
                chunk = self.process.stdout.read(4096)
                if not chunk:
                    break
                self.bytes_total += len(chunk)
                self._track_rate(len(chunk))
                if self.on_audio:
                    self.on_audio(chunk)
        except (OSError, ValueError) as exc:
            if not self._stopping:
                self._fail(f"Se perdió la lectura del audio codificado: {exc}")
        finally:
            self.running = False
            self._cleanup_audio()
            pcm_thread.join(timeout=0.3)
            feeder_thread.join(timeout=0.6)
            code = self.process.wait()
            elapsed = time.monotonic() - started
            err_handle.close()
            if not self._stopping and code not in (0, 255):
                detail = tail(log_file, 4)
                self._fail(f"ffmpeg terminó con código {code}. {detail}".strip())
            elif not self._stopping:
                self.log.info("ffmpeg terminó tras %.1fs (código %s)", elapsed, code)
            self._notify_finished(code)

    def _cleanup_audio(self) -> None:
        with self._lock:
            try:
                if self.pa_stream:
                    if self.pa_stream.is_active():
                        self.pa_stream.stop_stream()
                    self.pa_stream.close()
                    self.pa_stream = None
            except Exception:
                pass
            try:
                if self.p_audio:
                    self.p_audio.terminate()
                    self.p_audio = None
            except Exception:
                pass

    def _notify_finished(self, code: int) -> None:
        if self.on_finished:
            self.on_finished(code)

    def stop(self) -> None:
        self._stopping = True
        proc = self.process
        if proc and proc.poll() is None:
            try:
                if proc.stdin and not proc.stdin.closed:
                    proc.stdin.close()
            except OSError:
                pass
            try:
                proc.terminate()
            except OSError:
                pass
        self.join(timeout=2.0)
        self._cleanup_audio()
