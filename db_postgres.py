# db_postgres.py
import os
import logging
from datetime import datetime
from typing import Optional, Tuple, List, Dict, Any
import mimetypes
import psycopg2
from psycopg2.extras import RealDictCursor, Json
import bcrypt
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


# -----------------------------
# Connection
# -----------------------------
def get_conn():
    """Get PostgreSQL database connection."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable not set")
    return psycopg2.connect(
        database_url,
        sslmode=os.getenv("PGSSLMODE", "require")
    )


# -----------------------------
# Initialization / migrations
# -----------------------------
def _ensure_column(cur, table: str, column: str, ddl: str):
    """Safely add column if it doesn't exist."""
    try:
        cur.execute(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = %s AND column_name = %s
                ) THEN
                    EXECUTE %s;
                END IF;
            END$$;
        """, (table, column, f"ALTER TABLE {table} ADD COLUMN {ddl}"))
        logger.info(f"Column check/add for {table}.{column} completed")
    except Exception as e:
        logger.error(f"Failed to ensure column {table}.{column}: {e}")
        raise


def init_db():
    """Initialize database tables and ensure schema consistency with built-in migration."""
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                logger.info("Starting database initialization...")

                # USERS
                cur.execute("""
                            CREATE TABLE IF NOT EXISTS users
                            (
                                id
                                SERIAL
                                PRIMARY
                                KEY,
                                email
                                VARCHAR
                            (
                                255
                            ) UNIQUE NOT NULL,
                                password_hash VARCHAR
                            (
                                255
                            ) NOT NULL,
                                role VARCHAR
                            (
                                50
                            ) NOT NULL DEFAULT 'candidate',
                                force_password_reset BOOLEAN DEFAULT FALSE,
                                can_view_cvs BOOLEAN DEFAULT FALSE,
                                can_delete_records BOOLEAN DEFAULT FALSE,
                                can_grant_delete BOOLEAN DEFAULT FALSE,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                                );
                            """)

                # CANDIDATES - Create base table first
                cur.execute("""
                            CREATE TABLE IF NOT EXISTS candidates
                            (
                                id
                                SERIAL
                                PRIMARY
                                KEY,
                                candidate_id
                                VARCHAR
                            (
                                50
                            ) UNIQUE NOT NULL,
                                name VARCHAR
                            (
                                255
                            ),
                                email VARCHAR
                            (
                                255
                            ),
                                phone VARCHAR
                            (
                                50
                            ),
                                address TEXT, -- keep for older data (unused by UI)
                                form_data JSONB DEFAULT '{}'::jsonb,
                                resume_link TEXT,
                                can_edit BOOLEAN DEFAULT FALSE,
                                created_by VARCHAR
                            (
                                100
                            ),
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                                );
                            """)

                # Add all missing columns for expanded pre-interview fields
                logger.info("Running database migration to add missing columns...")

                # List of columns to ensure exist
                columns_to_ensure = [
                    ("current_address", "TEXT"),
                    ("permanent_address", "TEXT"),
                    ("dob", "DATE"),
                    ("caste", "VARCHAR(100)"),
                    ("sub_caste", "VARCHAR(100)"),
                    ("marital_status", "VARCHAR(50)"),
                    ("highest_qualification", "VARCHAR(255)"),
                    ("work_experience", "TEXT"),
                    ("referral", "VARCHAR(255)"),
                    ("ready_festivals", "BOOLEAN DEFAULT FALSE"),
                    ("ready_late_nights", "BOOLEAN DEFAULT FALSE"),
                    ("cv_file", "BYTEA"),
                    ("cv_filename", "TEXT")
                ]

                for col_name, col_type in columns_to_ensure:
                    _ensure_column(cur, "candidates", col_name, col_type)

                # INTERVIEWS
                cur.execute("""
                            CREATE TABLE IF NOT EXISTS interviews
                            (
                                id
                                SERIAL
                                PRIMARY
                                KEY,
                                candidate_id
                                VARCHAR
                            (
                                50
                            ) NOT NULL REFERENCES candidates
                            (
                                candidate_id
                            ) ON DELETE CASCADE,
                                scheduled_at TIMESTAMP,
                                interviewer VARCHAR
                            (
                                255
                            ),
                                result VARCHAR
                            (
                                50
                            ),
                                notes TEXT,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                                );
                            """)

                # RECEPTIONIST ASSESSMENTS
                cur.execute("""
                            CREATE TABLE IF NOT EXISTS receptionist_assessments
                            (
                                id
                                SERIAL
                                PRIMARY
                                KEY,
                                candidate_id
                                VARCHAR
                            (
                                50
                            ) NOT NULL REFERENCES candidates
                            (
                                candidate_id
                            ) ON DELETE CASCADE,
                                speed_test INTEGER,
                                accuracy_test INTEGER,
                                work_commitment TEXT,
                                english_understanding TEXT,
                                comments TEXT,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                                );
                            """)

                # Indexes
                cur.execute("CREATE INDEX IF NOT EXISTS idx_candidates_name ON candidates(name);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_candidates_email ON candidates(email);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_interviews_candidate_id ON interviews(candidate_id);")

        logger.info("Database initialized / migrated successfully.")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise
    finally:
        conn.close()


# -----------------------------
# Password helpers
# -----------------------------
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


# -----------------------------
# Users
# -----------------------------
def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE email=%s", (email,))
            return cur.fetchone()
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE id=%s", (user_id,))
            return cur.fetchone()
    finally:
        conn.close()


def create_user_in_db(email: str, password: str, role: str = "candidate") -> bool:
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("SELECT 1 FROM users WHERE email=%s", (email,))
            if cur.fetchone():
                return False
            cur.execute("""
                        INSERT INTO users (email, password_hash, role)
                        VALUES (%s, %s, %s)
                        """, (email, hash_password(password), role))
            return True
    finally:
        conn.close()


def update_user_password(email: str, new_password: str) -> bool:
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("""
                        UPDATE users
                        SET password_hash=%s,
                            force_password_reset= FALSE,
                            updated_at=CURRENT_TIMESTAMP
                        WHERE email = %s
                        """, (hash_password(new_password), email))
            return cur.rowcount > 0
    finally:
        conn.close()


def delete_user(user_id: int) -> bool:
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
            return cur.rowcount > 0
    finally:
        conn.close()


def get_all_users() -> List[Dict[str, Any]]:
    conn = get_conn()
    try:
        with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users ORDER BY id")
            return cur.fetchall()
    finally:
        conn.close()


def set_user_permission(user_id: int,
                        can_view: bool | None = None,
                        can_delete: bool | None = None,
                        can_grant_delete: bool | None = None) -> bool:
    if can_view is None and can_delete is None and can_grant_delete is None:
        return False
    sets, params = [], []
    if can_view is not None:
        sets.append("can_view_cvs=%s")
        params.append(can_view)
    if can_delete is not None:
        sets.append("can_delete_records=%s")
        params.append(can_delete)
    if can_grant_delete is not None:
        sets.append("can_grant_delete=%s")
        params.append(can_grant_delete)
    params.append(user_id)
    sql = f"UPDATE users SET {', '.join(sets)}, updated_at=CURRENT_TIMESTAMP WHERE id=%s"
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            return cur.rowcount > 0
    finally:
        conn.close()


def get_all_users_with_permissions() -> List[Dict[str, Any]]:
    conn = get_conn()
    try:
        with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                        SELECT id,
                               email,
                               role,
                               can_view_cvs,
                               can_delete_records,
                               can_grant_delete,
                               created_at,
                               updated_at,
                               force_password_reset
                        FROM users
                        ORDER BY id
                        """)
            return cur.fetchall()
    finally:
        conn.close()


def get_user_permissions(user_id: int) -> Dict[str, Any]:
    conn = get_conn()
    try:
        with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                        SELECT role, can_view_cvs, can_delete_records, can_grant_delete
                        FROM users
                        WHERE id = %s
                        """, (user_id,))
            return cur.fetchone() or {}
    finally:
        conn.close()


def user_can_manage_delete(user_id: int) -> bool:
    p = get_user_permissions(user_id)
    r = (p.get("role") or "").lower()
    return r in ("ceo", "admin") or bool(p.get("can_grant_delete"))


def user_can_delete(user_id: int) -> bool:
    """Return True for Admin/CEO or users explicitly granted delete rights (no 'grant' delegation)."""
    p = get_user_permissions(user_id)
    r = (p.get("role") or "").lower()
    return r in ("ceo", "admin") or bool(p.get("can_delete_records"))


# -----------------------------
# Candidate CRUD + Search
# -----------------------------
def create_candidate_in_db(candidate_id: str,
                           name: str,
                           address: str,
                           dob: Optional[str],
                           caste: Optional[str],
                           email: str,
                           phone: str,
                           form_data: dict,
                           created_by: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    A simplified candidate create helper (matching candidate_view.py's caller).
    Stores current_address into current_address column for compatibility.
    """
    conn = get_conn()
    try:
        with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Check which address columns exist
            cur.execute("""
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_name = 'candidates'
                          AND column_name IN ('current_address', 'address')
                        """)
            existing_address_columns = {row[0] for row in cur.fetchall()}

            # Build the insert query based on available columns
            if 'current_address' in existing_address_columns:
                # Use current_address column (preferred)
                cur.execute("""
                            INSERT INTO candidates (candidate_id, name, email, phone, current_address, form_data,
                                                    created_by, can_edit)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, FALSE) RETURNING *
                            """, (candidate_id, name, email, phone, address, Json(form_data or {}), created_by))
            elif 'address' in existing_address_columns:
                # Fallback to address column if current_address doesn't exist
                cur.execute("""
                            INSERT INTO candidates (candidate_id, name, email, phone, address, form_data, created_by,
                                                    can_edit)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, FALSE) RETURNING *
                            """, (candidate_id, name, email, phone, address, Json(form_data or {}), created_by))
            else:
                # No address column exists, insert without address
                # Store address in form_data instead
                updated_form_data = form_data or {}
                updated_form_data['current_address'] = address
                cur.execute("""
                            INSERT INTO candidates (candidate_id, name, email, phone, form_data, created_by, can_edit)
                            VALUES (%s, %s, %s, %s, %s, %s, FALSE) RETURNING *
                            """, (candidate_id, name, email, phone, Json(updated_form_data), created_by))

            return cur.fetchone()
    finally:
        conn.close()


def get_candidate_by_id(candidate_id: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM candidates WHERE candidate_id=%s", (candidate_id,))
            return cur.fetchone()
    finally:
        conn.close()


def get_all_candidates() -> List[Dict[str, Any]]:
    conn = get_conn()
    try:
        with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM candidates ORDER BY created_at DESC")
            return cur.fetchall()
    finally:
        conn.close()


def find_candidates_by_name(q: str) -> List[Dict[str, Any]]:
    conn = get_conn()
    try:
        with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                        SELECT *
                        FROM candidates
                        WHERE LOWER(name) LIKE %s
                        ORDER BY updated_at DESC LIMIT 200
                        """, (f"%{q.lower()}%",))
            return cur.fetchall()
    finally:
        conn.close()


def update_candidate_form_data(candidate_id: str, updates: dict) -> bool:
    allowed_cols = {
        "name", "email", "phone", "current_address", "permanent_address", "dob", "caste",
        "sub_caste", "marital_status", "highest_qualification", "work_experience",
        "referral", "ready_festivals", "ready_late_nights"
    }
    sets, params = [], []

    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            # Check which columns actually exist in the table
            cur.execute("""
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_name = 'candidates'
                        """)
            existing_columns = {row[0] for row in cur.fetchall()}

            # Only update columns that exist and are allowed
            for k, v in (updates or {}).items():
                if k in allowed_cols and k in existing_columns:
                    sets.append(f"{k}=%s")
                    params.append(v)

            form_patch = updates.get("form_patch")
            if form_patch and "form_data" in existing_columns:
                sets.append("form_data = COALESCE(form_data,'{}'::jsonb) || %s::jsonb")
                params.append(Json(form_patch))

            if not sets:
                return False

            params.append(candidate_id)

            cur.execute(f"""
                UPDATE candidates
                SET {', '.join(sets)}, updated_at=CURRENT_TIMESTAMP
                WHERE candidate_id=%s
            """, tuple(params))
            return cur.rowcount > 0
    finally:
        conn.close()


def update_candidate_resume_link(candidate_id: str, resume_link: str) -> bool:
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("""
                        UPDATE candidates
                        SET resume_link=%s,
                            updated_at=CURRENT_TIMESTAMP
                        WHERE candidate_id = %s
                        """, (resume_link, candidate_id))
            return cur.rowcount > 0
    finally:
        conn.close()


def set_candidate_permission(candidate_id: str, can_edit: bool) -> bool:
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("""
                        UPDATE candidates
                        SET can_edit=%s,
                            updated_at=CURRENT_TIMESTAMP
                        WHERE candidate_id = %s
                        """, (can_edit, candidate_id))
            return cur.rowcount > 0
    finally:
        conn.close()


def delete_candidate(candidate_ids, actor_user_id: int) -> (bool, str):
    """
    Deletes one or more candidate records (including CV) if actor_user_id has the right permissions.
    Accepts a single candidate_id (str) or a list of candidate_ids.
    Returns (success, reason) where reason is one of:
      - "ok"
      - "no_permission"
      - "not_found"
      - "db_error"
    """
    # Server-side permission check
    p = get_user_permissions(actor_user_id) or {}
    role = (p.get("role") or "").lower()
    has_permission = role in ("ceo", "admin") or bool(p.get("can_delete_records", False))
    if not has_permission:
        logger.warning("User %s attempted to delete candidate(s) %s without permissions", actor_user_id, candidate_ids)
        return False, "no_permission"

    # Normalize to list
    if isinstance(candidate_ids, str):
        candidate_ids = [candidate_ids]
    if not candidate_ids:
        return False, "not_found"

    placeholders = ",".join(["%s"] * len(candidate_ids))

    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(f"DELETE FROM candidates WHERE candidate_id IN ({placeholders})", tuple(candidate_ids))
            if cur.rowcount == 0:
                return False, "not_found"
            return True, "ok"
    except Exception:
        logger.exception("Error deleting candidate(s) %s", candidate_ids)
        return False, "db_error"
    finally:
        conn.close()


# -----------------------------
# CV storage helpers
# -----------------------------
def save_candidate_cv(candidate_id: str, file_bytes: bytes, filename: Optional[str] = None) -> bool:
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("""
                        UPDATE candidates
                        SET cv_file=%s,
                            cv_filename=%s,
                            updated_at=CURRENT_TIMESTAMP
                        WHERE candidate_id = %s
                        """, (psycopg2.Binary(file_bytes), filename, candidate_id))
            return cur.rowcount > 0
    finally:
        conn.close()


def clear_candidate_cv(candidate_id: str) -> bool:
    """Remove stored CV file and filename for a candidate without deleting the record."""
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE candidates
                SET cv_file=NULL,
                    cv_filename=NULL,
                    updated_at=CURRENT_TIMESTAMP
                WHERE candidate_id = %s
                """,
                (candidate_id,)
            )
            return cur.rowcount > 0
    finally:
        conn.close()


def get_candidate_cv_secure(candidate_id: str, actor_user_id: int) -> Tuple[
    Optional[bytes], Optional[str], Optional[str], str]:
    """
    Securely fetch a candidate's CV.
    Returns: (file_bytes, filename, mime_type, reason)
    reason ∈ {"ok", "no_permission", "not_found", "error"}
    """
    try:
        # Permission check
        perms = get_user_permissions(actor_user_id)
        role = (perms.get("role") or "").lower()
        if not (role in ("ceo", "admin") or perms.get("can_view_cvs")):
            return None, None, None, "no_permission"

    cursor = conn.cursor()
    cursor.execute("SELECT cv_link FROM candidates WHERE candidate_id = %s", (candidate_id,))
    result = cursor.fetchone()
    cursor.close()

    if not result or not result[0]:
        return None

    link = result[0]

    # Fix Google Drive preview URL for embedding
    if "drive.google.com" in link:
        if "view" in link:
            return link
        elif "file/d/" in link:
            file_id = link.split("file/d/")[1].split("/")[0]
            return f"https://drive.google.com/file/d/{file_id}/preview"
        elif "id=" in link:
            file_id = link.split("id=")[1]
            return f"https://drive.google.com/file/d/{file_id}/preview"
    return link

def get_total_cv_storage_usage() -> int:
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("SELECT COALESCE(SUM(OCTET_LENGTH(cv_file)),0) FROM candidates")
            return cur.fetchone()[0] or 0
    finally:
        conn.close()


# -----------------------------
# Receptionist assessments
# -----------------------------
def save_receptionist_assessment(candidate_id: str,
                                 speed_test: Optional[int],
                                 accuracy_test: Optional[int],
                                 work_commitment: Optional[str],
                                 english_understanding: Optional[str],
                                 comments: Optional[str]) -> bool:
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("""
                        INSERT INTO receptionist_assessments
                        (candidate_id, speed_test, accuracy_test, work_commitment,
                         english_understanding, comments)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """, (candidate_id, speed_test, accuracy_test, work_commitment,
                              english_understanding, comments))
            return True
    finally:
        conn.close()


def get_receptionist_assessments(candidate_id: str) -> List[Dict[str, Any]]:
    conn = get_conn()
    try:
        with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                        SELECT *
                        FROM receptionist_assessments
                        WHERE candidate_id = %s
                        ORDER BY created_at DESC
                        """, (candidate_id,))
            return cur.fetchall()
    finally:
        conn.close()


# -----------------------------
# Interviews
# -----------------------------
def create_interview(candidate_id: str,
                     scheduled_at: Optional[datetime],
                     interviewer: Optional[str],
                     result: Optional[str] = None,
                     notes: Optional[str] = None) -> Optional[int]:
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("""
                        INSERT INTO interviews (candidate_id, scheduled_at, interviewer, result, notes)
                        VALUES (%s, %s, %s, %s, %s) RETURNING id
                        """, (candidate_id, scheduled_at, interviewer, result, notes))
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        conn.close()


def get_interviews_for_candidate(candidate_id: str) -> List[Dict[str, Any]]:
    conn = get_conn()
    try:
        with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                        SELECT *
                        FROM interviews
                        WHERE candidate_id = %s
                        ORDER BY created_at DESC
                        """, (candidate_id,))
            return cur.fetchall()
    finally:
        conn.close()


def get_all_interviews() -> List[Dict[str, Any]]:
    conn = get_conn()
    try:
        with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                        SELECT i.*, c.name AS candidate_name, c.email AS candidate_email
                        FROM interviews i
                                 JOIN candidates c ON c.candidate_id = i.candidate_id
                        ORDER BY i.scheduled_at DESC NULLS LAST, i.created_at DESC
                        """)
            return cur.fetchall()
    finally:
        conn.close()


# -----------------------------
# New helpers: HISTORY + INTERVIEWER STATS + PERMISSIONS UPDATE
# -----------------------------
def get_candidate_history(candidate_id: str) -> List[Dict[str, Any]]:
    """
    Return a merged chronological timeline for a candidate.
    Each item is a dict: { event: str, details: str, created_at: datetime, actor: Optional[str] }
    """
    conn = get_conn()
    try:
        with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            # ensure candidate exists
            cur.execute(
                "SELECT candidate_id, name, created_at, updated_at, created_by FROM candidates WHERE candidate_id=%s",
                (candidate_id,))
            cand = cur.fetchone()
            if not cand:
                return []

            timeline: List[Dict[str, Any]] = []

            # candidate created/updated events
            if cand.get("created_at"):
                timeline.append({
                    "event": "candidate_created",
                    "details": f"Candidate record created ({cand.get('name')})",
                    "created_at": cand.get("created_at"),
                    "actor": cand.get("created_by") if cand.get("created_by") else None
                })
            if cand.get("updated_at") and cand.get("updated_at") != cand.get("created_at"):
                timeline.append({
                    "event": "candidate_updated",
                    "details": f"Candidate record updated",
                    "created_at": cand.get("updated_at"),
                    "actor": None
                })

            # receptionist assessments
            cur.execute("""
                        SELECT id,
                               speed_test,
                               accuracy_test,
                               work_commitment,
                               english_understanding,
                               comments,
                               created_at
                        FROM receptionist_assessments
                        WHERE candidate_id = %s
                        ORDER BY created_at DESC
                        """, (candidate_id,))
            for r in cur.fetchall():
                details = f"Speed: {r.get('speed_test')}, Accuracy: {r.get('accuracy_test')}"
                if r.get("work_commitment"):
                    details += f", Commitment: {r.get('work_commitment')}"
                if r.get("english_understanding"):
                    details += f", English: {r.get('english_understanding')}"
                if r.get("comments"):
                    details += f", Notes: {r.get('comments')}"
                timeline.append({
                    "event": "receptionist_assessment",
                    "details": details,
                    "created_at": r.get("created_at"),
                    "actor": "receptionist"
                })

            # interviews (include scheduled_at as the event time if present; fallback to created_at)
            cur.execute("""
                        SELECT id, scheduled_at, created_at, result, interviewer, notes
                        FROM interviews
                        WHERE candidate_id = %s
                        """, (candidate_id,))
            for iv in cur.fetchall():
                ev_time = iv.get("scheduled_at") or iv.get("created_at")
                details = f"Result: {iv.get('result') or 'unspecified'}"
                if iv.get("notes"):
                    details += f", Notes: {iv.get('notes')}"
                timeline.append({
                    "event": "interview",
                    "details": details,
                    "created_at": ev_time,
                    "actor": iv.get("interviewer")
                })

            # sort timeline newest first
            timeline_sorted = sorted(
                timeline,
                key=lambda x: x.get("created_at") or datetime(1970, 1, 1),
                reverse=True
            )
            return timeline_sorted
    finally:
        conn.close()


def get_interviewer_performance_stats(interviewer_id: str) -> Dict[str, Any]:
    """
    Return simple interviewer performance stats for a given interviewer identifier (string).
    """
    conn = get_conn()
    try:
        with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                        SELECT COUNT(*)::int AS total_interviews, SUM(CASE WHEN LOWER(result) = 'scheduled' THEN 1 ELSE 0 END)::int AS scheduled, SUM(CASE
                                                                                                                                                          WHEN LOWER(result) IN ('completed', 'pass', 'fail')
                                                                                                                                                              THEN 1
                                                                                                                                                          ELSE 0 END)::int AS completed, SUM(CASE WHEN LOWER(result) = 'pass' THEN 1 ELSE 0 END) ::int AS passed
                        FROM interviews
                        WHERE interviewer = %s
                        """, (interviewer_id,))
            row = cur.fetchone() or {}
            total = int(row.get("total_interviews") or 0)
            scheduled = int(row.get("scheduled") or 0)
            completed = int(row.get("completed") or 0)
            passed = int(row.get("passed") or 0)
            success_rate = int((passed / completed) * 100) if completed > 0 else 0
            return {
                "total_interviews": total,
                "scheduled": scheduled,
                "completed": completed,
                "passed": passed,
                "success_rate": success_rate,
            }
    finally:
        conn.close()


def update_user_permissions(user_id: int, perms: Dict[str, Any]) -> bool:
    """
    Update only the provided permission fields.
    Example payloads:
      {"can_view_cvs": True}
      {"can_view_cvs": False, "can_delete_records": True}
    """
    sets, params = [], []
    if "can_view_cvs" in perms:
        sets.append("can_view_cvs=%s")
        params.append(bool(perms.get("can_view_cvs")))
    if "can_delete_records" in perms:
        sets.append("can_delete_records=%s")
        params.append(bool(perms.get("can_delete_records")))
    # Intentionally ignore can_grant_delete so UI cannot toggle it anymore
    if not sets:
        return False
    params.append(int(user_id))

    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE users SET {', '.join(sets)}, updated_at=CURRENT_TIMESTAMP WHERE id=%s",
                tuple(params),
            )
            return cur.rowcount > 0
    finally:
        conn.close()


# -----------------------------
# Search helpers
# -----------------------------
def search_candidates_by_name_or_email(query: str) -> List[Dict[str, Any]]:
    conn = get_conn()
    try:
        with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            if query.strip():
                like = f"%{query.lower()}%"
                cur.execute("""
                            SELECT *
                            FROM candidates
                            WHERE LOWER(name) LIKE %s
                               OR LOWER(email) LIKE %s
                            ORDER BY updated_at DESC LIMIT 50
                            """, (like, like))
            else:
                cur.execute("""
                            SELECT *
                            FROM candidates
                            ORDER BY updated_at DESC LIMIT 50
                            """)
            return cur.fetchall()
    finally:
        conn.close()


# -----------------------------
# Statistics for CEO
# -----------------------------
def get_candidate_statistics() -> Dict[str, Any]:
    stats: Dict[str, Any] = {}
    conn = get_conn()
    try:
        with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT COUNT(*) AS c FROM candidates")
            stats["total_candidates"] = cur.fetchone()["c"]

            cur.execute("SELECT COUNT(*) AS c FROM candidates WHERE DATE(created_at)=CURRENT_DATE")
            stats["candidates_today"] = cur.fetchone()["c"]

            cur.execute("""
                        SELECT COUNT(*) AS c
                        FROM candidates
                        WHERE DATE_TRUNC('week', created_at) = DATE_TRUNC('week', CURRENT_DATE)
                        """)
            stats["candidates_this_week"] = cur.fetchone()["c"]

            cur.execute("""
                        SELECT COUNT(*) AS c
                        FROM candidates
                        WHERE DATE_TRUNC('month', created_at) = DATE_TRUNC('month', CURRENT_DATE)
                        """)
            stats["candidates_this_month"] = cur.fetchone()["c"]

            cur.execute("SELECT COUNT(*) AS c FROM candidates WHERE cv_file IS NOT NULL OR resume_link IS NOT NULL")
            stats["candidates_with_resume"] = cur.fetchone()["c"]
            stats["candidates_without_resume"] = stats["total_candidates"] - stats["candidates_with_resume"]

            cur.execute("SELECT COUNT(*) AS c FROM interviews")
            stats["total_interviews"] = cur.fetchone()["c"]

            cur.execute("SELECT result, COUNT(*) AS c FROM interviews GROUP BY result")
            stats["interview_results"] = {(r["result"] or "unspecified"): r["c"] for r in cur.fetchall()}

            cur.execute("SELECT COUNT(*) AS c FROM interviews WHERE result IS NULL OR result ILIKE 'scheduled'")
            stats["interviews_scheduled"] = cur.fetchone()["c"]

            cur.execute(
                "SELECT COUNT(*) AS c FROM interviews WHERE result IS NOT NULL AND result NOT ILIKE 'scheduled'")
            stats["interviews_completed"] = cur.fetchone()["c"]

            cur.execute("""
                        SELECT COUNT(*) AS c
                        FROM interviews
                        WHERE DATE_TRUNC('week', COALESCE(scheduled_at, created_at)) = DATE_TRUNC('week', CURRENT_DATE)
                        """)
            stats["interviews_this_week"] = cur.fetchone()["c"]

            cur.execute("SELECT COUNT(*) AS c FROM interviews WHERE result ILIKE 'pass'")
            stats["interviews_passed"] = cur.fetchone()["c"] if cur.rowcount is not None else 0

            cur.execute("SELECT COUNT(*) AS c FROM interviews WHERE result ILIKE 'fail'")
            stats["interviews_failed"] = cur.fetchone()["c"] if cur.rowcount is not None else 0

            cur.execute("SELECT COUNT(*) AS c FROM interviews WHERE result ILIKE 'on hold'")
            stats["interviews_on_hold"] = cur.fetchone()["c"] if cur.rowcount is not None else 0

            cur.execute("SELECT interviewer, COUNT(*) AS c FROM interviews GROUP BY interviewer")
            stats["per_interviewer"] = {(r["interviewer"] or "unknown"): r["c"] for r in cur.fetchall()}

            cur.execute("SELECT role, COUNT(*) AS c FROM users GROUP BY role")
            stats["users_per_role"] = {r["role"]: r["c"] for r in cur.fetchall()}

            cur.execute("SELECT COUNT(*) AS c FROM receptionist_assessments")
            stats["total_assessments"] = cur.fetchone()["c"]

            cur.execute("""
                        SELECT AVG(speed_test) AS avg_speed, AVG(accuracy_test) AS avg_accuracy
                        FROM receptionist_assessments
                        """)
            row = cur.fetchone()
            stats["avg_speed_test"] = float(row["avg_speed"] or 0)
            stats["avg_accuracy_test"] = float(row["avg_accuracy"] or 0)

        return stats
    finally:
        conn.close()


# -----------------------------
# Seeding (optional)
# -----------------------------
def seed_sample_users():
    """Create sample users for testing (idempotent)."""
    samples = [
        ("admin@brv.com", "admin123", "admin"),
        ("ceo@brv.com", "ceo123", "ceo"),
        ("receptionist@brv.com", "recep123", "receptionist"),
        ("interviewer@brv.com", "interviewer123", "interviewer"),
        ("hr@brv.com", "hr123", "hr"),
        ("candidate@brv.com", "candidate123", "candidate"),
    ]
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            for email, pw, role in samples:
                cur.execute("SELECT 1 FROM users WHERE email=%s", (email,))
                if not cur.fetchone():
                    cur.execute("""
                                INSERT INTO users (email, password_hash, role)
                                VALUES (%s, %s, %s)
                                """, (email, hash_password(pw), role))
    finally:
        conn.close()