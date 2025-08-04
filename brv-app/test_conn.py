import oracledb
import os
import time
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Oracle DB config
DB_USER = os.getenv("ORACLE_USER")
DB_PASSWORD = os.getenv("ORACLE_PASSWORD")
DB_DSN = os.getenv("ORACLE_DSN")
WALLET_PATH = os.getenv("ORACLE_WALLET_LOCATION")

# Required by oracledb to find tnsnames.ora
os.environ["TNS_ADMIN"] = WALLET_PATH

# Use only the current DSN from .env
DB_SERVICES = [DB_DSN]

def try_connect(dsn):
    print(f"\n🔄 Trying service: {dsn}")
    try:
        start = time.time()
        conn = oracledb.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            dsn=dsn,
            config_dir=WALLET_PATH,
            wallet_location=WALLET_PATH,
            wallet_password=None  # Only needed if wallet is password-protected
        )
        elapsed = time.time() - start
        print(f"✅ SUCCESS: Connected to {dsn} in {elapsed:.2f}s")
        with conn.cursor() as cursor:
            cursor.execute("SELECT sys_context('userenv','db_name') FROM dual")
            print("📦 DB Name:", cursor.fetchone()[0])
        conn.close()
    except Exception as e:
        print(f"❌ FAIL: Could not connect to {dsn}")
        print("   ↳ Error:", str(e))

# === MAIN TEST LOOP ===
print("🚀 Oracle DB Service Connection Test\n")
for svc in DB_SERVICES:
    try_connect(svc)
