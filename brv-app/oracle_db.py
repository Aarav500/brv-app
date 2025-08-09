import os
import json
import uuid
import bcrypt
from datetime import datetime
import oracledb
from typing import Dict, List, Optional, Any, Tuple, Union
from dotenv import load_dotenv

# Load environment variables from .env (still works for local dev)
load_dotenv()

# Detect if running inside Docker (instant client + wallet baked in)
if os.path.exists("/opt/oracle/instantclient_23_9") and os.path.exists("/opt/oracle/wallet"):
    LIB_DIR = "/opt/oracle/instantclient_23_9"
    WALLET_PATH = "/opt/oracle/wallet"
else:
    # Fallback to .env for local dev
    WALLET_PATH = os.getenv("ORACLE_WALLET_LOCATION")
    LIB_DIR = os.getenv("ORACLE_CLIENT_LIB_DIR")

# Oracle DB config
DB_USER = os.getenv("ORACLE_USER")
DB_PASSWORD = os.getenv("ORACLE_PASSWORD")
DB_DSN = os.getenv("ORACLE_DSN")

# Required by oracledb to find tnsnames.ora
if WALLET_PATH:
    os.environ["TNS_ADMIN"] = WALLET_PATH

# Initialize Oracle Client early
print(f"🔍 Using Oracle Wallet Path: {WALLET_PATH}")
print(f"🔍 Using Oracle Client Lib Dir: {LIB_DIR}")
try:
    oracledb.init_oracle_client(lib_dir=LIB_DIR, config_dir=WALLET_PATH)
except Exception as e:
    if "already called" in str(e).lower():
        print("ℹ️ Oracle client already initialized.")
    else:
        print(f"⚠️ Could not initialize Oracle client: {e}")

# Import configuration from env_config.py
from env_config import (
    DB_CONFIG_FILE,
    get_db_config as env_get_db_config,
    update_db_config as env_update_db_config
)
