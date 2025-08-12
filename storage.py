# storage.py
import os
from dotenv import load_dotenv
from datetime import datetime
import logging

load_dotenv()
LOCAL_PATH = os.getenv("LOCAL_STORAGE_PATH", "./storage")
os.makedirs(LOCAL_PATH, exist_ok=True)

logger = logging.getLogger(__name__)

def _sanitize_name(name: str) -> str:
    safe = "".join(c for c in name if c.isalnum() or c in "-_.").rstrip()
    return safe or "file"

def save_resume(file_bytes: bytes, filename: str) -> str:
    """
    Save a resume and return the absolute path to file.
    """
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    base = _sanitize_name(os.path.splitext(filename)[0])
    ext = os.path.splitext(filename)[1] or ".bin"
    new_name = f"{base}_{ts}{ext}"
    path = os.path.join(LOCAL_PATH, new_name)
    try:
        with open(path, "wb") as f:
            f.write(file_bytes)
        logger.info("Saved resume to %s", path)
        return os.path.abspath(path)
    except Exception as e:
        logger.exception("Failed to save resume")
        raise
