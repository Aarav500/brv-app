#!/usr/bin/env python3
"""
Storage Check Script for BRV Applicant Management System (Postgres Railway)
Checks DB size and alerts CEO via a local file.
"""

import os
import psycopg2
from datetime import datetime

# === CONFIG ===
DB_CONFIG = {
    "dbname": os.getenv("PGDATABASE", "railway"),
    "user": os.getenv("PGUSER", "postgres"),
    "password": os.getenv("PGPASSWORD", ""),
    "host": os.getenv("PGHOST", "containers-us-west-50.railway.app"),
    "port": os.getenv("PGPORT", "5432")
}
SIZE_LIMIT_GB = 4.8  # Warn slightly before 5 GB
ALERT_FILE = "storage_alert.txt"
CEO_MESSAGE = f"⚠ Database storage exceeded {SIZE_LIMIT_GB} GB. Please free space."

def get_db_size_gb():
    """Return DB size in GB."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT pg_database_size(current_database());")
    size_bytes = cur.fetchone()[0]
    cur.close()
    conn.close()
    return size_bytes / (1024 ** 3)

def main():
    print(f"[{datetime.now()}] Checking database storage...")
    size_gb = get_db_size_gb()
    print(f"Current size: {size_gb:.2f} GB")

    if size_gb >= SIZE_LIMIT_GB:
        with open(ALERT_FILE, "w") as f:
            f.write(f"{CEO_MESSAGE} (Current: {size_gb:.2f} GB)")
        print("⚠ Alert file created.")
    else:
        if os.path.exists(ALERT_FILE):
            os.remove(ALERT_FILE)
            print("✅ Alert file removed (DB size normal).")
        else:
            print("✅ No alert. DB size is within limit.")

if __name__ == "__main__":
    main()
