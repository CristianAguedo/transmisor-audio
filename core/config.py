import json
import logging
from pathlib import Path
from typing import Any

from core.ffmpeg_bin import app_dir, data_dir

log = logging.getLogger("stream_audio")

CONFIG_FILE_NAME = "config.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "device": "",
    "port": 9000,
    "bitrate": "128k",
    "samplerate": 44100,
    "channels": "original",
    "buffer": 4,
    "nobuffer": True,
    "autostart": True,
    "window_width": 980,
    "window_height": 640,
    "window_geometry": "",
    "window_state": "normal",
}


def config_file_path() -> Path:
    # Si existe config.json junto al ejecutable (modo portable), se usa ese;
    # sino se guarda en %LOCALAPPDATA%\TransmisorAudio\config.json
    local_path = app_dir() / CONFIG_FILE_NAME
    if local_path.is_file():
        return local_path
    return data_dir() / CONFIG_FILE_NAME


def load_config() -> dict[str, Any]:
    path = config_file_path()
    config = dict(DEFAULT_CONFIG)
    if not path.is_file():
        return config

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                config.update(data)
    except Exception as exc:
        log.warning("No se pudo leer la configuración desde %s: %s", path, exc)

    return config


def save_config(config_data: dict[str, Any]) -> None:
    path = config_file_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Limitar a campos válidos
        clean = {k: config_data.get(k, DEFAULT_CONFIG.get(k)) for k in DEFAULT_CONFIG}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(clean, f, indent=2, ensure_ascii=False)
        log.info("Configuración guardada en %s", path)
    except Exception as exc:
        log.error("Error al guardar configuración en %s: %s", path, exc)
