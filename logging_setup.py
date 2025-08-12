# logging_setup.py
import logging
import os

LOG_PATH = os.getenv("LOG_PATH", "./logs")
os.makedirs(LOG_PATH, exist_ok=True)
LOG_FILE = os.path.join(LOG_PATH, "app.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
