import os
import shutil
import sys
from pathlib import Path

NO_WINDOW = 0x08000000 if os.name == "nt" else 0
APP_DIR_NAME = "TransmisorAudio"
ASSETS_DIR_NAME = "assets"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def assets_dir() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", app_dir())) / ASSETS_DIR_NAME
    return app_dir() / ASSETS_DIR_NAME


def data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(app_dir())
    path = Path(base) / APP_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def candidate_ffmpeg_paths():
    base = app_dir()
    yield base / "ffmpeg.exe"
    yield base / "ffmpeg" / "ffmpeg.exe"
    yield base / "ffmpeg" / "bin" / "ffmpeg.exe"
    yield base / "bin" / "ffmpeg.exe"
    yield data_dir() / "ffmpeg.exe"


def find_ffmpeg() -> str | None:
    for path in candidate_ffmpeg_paths():
        if path.is_file():
            return str(path)
    for var in ("FFMPEG", "FFMPEG_PATH"):
        value = os.environ.get(var)
        if value and Path(value).is_file():
            return value
    return shutil.which("ffmpeg")


def decode_output(raw: bytes) -> str:
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")
