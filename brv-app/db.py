# db.py
import os
import asyncio
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

import asyncpg
from dotenv import load_dotenv

load_dotenv()

PGHOST = os.getenv("PGHOST", "localhost")
PGPORT = int(os.getenv("PGPORT", 5432))
PGUSER = os.getenv("PGUSER", "postgres")
PGPASSWORD = os.getenv("PGPASSWORD", "")
PGDATABASE = os.getenv("PGDATABASE", "postgres")

DATABASE_URL = f"postgresql://{PGUSER}:{PGPASSWORD}@{PGHOST}:{PGPORT}/{PGDATABASE}"

# connection pool
pool: Optional[asyncpg.pool.Pool] = None

# -------------------------
# Initialization / helpers
# -------------------------
async def init_db(min_size: int = 1, max_size: int = 10):
    """Initialize asyncpg connection pool."""
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(DATABASE_URL, min_size=min_size, max_size=max_size, statement_cache_size=0, command_timeout=60)
        # Optional: ensure required tables exist (migrations are preferred)
        # await _ensure_schema()
        print("✅ PostgreSQL pool initialized")


async def close_db():
    """Close pool."""
    global pool
    if pool:
        await pool.close()
    pool = None
    print("🔌 PostgreSQL pool closed")


async def fetch(query: str, *args) -> List[asyncpg.Record]:
    """Run SELECT returning multiple rows."""
    async with pool.acquire() as conn:
        return await conn.fetch(query, *args)


async def fetchrow(query: str, *args) -> Optional[asyncpg.Record]:
    """Run SELECT returning single row."""
    async with pool.acquire() as conn:
        return await conn.fetchrow(query, *args)


async def execute(query: str, *args) -> str:
    """Run INSERT/UPDATE/DELETE. Returns status string e.g. 'INSERT 0 1' or 'UPDATE 1'."""
    async with pool.acquire() as conn:
        return await conn.execute(query, *args)


# -------------------------
# Authentication wrapper
# -------------------------
async def authenticate(username_or_email: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Authenticate a user. Returns user dict on success, otherwise None.
    Expects users table to have: id, email, username, password (hashed), role, force_password_reset, last_password_change
    """
    # fetch user by email or username
    query = "SELECT id, email, username, password, role, force_password_reset, last_password_change FROM users WHERE email = $1 OR username = $1"
    user = await fetchrow(query, username_or_email)
    if not user:
        return None

    hashed = user.get("password")
    # Try to verify using security.verify_password if available
    try:
        from security import verify_password
        ok = verify_password(hashed, password)
    except Exception:
        # Fallback — NOT RECOMMENDED: plain compare
        ok = (hashed == password)

    if not ok:
        return None

    # convert Record -> dict
    return dict(user)


# -------------------------
# Activity log functions
# -------------------------
async def log_activity(user_id: str, action: str, details: Optional[str] = None) -> bool:
    """
    Log an activity to activity_log.
    Creates log_id UUID and inserts timestamp.
    """
    log_id = str(uuid.uuid4())
    query = """
    INSERT INTO activity_log (log_id, user_id, action, details, timestamp)
    VALUES ($1, $2, $3, $4, NOW())
    """
    try:
        await execute(query, log_id, user_id, action, details)
        return True
    except Exception as e:
        # Optionally log error
        print("log_activity error:", e)
        return False


async def get_activity_logs(limit: int = 100, offset: int = 0,
                            user_id: Optional[str] = None, action: Optional[str] = None,
                            start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retrieve activity logs with filtering.
    start_date and end_date expected as 'YYYY-MM-DD' strings.
    """
    where_clauses = []
    params = []
    idx = 1

    if user_id:
        where_clauses.append(f"user_id = ${idx}"); params.append(user_id); idx += 1
    if action:
        where_clauses.append(f"action = ${idx}"); params.append(action); idx += 1
    if start_date:
        where_clauses.append(f"timestamp >= to_timestamp(${idx}, 'YYYY-MM-DD')"); params.append(start_date); idx += 1
    if end_date:
        where_clauses.append(f"timestamp <= (to_timestamp(${idx}, 'YYYY-MM-DD') + interval '1 day')"); params.append(end_date); idx += 1

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    query = f"""
    SELECT log_id, user_id, action, details, to_char(timestamp, 'YYYY-MM-DD HH24:MI:SS') as timestamp
    FROM activity_log
    {where_sql}
    ORDER BY timestamp DESC
    LIMIT ${idx} OFFSET ${idx+1}
    """
    params.extend([limit, offset])
    rows = await fetch(query, *params)
    return [dict(r) for r in rows]


# -------------------------
# Resume metadata functions
# -------------------------
async def add_resume_metadata(resume_id: str, candidate_id: int, filename: str,
                              file_size: int, mime_type: str, upload_date: datetime, resume_link: str) -> bool:
    query = """
    INSERT INTO resumes_metadata (resume_id, candidate_id, filename, file_size, mime_type, upload_date, resume_link)
    VALUES ($1, $2, $3, $4, $5, $6, $7)
    """
    try:
        await execute(query, resume_id, candidate_id, filename, file_size, mime_type, upload_date, resume_link)
        return True
    except Exception as e:
        print("add_resume_metadata error:", e)
        return False


async def get_resume_metadata(resume_id: Optional[str] = None, candidate_id: Optional[int] = None):
    if resume_id:
        query = """
        SELECT resume_id, candidate_id, filename, file_size, mime_type,
               to_char(upload_date, 'YYYY-MM-DD HH24:MI:SS') as upload_date, resume_link
        FROM resumes_metadata
        WHERE resume_id = $1
        """
        return dict(await fetchrow(query, resume_id))
    elif candidate_id:
        query = """
        SELECT resume_id, candidate_id, filename, file_size, mime_type,
               to_char(upload_date, 'YYYY-MM-DD HH24:MI:SS') as upload_date, resume_link
        FROM resumes_metadata
        WHERE candidate_id = $1
        ORDER BY upload_date DESC
        """
        rows = await fetch(query, candidate_id)
        return [dict(r) for r in rows]
    else:
        query = """
        SELECT resume_id, candidate_id, filename, file_size, mime_type,
               to_char(upload_date, 'YYYY-MM-DD HH24:MI:SS') as upload_date, resume_link
        FROM resumes_metadata
        ORDER BY upload_date DESC
        """
        rows = await fetch(query)
        return [dict(r) for r in rows]


async def delete_resume_metadata(resume_id: str) -> bool:
    query = "DELETE FROM resumes_metadata WHERE resume_id = $1"
    try:
        await execute(query, resume_id)
        return True
    except Exception as e:
        print("delete_resume_metadata error:", e)
        return False


# -------------------------
# Interview management
# -------------------------
async def create_interview(candidate_id: int, interviewer_id: str, scheduled_time: str, notes: Optional[str] = None):
    """
    Insert a new interview row. scheduled_time expected in 'YYYY-MM-DD HH24:MI:SS' format.
    Returns (success, interview_id, message)
    """
    interview_id = str(uuid.uuid4())
    query = """
    INSERT INTO interviews (interview_id, candidate_id, interviewer_id, scheduled_time, feedback, status, created_at, updated_at)
    VALUES ($1, $2, $3, to_timestamp($4, 'YYYY-MM-DD HH24:MI:SS'), $5, $6, NOW(), NOW())
    """
    try:
        await execute(query, interview_id, candidate_id, interviewer_id, scheduled_time, notes, "scheduled")
        # update candidate status if you have such function or table
        await update_interview_status(candidate_id, "Interview Scheduled")
        return True, interview_id, "Interview scheduled successfully"
    except Exception as e:
        print("create_interview error:", e)
        return False, None, "Failed to schedule interview"


async def get_interviews_by_candidate(candidate_id: int):
    query = """
    SELECT i.interview_id, i.candidate_id, i.interviewer_id, u.username as interviewer_name,
           to_char(i.scheduled_time, 'YYYY-MM-DD HH24:MI:SS') as scheduled_time,
           i.feedback, i.status, i.result,
           to_char(i.created_at, 'YYYY-MM-DD HH24:MI:SS') as created_at,
           to_char(i.updated_at, 'YYYY-MM-DD HH24:MI:SS') as updated_at
    FROM interviews i
    LEFT JOIN users u ON i.interviewer_id = u.id
    WHERE i.candidate_id = $1
    ORDER BY i.scheduled_time DESC
    """
    rows = await fetch(query, candidate_id)
    return [dict(r) for r in rows]


async def get_interviews_by_interviewer(interviewer_id: str):
    query = """
    SELECT i.interview_id, i.candidate_id, c.name as candidate_name, i.interviewer_id,
           to_char(i.scheduled_time, 'YYYY-MM-DD HH24:MI:SS') as scheduled_time,
           i.feedback, i.status, i.result,
           to_char(i.created_at, 'YYYY-MM-DD HH24:MI:SS') as created_at,
           to_char(i.updated_at, 'YYYY-MM-DD HH24:MI:SS') as updated_at
    FROM interviews i
    LEFT JOIN candidates c ON i.candidate_id = c.id
    WHERE i.interviewer_id = $1
    ORDER BY i.scheduled_time DESC
    """
    rows = await fetch(query, interviewer_id)
    return [dict(r) for r in rows]


async def update_interview_feedback(interview_id: str, feedback: str, result: str):
    query = """
    UPDATE interviews
    SET feedback = $1,
        result = $2,
        status = $3,
        updated_at = NOW()
    WHERE interview_id = $4
    """
    try:
        await execute(query, feedback, result, result, interview_id)
        # fetch candidate_id to update candidate status
        row = await fetchrow("SELECT candidate_id FROM interviews WHERE interview_id = $1", interview_id)
        if row:
            candidate_id = row["candidate_id"]
            await update_interview_status(candidate_id, result)
            return True, "Interview feedback updated successfully"
        return False, "Interview updated but failed to find candidate"
    except Exception as e:
        print("update_interview_feedback error:", e)
        return False, "Failed to update interview feedback"


# -------------------------
# Candidate status helper
# -------------------------
async def update_interview_status(candidate_id: int, status: str):
    """Update candidate status field"""
    try:
        await execute("UPDATE candidates SET status = $1, updated_at = NOW() WHERE id = $2", status, candidate_id)
    except Exception as e:
        print("update_interview_status error:", e)


# -------------------------
# Optional convenience: sync runner for one-off scripts
# -------------------------
def run_sync(coro):
    """Run an async coroutine from sync code (small helper)."""
    return asyncio.get_event_loop().run_until_complete(coro)
