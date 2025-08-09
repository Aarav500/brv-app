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


# -------------------------------
# Execute a query on the primary DB
# -------------------------------
def execute_query(query: str, params: Optional[Tuple[Any, ...]] = None, commit: bool = False) -> List[Tuple[Any]]:
    """Run a SQL query on the main Oracle DB."""
    try:
        with oracledb.connect(user=DB_USER, password=DB_PASSWORD, dsn=DB_DSN) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params or [])
                if commit:
                    conn.commit()
                    return []
                try:
                    return cursor.fetchall()
                except oracledb.InterfaceError:
                    return []
    except Exception as e:
        print(f"❌ execute_query failed: {e}")
        return []


# -------------------------------
# Execute a query across ALL DBs from env_config
# -------------------------------
def execute_across_all_dbs(query: str, params: Optional[Tuple[Any, ...]] = None, commit: bool = False) -> Dict[
    str, List[Tuple[Any]]]:
    """Run a SQL query across all DBs defined in env_config."""
    results = {}
    db_config_list = env_get_db_config()

    for db_info in db_config_list:
        db_name = db_info.get("name", "unknown")
        try:
            with oracledb.connect(
                    user=db_info["user"],
                    password=db_info["password"],
                    dsn=db_info["dsn"]
            ) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, params or [])
                    if commit:
                        conn.commit()
                        results[db_name] = []
                    else:
                        try:
                            results[db_name] = cursor.fetchall()
                        except oracledb.InterfaceError:
                            results[db_name] = []
        except Exception as e:
            print(f"❌ Query failed for {db_name}: {e}")
            results[db_name] = []
    return results