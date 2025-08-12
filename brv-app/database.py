import os
import asyncpg
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

PGHOST = os.getenv("PGHOST")
PGPORT = os.getenv("PGPORT")
PGUSER = os.getenv("PGUSER")
PGPASSWORD = os.getenv("PGPASSWORD")
PGDATABASE = os.getenv("PGDATABASE")

DATABASE_URL = f"postgresql://{PGUSER}:{PGPASSWORD}@{PGHOST}:{PGPORT}/{PGDATABASE}"

# Connection pool (set in init_db)
pool = None

async def init_db():
    """Initialize the DB connection pool."""
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(DATABASE_URL, ssl="require")
        print("✅ PostgreSQL pool initialized")

async def close_db():
    """Close the connection pool."""
    global pool
    if pool:
        await pool.close()
        pool = None
        print("🔌 PostgreSQL pool closed")

async def fetch(query, *args):
    """Run a SELECT query and return all results."""
    async with pool.acquire() as conn:
        return await conn.fetch(query, *args)

async def fetchrow(query, *args):
    """Run a SELECT query and return one row."""
    async with pool.acquire() as conn:
        return await conn.fetchrow(query, *args)

async def execute(query, *args):
    """Run INSERT/UPDATE/DELETE query."""
    async with pool.acquire() as conn:
        return await conn.execute(query, *args)

# ===== Example functions from your old database.py =====
# Adapt these for your schema. I’m showing a couple; you can follow the same pattern for others.

async def get_user_by_email(email):
    query = "SELECT * FROM users WHERE email = $1"
    return await fetchrow(query, email)

async def create_user(email, username, password, role):
    query = """
    INSERT INTO users (email, username, password, role)
    VALUES ($1, $2, $3, $4)
    RETURNING id
    """
    row = await fetchrow(query, email, username, password, role)
    if row:
        return True, row["id"], "User created successfully"
    return False, None, "Insert failed"

async def update_user_password(user_id, new_password):
    query = "UPDATE users SET password = $1 WHERE id = $2"
    result = await execute(query, new_password, user_id)
    return result.startswith("UPDATE")

