import struct
from typing import Any

try:
    import pyaudiowpatch as pyaudio
except ImportError:
    import pyaudio  # type: ignore


class DeviceError(RuntimeError):
    pass


def _get_wasapi_host_api(p: pyaudio.PyAudio) -> dict[str, Any] | None:
    try:
        return p.get_host_api_info_by_type(pyaudio.paWASAPI)
    except (KeyError, OSError):
        return None


def get_wasapi_device_info(target_name: str) -> dict[str, Any] | None:
    """Busca el dispositivo WASAPI correspondiente según su nombre."""
    p = pyaudio.PyAudio()
    try:
        wasapi = _get_wasapi_host_api(p)
        if not wasapi:
            return None
        wasapi_idx = wasapi["index"]

        name_clean = target_name.strip().lower()
        candidates: list[dict[str, Any]] = []
        for i in range(p.get_device_count()):
            d = p.get_device_info_by_index(i)
            if d.get("hostApi") == wasapi_idx and d.get("maxInputChannels", 0) > 0:
                if d.get("name", "").strip().lower() == name_clean:
                    return dict(d)
                candidates.append(dict(d))

        # Búsqueda parcial por si cambió levemente
        for d in candidates:
            if name_clean in d.get("name", "").lower() or d.get("name", "").lower() in name_clean:
                return d
        return None
    finally:
        p.terminate()


def list_inputs(ffmpeg: str = "", timeout: float = 10.0) -> list[str]:
    """Lista todos los dispositivos de audio disponibles vía WASAPI en Windows 10/11."""
    p = pyaudio.PyAudio()
    try:
        wasapi = _get_wasapi_host_api(p)
        if not wasapi:
            raise DeviceError("No se encontró el subsistema de audio WASAPI en este sistema Windows.")

        wasapi_idx = wasapi["index"]
        device_names: list[str] = []
        seen: dict[str, int] = {}

        # Ordenar: primero loopbacks (altavoces/sonido del sistema), luego entradas físicas (micrófonos)
        all_devs: list[dict[str, Any]] = []
        for i in range(p.get_device_count()):
            d = p.get_device_info_by_index(i)
            if d.get("hostApi") == wasapi_idx and d.get("maxInputChannels", 0) > 0:
                all_devs.append(d)

        # Ordenar poniendo Loopback primero ya que suele ser lo más buscado (emitir audio de la PC),
        # seguido de micrófonos e interfaces de audio
        all_devs.sort(key=lambda x: (not x.get("isLoopbackDevice", False), x.get("name", "")))

        for d in all_devs:
            raw_name = d.get("name", "").strip()
            if not raw_name:
                continue
            if raw_name in seen:
                seen[raw_name] += 1
                display_name = f"{raw_name} ({seen[raw_name]})"
            else:
                seen[raw_name] = 1
                display_name = raw_name

            device_names.append(display_name)

        if not device_names:
            raise DeviceError("No se detectaron dispositivos de audio WASAPI activos.")

        return device_names
    except Exception as exc:
        if isinstance(exc, DeviceError):
            raise
        raise DeviceError(f"Error al listar dispositivos WASAPI: {exc}") from exc
    finally:
        p.terminate()


def test_input(ffmpeg: str, device: str, timeout: float = 3.0) -> tuple[bool, str]:
    """Prueba la apertura y lectura del dispositivo WASAPI."""
    info = get_wasapi_device_info(device)
    if not info:
        return False, f"Dispositivo no encontrado en WASAPI: '{device}'"

    p = pyaudio.PyAudio()
    try:
        rate = int(info["defaultSampleRate"])
        channels = int(info["maxInputChannels"])
        is_loop = bool(info.get("isLoopbackDevice", False))

        stream = p.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=rate,
            input=True,
            input_device_index=info["index"],
            frames_per_buffer=1024,
        )

        data = b""
        if is_loop:
            # En loopback, si no hay sonido reproduciéndose en Windows, get_read_available es 0
            avail = stream.get_read_available()
            if avail > 0:
                data = stream.read(avail, exception_on_overflow=False)
        else:
            data = stream.read(1024, exception_on_overflow=False)

        stream.stop_stream()
        stream.close()

        max_amp = 0
        if data:
            samples = struct.unpack(f"<{len(data)//2}h", data)
            max_amp = max(abs(s) for s in samples)

        if max_amp > 100:
            return True, f"Dispositivo WASAPI OK (señal de audio activa detectada: {max_amp})"
        if is_loop:
            return True, "Dispositivo WASAPI OK (Loopback listo, en espera de audio en Windows)"
        return True, "Dispositivo WASAPI OK (listo)"
    except Exception as exc:
        return False, f"No se pudo abrir el dispositivo WASAPI: {exc}"
    finally:
        p.terminate()
