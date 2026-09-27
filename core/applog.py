import logging
import sys
from pathlib import Path

from core.ffmpeg_bin import data_dir, is_frozen

_log_path = data_dir() / "stream.log"
_configured = False


def log_file() -> Path:
    return _log_path


def ffmpeg_log_file() -> Path:
    return _log_path.parent / "ffmpeg.log"


def setup(name: str = "stream") -> logging.Logger:
    global _configured
    logger = logging.getLogger(name)
    if _configured:
        return logger
    _configured = True
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    try:
        if _log_path.exists() and _log_path.stat().st_size > 512_000:
            _log_path.replace(_log_path.with_suffix(".old.log"))
    except OSError:
        pass
    try:
        handler = logging.FileHandler(_log_path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s"))
        logger.addHandler(handler)
    except OSError:
        pass
    if not is_frozen() or sys.stderr is not None:
        try:
            stream = logging.StreamHandler(sys.stderr)
            stream.setFormatter(logging.Formatter("%(levelname)-7s %(message)s"))
            logger.addHandler(stream)
        except (OSError, ValueError):
            pass
    return logger


def tail(path: Path, lines: int = 12) -> str:
    try:
        content = path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""
    if not content:
        return ""
    return " | ".join(content.splitlines()[-lines:])
