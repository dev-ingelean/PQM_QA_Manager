"""Rutas y ajustes locales del usuario."""
from pathlib import Path
import os

APP_NAME = "PQM Quality Manager"
ORG_NAME = "INGELEAN S.A.S."

def data_dir() -> Path:
    base = os.environ.get("APPDATA") if os.name == "nt" else os.environ.get("XDG_DATA_HOME")
    root = Path(base) if base else Path.home() / ("AppData/Roaming" if os.name == "nt" else ".local/share")
    path = root / "Ingelean" / "PQMQualityManager"
    path.mkdir(parents=True, exist_ok=True)
    return path

DATA_DIR = data_dir()
DB_PATH = DATA_DIR / "pqm_quality_manager.sqlite3"
PHOTO_DIR = DATA_DIR / "photos"
REPORT_DIR = DATA_DIR / "reports"
THUMB_DIR = DATA_DIR / "thumbnails"
LOG_DIR = DATA_DIR / "logs"
for _path in (PHOTO_DIR, REPORT_DIR, THUMB_DIR, LOG_DIR):
    _path.mkdir(parents=True, exist_ok=True)
