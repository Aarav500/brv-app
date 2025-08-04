from dotenv import load_dotenv
import os
import oracledb

# Load environment variables from .env
load_dotenv()

# Oracle DB config
DB_USER = os.getenv("ORACLE_USER")
DB_PASSWORD = os.getenv("ORACLE_PASSWORD")
DB_DSN = os.getenv("ORACLE_DSN")
WALLET_PATH = os.getenv("ORACLE_WALLET_LOCATION")

# Required by oracledb to find tnsnames.ora
os.environ["TNS_ADMIN"] = WALLET_PATH

print("Oracle DB Connection Test")
print(f"User: {DB_USER}")
print(f"DSN: {DB_DSN}")
print(f"Wallet Path: {WALLET_PATH}")
print(f"TNS_ADMIN: {os.environ['TNS_ADMIN']}")

try:
    # Connect
    print("\nAttempting connection...")
    conn = oracledb.connect(
        user=DB_USER,
        password=DB_PASSWORD,
        dsn=DB_DSN,
        config_dir=WALLET_PATH,
        wallet_location=WALLET_PATH,
        wallet_password=None  # Only needed if wallet is password-protected
    )
    
    print("✅ Connection successful!")
    
    # Test a simple query
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM DUAL")
    result = cursor.fetchone()
    print(f"Query result: {result[0]}")
    
    # Close connection
    conn.close()
    print("Connection closed.")
    
except Exception as e:
    print(f"❌ Connection failed: {e}")