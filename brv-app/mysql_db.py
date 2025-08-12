import os
import psycopg2

# ✅ Load PostgreSQL connection details from environment variables
PG_HOST = os.getenv("PG_HOST", "shuttle.proxy.rlwy.net")
PG_PORT = os.getenv("PG_PORT", "34781")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "vECSzNiYXpmNPfUNjMXLmdMpOLVuSdhq")
PG_DATABASE = os.getenv("PG_DATABASE", "railway")

def get_db_connection():
    """Create and return a PostgreSQL connection."""
    try:
        conn = psycopg2.connect(
            host=PG_HOST,
            port=PG_PORT,
            user=PG_USER,
            password=PG_PASSWORD,
            dbname=PG_DATABASE,
            sslmode="require"  # Railway requires SSL
        )
        return conn
    except Exception as e:
        print(f"❌ PostgreSQL connection failed: {e}")
        return None

# ✅ Optional: Test connection
if __name__ == "__main__":
    conn = get_db_connection()
    if conn:
        print("✅ Connected to PostgreSQL successfully!")
        conn.close()
    else:
        print("❌ Failed to connect to PostgreSQL.")
