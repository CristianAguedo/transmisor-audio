import re
import subprocess

from core.ffmpeg_bin import NO_WINDOW, decode_output

DEVICE_PATTERN = re.compile(r'"(.+?)"\s+\((audio|video)\)')
INTERESTING = ("cannot find", "no such", "cannot open", "error", "cannot set", "not found", "impossible")


class DeviceError(RuntimeError):
    pass


def list_inputs(ffmpeg: str, timeout: float = 25.0) -> list[str]:
    cmd = [ffmpeg, "-hide_banner", "-f", "dshow", "-list_devices", "true", "-i", "dummy"]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            creationflags=NO_WINDOW,
        )
    except subprocess.TimeoutExpired as exc:
        raise DeviceError("ffmpeg tardó demasiado en listar los dispositivos.") from exc
    except OSError as exc:
        raise DeviceError(f"No se pudo ejecutar ffmpeg: {exc}") from exc

    text = decode_output(proc.stderr or b"") + "\n" + decode_output(proc.stdout or b"")
    if "dshow" not in text and not DEVICE_PATTERN.search(text):
        raise DeviceError("ffmpeg no respondió como se esperaba. Revisá que sea un build de Windows.")

    names: list[str] = []
    for raw_name, kind in DEVICE_PATTERN.findall(text):
        if kind != "audio":
            continue
        name = raw_name.strip()
        if not name or name.lower().startswith("@device_"):
            continue
        if name not in names:
            names.append(name)
    return names


def _relevant_line(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        low = line.lower()
        if any(token in low for token in INTERESTING):
            return line
    return lines[-1] if lines else "Error desconocido de ffmpeg"


def test_input(ffmpeg: str, device: str, timeout: float = 10.0) -> tuple[bool, str]:
    cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-thread_queue_size", "512",
        "-f", "dshow", "-i", f"audio={device}", "-t", "0.4", "-f", "null", "-",
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            creationflags=NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        return True, "Dispositivo abierto correctamente (la prueba se cortó por tiempo)."
    except OSError as exc:
        return False, f"No se pudo ejecutar ffmpeg: {exc}"

    if proc.returncode == 0:
        return True, "Dispositivo OK"
    return False, _relevant_line(decode_output(proc.stderr or b""))
