import asyncpg
from env_config import get_credentials

pool = None

async def init_db():
    """
    Initialize the asyncpg connection pool for PostgreSQL.
    """
    global pool
    if pool is None:
        creds = get_credentials()
        pool = await asyncpg.create_pool(
            host=creds["host"],
            port=creds["port"],
            user=creds["user"],
            password=creds["password"],
            database=creds["database"],
            min_size=1,
            max_size=10
        )
        print("✅ PostgreSQL connection pool initialized.")

async def close_db():
    """
    Close the connection pool.
    """
    global pool
    if pool:
        await pool.close()
        pool = None
        print("✅ PostgreSQL connection pool closed.")

async def fetch_all(query, params=None):
    """
    Fetch all rows for a query as dictionaries.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *(params or []))
        return [dict(row) for row in rows]

async def fetch_one(query, params=None):
    """
    Fetch a single row as a dictionary.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *(params or []))
        return dict(row) if row else None

async def execute(query, params=None):
    """
    Execute a statement (INSERT, UPDATE, DELETE).
    """
    async with pool.acquire() as conn:
        return await conn.execute(query, *(params or []))
