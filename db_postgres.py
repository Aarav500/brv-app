import os
import psycopg2
from psycopg2.extras import RealDictCursor, Json
import bcrypt
from datetime import datetime
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def get_conn():
    """Get PostgreSQL database connection"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable not set")

    return psycopg2.connect(
        database_url,
        sslmode=os.getenv("PGSSLMODE", "require")
    )

def init_db():
    """Initialize database tables and ensure schema consistency"""
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                # --- USERS TABLE ---
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users
                    (
                        id SERIAL PRIMARY KEY,
                        email VARCHAR(255) UNIQUE NOT NULL,
                        password_hash VARCHAR(255) NOT NULL,
                        role VARCHAR(50) NOT NULL DEFAULT 'candidate',
                        force_password_reset BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                # ✅ Ensure permission columns exist (migration-safe)
                cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS can_view_cvs BOOLEAN DEFAULT FALSE;")
                cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS can_delete_records BOOLEAN DEFAULT FALSE;")
                cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS can_grant_delete BOOLEAN DEFAULT FALSE;")

                # --- CANDIDATES TABLE ---
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS candidates
                    (
                        id SERIAL PRIMARY KEY,
                        candidate_id VARCHAR(50) UNIQUE NOT NULL,
                        name VARCHAR(255),
                        address TEXT,
                        dob DATE,
                        caste VARCHAR(100),
                        email VARCHAR(255),
                        phone VARCHAR(50),
                        form_data JSONB DEFAULT '{}'::jsonb,
                        resume_link TEXT,
                        can_edit BOOLEAN DEFAULT FALSE,
                        created_by VARCHAR(100),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                # ✅ Ensure CV columns exist (migration-safe)
                cur.execute("ALTER TABLE candidates ADD COLUMN IF NOT EXISTS cv_file BYTEA;")
                cur.execute("ALTER TABLE candidates ADD COLUMN IF NOT EXISTS cv_filename TEXT;")

                # --- INTERVIEWS TABLE ---
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS interviews
                    (
                        id SERIAL PRIMARY KEY,
                        candidate_id VARCHAR(50) NOT NULL,
                        scheduled_at TIMESTAMP,
                        interviewer VARCHAR(255),
                        result VARCHAR(50),
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (candidate_id) REFERENCES candidates(candidate_id)
                    );
                """)

                # Indexes
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_candidates_name ON candidates(name);
                    CREATE INDEX IF NOT EXISTS idx_candidates_email ON candidates(email);
                    CREATE INDEX IF NOT EXISTS idx_interviews_candidate_id ON interviews(candidate_id);
                """)

                # --- RECEPTIONIST ASSESSMENTS ---
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS receptionist_assessments
                    (
                        id SERIAL PRIMARY KEY,
                        candidate_id VARCHAR(50) NOT NULL REFERENCES candidates(candidate_id),
                        speed_test INTEGER,
                        accuracy_test INTEGER,
                        work_commitment TEXT,
                        english_understanding TEXT,
                        comments TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

        logger.info("Database tables initialized successfully (with migration checks)")
    except Exception:
        logger.exception("Failed to initialize database")
        raise
    finally:
        conn.close()

# === Password utilities ===

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False


# === User management ===

def get_user_by_email(email: str):
    conn = get_conn()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM users WHERE email = %s", (email,))
                return cur.fetchone()
    except Exception:
        logger.exception(f"Error getting user by email: {email}")
        return None
    finally:
        conn.close()


def get_user_by_id(user_id: int):
    conn = get_conn()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
                return cur.fetchone()
    except Exception:
        logger.exception(f"Error getting user by ID: {user_id}")
        return None
    finally:
        conn.close()


def update_user_role(email: str, new_role: str) -> bool:
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET role = %s, updated_at = CURRENT_TIMESTAMP WHERE email = %s",
                    (new_role, email)
                )
                return cur.rowcount > 0
    except Exception:
        logger.exception(f"Error updating user role for {email}")
        return False
    finally:
        conn.close()


def update_user_password(email: str, new_password: str) -> bool:
    conn = get_conn()
    try:
        password_hash = hash_password(new_password)
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE users
                       SET password_hash        = %s,
                           force_password_reset = FALSE,
                           updated_at           = CURRENT_TIMESTAMP
                       WHERE email = %s""",
                    (password_hash, email)
                )
                return cur.rowcount > 0
    except Exception:
        logger.exception(f"Error updating password for {email}")
        return False
    finally:
        conn.close()


def get_all_users():
    conn = get_conn()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM users ORDER BY created_at DESC")
                return cur.fetchall()
    except Exception:
        logger.exception("Error getting all users")
        return []
    finally:
        conn.close()


def create_user_in_db(email: str, password: str, role: str = "candidate") -> bool:
    conn = get_conn()
    try:
        password_hash = hash_password(password)
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO users (email, password_hash, role)
                    VALUES (%s, %s, %s)
                """, (email, password_hash, role))
                return True
    except psycopg2.errors.UniqueViolation:
        logger.warning(f"User with email {email} already exists")
        return False
    except Exception:
        logger.exception(f"Error creating user {email}")
        return False
    finally:
        conn.close()


def delete_user(user_id: int) -> bool:
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
                return cur.rowcount > 0
    except Exception:
        logger.exception(f"Error deleting user {user_id}")
        return False
    finally:
        conn.close()


# === CV Management ===

def save_candidate_cv(candidate_id: str, file_bytes: bytes, filename: str | None = None) -> bool:
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE candidates
                    SET cv_file = %s, cv_filename = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE candidate_id = %s
                """, (psycopg2.Binary(file_bytes), filename, candidate_id))
                if cur.rowcount == 0:
                    logger.warning(f"No candidate found for resume upload (candidate_id={candidate_id})")
                else:
                    logger.info(f"Resume saved for candidate {candidate_id} as {filename}")
                return cur.rowcount > 0
    except Exception:
        logger.exception(f"Error saving CV for candidate {candidate_id}")
        return False
    finally:
        conn.close()


def get_candidate_cv(candidate_id: str):
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT cv_file, cv_filename FROM candidates WHERE candidate_id = %s", (candidate_id,))
                row = cur.fetchone()
                if row and row[0]:
                    return bytes(row[0]), row[1]
                return None, None
    except Exception:
        logger.exception(f"Error retrieving CV for candidate {candidate_id}")
        return None, None
    finally:
        conn.close()


def delete_candidate_cv(candidate_id: str) -> bool:
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE candidates
                    SET cv_file = NULL, cv_filename = NULL, updated_at = CURRENT_TIMESTAMP
                    WHERE candidate_id = %s
                """, (candidate_id,))
                return cur.rowcount > 0
    except Exception:
        logger.exception(f"Error deleting CV for candidate {candidate_id}")
        return False
    finally:
        conn.close()


def get_total_cv_storage_usage():
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COALESCE(SUM(OCTET_LENGTH(cv_file)), 0) FROM candidates")
                return cur.fetchone()[0]
    except Exception:
        logger.exception("Error getting CV storage usage")
        return 0
    finally:
        conn.close()




# === Candidate Management ===

def create_candidate_in_db(candidate_id: str, name: str, address: str, dob: str,
                           caste: str, email: str, phone: str,
                           form_data: dict, created_by: str):
    conn = get_conn()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    INSERT INTO candidates (candidate_id, name, address, dob, caste,
                                            email, phone, form_data, created_by, can_edit)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *;
                """, (candidate_id, name, address, dob, caste,
                      email, phone, Json(form_data), created_by, False))
                return cur.fetchone()
    except psycopg2.errors.UniqueViolation:
        logger.warning(f"Candidate ID {candidate_id} already exists")
        return None
    except Exception:
        logger.exception(f"Error creating candidate {candidate_id}")
        return None
    finally:
        conn.close()


def get_candidate_by_id(candidate_id: str):
    conn = get_conn()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM candidates WHERE candidate_id = %s", (candidate_id,))
                return cur.fetchone()
    except Exception:
        logger.exception(f"Error getting candidate {candidate_id}")
        return None
    finally:
        conn.close()


def get_all_candidates():
    conn = get_conn()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM candidates ORDER BY created_at DESC")
                return cur.fetchall()
    except Exception:
        logger.exception("Error getting all candidates")
        return []
    finally:
        conn.close()


def find_candidates_by_name(name: str):
    conn = get_conn()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT *
                    FROM candidates
                    WHERE LOWER(name) LIKE %s
                    ORDER BY updated_at DESC
                """, (f"%{name.lower()}%",))
                return cur.fetchall()
    except Exception:
        logger.exception(f"Error finding candidates by name: {name}")
        return []
    finally:
        conn.close()


def update_candidate_form_data(candidate_id: str, form_data: dict) -> bool:
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE candidates
                    SET form_data  = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE candidate_id = %s
                """, (Json(form_data), candidate_id))
                return cur.rowcount > 0
    except Exception:
        logger.exception(f"Error updating form data for candidate {candidate_id}")
        return False
    finally:
        conn.close()


def update_candidate_resume_link(candidate_id: str, resume_link: str) -> bool:
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE candidates
                    SET resume_link = %s,
                        updated_at  = CURRENT_TIMESTAMP
                    WHERE candidate_id = %s
                """, (resume_link, candidate_id))
                return cur.rowcount > 0
    except Exception:
        logger.exception(f"Error updating resume link for candidate {candidate_id}")
        return False
    finally:
        conn.close()


def set_candidate_permission(candidate_id: str, can_edit: bool) -> bool:
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE candidates
                    SET can_edit   = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE candidate_id = %s
                """, (can_edit, candidate_id))
                return cur.rowcount > 0
    except Exception:
        logger.exception(f"Error setting permission for candidate {candidate_id}")
        return False
    finally:
        conn.close()

def save_receptionist_assessment(candidate_id: str, speed_test: int, accuracy_test: int,
                                 work_commitment: str, english_understanding: str,
                                 comments: str):
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO receptionist_assessments
                        (candidate_id, speed_test, accuracy_test, work_commitment,
                         english_understanding, comments)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (candidate_id, speed_test, accuracy_test,
                      work_commitment, english_understanding, comments))
                return True
    except Exception:
        logger.exception(f"Error saving receptionist assessment for candidate {candidate_id}")
        return False
    finally:
        conn.close()

def get_receptionist_assessment(candidate_id: str):
    """
    Fetch the latest receptionist assessment for a candidate.
    """
    conn = get_conn()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT speed_test, accuracy_test, work_commitment,
                           english_understanding, comments, created_at
                    FROM receptionist_assessments
                    WHERE candidate_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1;
                """, (candidate_id,))
                return cur.fetchone()
    except Exception:
        logger.exception(f"Error getting receptionist assessment for candidate {candidate_id}")
        return None
    finally:
        conn.close()


# === Interview Management ===

def create_interview(candidate_id: str, scheduled_at: datetime, interviewer: str, result: str = None,
                     notes: str = None):
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO interviews (candidate_id, scheduled_at, interviewer, result, notes)
                    VALUES (%s, %s, %s, %s, %s) RETURNING id;
                """, (candidate_id, scheduled_at, interviewer, result, notes))
                return cur.fetchone()[0]
    except Exception:
        logger.exception(f"Error creating interview for candidate {candidate_id}")
        return None
    finally:
        conn.close()


def get_interviews_for_candidate(candidate_id: str):
    conn = get_conn()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT *
                    FROM interviews
                    WHERE candidate_id = %s
                    ORDER BY created_at DESC
                """, (candidate_id,))
                return cur.fetchall()
    except Exception:
        logger.exception(f"Error getting interviews for candidate {candidate_id}")
        return []
    finally:
        conn.close()


def get_all_interviews():
    conn = get_conn()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT i.*, c.name as candidate_name, c.email as candidate_email
                    FROM interviews i
                             JOIN candidates c ON i.candidate_id = c.candidate_id
                    ORDER BY i.scheduled_at DESC
                """)
                return cur.fetchall()
    except Exception:
        logger.exception("Error getting all interviews")
        return []
    finally:
        conn.close()


def search_candidates_by_name_or_email(query: str):
    conn = get_conn()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if query.strip():
                    cur.execute("""
                        SELECT *
                        FROM candidates
                        WHERE LOWER(name) LIKE %s
                           OR LOWER(email) LIKE %s
                        ORDER BY updated_at DESC LIMIT 50
                    """, (f"%{query.lower()}%", f"%{query.lower()}%"))
                else:
                    cur.execute("""
                        SELECT *
                        FROM candidates
                        ORDER BY updated_at DESC LIMIT 50
                    """)
                return cur.fetchall()
    except Exception:
        logger.exception(f"Error searching candidates with query: {query}")
        return []
    finally:
        conn.close()


# === CEO Permission Management ===

def set_user_permission(user_id: int,
                        can_view: bool | None = None,
                        can_delete: bool | None = None,
                        can_grant_delete: bool | None = None) -> bool:
    if can_view is None and can_delete is None and can_grant_delete is None:
        return False

    sets, params = [], []
    if can_view is not None:
        sets.append("can_view_cvs = %s")
        params.append(can_view)
    if can_delete is not None:
        sets.append("can_delete_records = %s")
        params.append(can_delete)
    if can_grant_delete is not None:
        sets.append("can_grant_delete = %s")
        params.append(can_grant_delete)
    params.append(user_id)
    sql = f"UPDATE users SET {', '.join(sets)}, updated_at = CURRENT_TIMESTAMP WHERE id = %s"

    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))
                return cur.rowcount > 0
    except Exception:
        logger.exception(f"Error updating permissions for user {user_id}")
        return False
    finally:
        conn.close()


def get_all_users_with_permissions():
    conn = get_conn()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, email, role, can_view_cvs, can_delete_records, can_grant_delete, created_at
                    FROM users ORDER BY created_at DESC
                """)
                return cur.fetchall()
    except Exception:
        logger.exception("Error getting users with permissions")
        return []
    finally:
        conn.close()

def seed_sample_users():
    """Create sample users for testing (only if they don’t exist)."""
    sample_users = [
        ("admin@brv.com", "admin123", "admin"),
        ("ceo@brv.com", "ceo123", "ceo"),
        ("receptionist@brv.com", "recep123", "receptionist"),
        ("interviewer@brv.com", "interview123", "interviewer"),
        ("hr@brv.com", "hr123", "hr"),
        ("candidate@brv.com", "candidate123", "candidate")
    ]

    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                for email, password, role in sample_users:
                    # check if user already exists
                    cur.execute("SELECT id FROM users WHERE email = %s", (email,))
                    if not cur.fetchone():
                        password_hash = hash_password(password)
                        cur.execute("""
                            INSERT INTO users (email, password_hash, role)
                            VALUES (%s, %s, %s)
                        """, (email, password_hash, role))
                        logger.info(f"Created sample user: {email} with role: {role}")
    except Exception:
        logger.exception("Error creating sample users")
    finally:
        conn.close()

# === Candidate Deletion (direct + permission-aware) ===

def delete_candidate(candidate_id: str) -> bool:
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM interviews WHERE candidate_id = %s", (candidate_id,))
                cur.execute("DELETE FROM candidates WHERE candidate_id = %s", (candidate_id,))
                return cur.rowcount > 0
    except Exception:
        logger.exception(f"Error deleting candidate {candidate_id}")
        return False
    finally:
        conn.close()


def get_user_permissions(user_id: int):
    conn = get_conn()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT role, can_delete_records, can_grant_delete
                    FROM users WHERE id = %s
                """, (user_id,))
                return cur.fetchone() or {}
    except Exception:
        logger.exception(f"Error reading permissions for user {user_id}")
        return {}
    finally:
        conn.close()


def user_can_manage_delete(user_id: int) -> bool:
    perms = get_user_permissions(user_id)
    role = (perms.get("role") or "").lower()
    if role in ("ceo", "admin"):
        return True
    return bool(perms.get("can_grant_delete"))


def user_can_delete(user_id: int) -> bool:
    perms = get_user_permissions(user_id)
    role = (perms.get("role") or "").lower()
    return role in ("ceo", "admin") or bool(perms.get("can_delete_records"))


def set_user_delete_permission(granter_user_id: int, target_user_id: int, allowed: bool) -> bool:
    if not user_can_manage_delete(granter_user_id):
        return False
    return set_user_permission(target_user_id, can_delete=allowed)


def delete_candidate_by_actor(candidate_id: str, actor_user_id: int) -> bool:
    if not user_can_delete(actor_user_id):
        logger.warning(f"User {actor_user_id} attempted candidate delete without permission.")
        return False
    return delete_candidate(candidate_id)

# === Candidate Statistics ===

def get_candidate_statistics():
    """
    Collect as many useful statistics as possible for CEO dashboard.
    """
    conn = get_conn()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                stats = {}

                # Total candidates
                cur.execute("SELECT COUNT(*) FROM candidates;")
                stats["total_candidates"] = cur.fetchone()["count"]

                # Candidates created today
                cur.execute("SELECT COUNT(*) FROM candidates WHERE DATE(created_at) = CURRENT_DATE;")
                stats["candidates_today"] = cur.fetchone()["count"]

                # Candidates created this week
                cur.execute("""
                    SELECT COUNT(*) 
                    FROM candidates 
                    WHERE DATE_TRUNC('week', created_at) = DATE_TRUNC('week', CURRENT_DATE);
                """)
                stats["candidates_this_week"] = cur.fetchone()["count"]

                # Candidates created this month
                cur.execute("""
                    SELECT COUNT(*) 
                    FROM candidates 
                    WHERE DATE_TRUNC('month', created_at) = DATE_TRUNC('month', CURRENT_DATE);
                """)
                stats["candidates_this_month"] = cur.fetchone()["count"]

                # With CV
                cur.execute("SELECT COUNT(*) FROM candidates WHERE cv_file IS NOT NULL OR resume_link IS NOT NULL;")
                stats["candidates_with_resume"] = cur.fetchone()["count"]

                # Without CV
                stats["candidates_without_resume"] = stats["total_candidates"] - stats["candidates_with_resume"]

                # Interviews total
                cur.execute("SELECT COUNT(*) FROM interviews;")
                stats["total_interviews"] = cur.fetchone()["count"]

                # Interviews by result
                cur.execute("SELECT result, COUNT(*) FROM interviews GROUP BY result;")
                stats["interview_results"] = {row["result"] or "unspecified": row["count"] for row in cur.fetchall()}

                # Scheduled interviews
                cur.execute("SELECT COUNT(*) FROM interviews WHERE result IS NULL OR result ILIKE 'scheduled';")
                stats["interviews_scheduled"] = cur.fetchone()["count"]

                # Completed interviews
                cur.execute("SELECT COUNT(*) FROM interviews WHERE result IS NOT NULL AND result NOT ILIKE 'scheduled';")
                stats["interviews_completed"] = cur.fetchone()["count"]

                # Interviews this week
                cur.execute("""
                    SELECT COUNT(*) 
                    FROM interviews 
                    WHERE DATE_TRUNC('week', scheduled_at) = DATE_TRUNC('week', CURRENT_DATE);
                """)
                stats["interviews_this_week"] = cur.fetchone()["count"]

                # Pass / Fail breakdown
                cur.execute("SELECT COUNT(*) FROM interviews WHERE result ILIKE 'pass';")
                stats["interviews_passed"] = cur.fetchone()["count"]

                cur.execute("SELECT COUNT(*) FROM interviews WHERE result ILIKE 'fail';")
                stats["interviews_failed"] = cur.fetchone()["count"]

                cur.execute("SELECT COUNT(*) FROM interviews WHERE result ILIKE 'on hold';")
                stats["interviews_on_hold"] = cur.fetchone()["count"]

                # Per interviewer
                cur.execute("SELECT interviewer, COUNT(*) FROM interviews GROUP BY interviewer;")
                stats["per_interviewer"] = {row["interviewer"] or "unknown": row["count"] for row in cur.fetchall()}

                # Per role (based on user role)
                cur.execute("SELECT role, COUNT(*) FROM users GROUP BY role;")
                stats["users_per_role"] = {row["role"]: row["count"] for row in cur.fetchall()}

                # Receptionist stats
                cur.execute("SELECT COUNT(*) FROM receptionist_assessments;")
                stats["total_assessments"] = cur.fetchone()["count"]

                cur.execute(
                    "SELECT AVG(speed_test) AS avg_speed, AVG(accuracy_test) AS avg_accuracy FROM receptionist_assessments;")
                row = cur.fetchone()
                stats["avg_speed_test"] = row["avg_speed"] or 0
                stats["avg_accuracy_test"] = row["avg_accuracy"] or 0


                return stats
    except Exception:
        logger.exception("Error getting candidate statistics")
        return {}
    finally:
        conn.close()