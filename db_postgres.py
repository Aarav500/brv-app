# db_postgres.py
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
    """Initialize database tables"""
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                # Create users table
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
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                                );
                            """)

                # Create candidates table
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

                # Create interviews table
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
                            ) NOT NULL,
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
                                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                FOREIGN KEY
                            (
                                candidate_id
                            ) REFERENCES candidates
                            (
                                candidate_id
                            )
                                );
                            """)

                # Create indexes for better performance
                cur.execute("""
                            CREATE INDEX IF NOT EXISTS idx_candidates_name ON candidates(name);
                            CREATE INDEX IF NOT EXISTS idx_candidates_email ON candidates(email);
                            CREATE INDEX IF NOT EXISTS idx_interviews_candidate_id ON interviews(candidate_id);
                            """)

        logger.info("Database tables initialized successfully")
    except Exception as e:
        logger.exception("Failed to initialize database")
        raise
    finally:
        conn.close()


def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash"""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False


# User management functions
def get_user_by_email(email: str):
    """Get user by email"""
    conn = get_conn()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM users WHERE email = %s", (email,))
                return cur.fetchone()
    except Exception as e:
        logger.exception(f"Error getting user by email: {email}")
        return None
    finally:
        conn.close()


def get_user_by_id(user_id: int):
    """Get user by ID"""
    conn = get_conn()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
                return cur.fetchone()
    except Exception as e:
        logger.exception(f"Error getting user by ID: {user_id}")
        return None
    finally:
        conn.close()


def update_user_role(email: str, new_role: str) -> bool:
    """Update user role"""
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET role = %s, updated_at = CURRENT_TIMESTAMP WHERE email = %s",
                    (new_role, email)
                )
                return cur.rowcount > 0
    except Exception as e:
        logger.exception(f"Error updating user role for {email}")
        return False
    finally:
        conn.close()


def update_user_password(email: str, new_password: str) -> bool:
    """Update user password"""
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
    except Exception as e:
        logger.exception(f"Error updating password for {email}")
        return False
    finally:
        conn.close()


# Candidate management functions
def create_candidate_in_db(candidate_id: str, name: str, email: str, phone: str, form_data: dict, created_by: str):
    """Create new candidate in database"""
    conn = get_conn()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                            INSERT INTO candidates (candidate_id, name, email, phone, form_data, created_by, can_edit)
                            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *;
                            """, (candidate_id, name, email, phone, Json(form_data), created_by, False))
                return cur.fetchone()
    except psycopg2.errors.UniqueViolation:
        logger.warning(f"Candidate ID {candidate_id} already exists")
        return None
    except Exception as e:
        logger.exception(f"Error creating candidate {candidate_id}")
        return None
    finally:
        conn.close()


def get_candidate_by_id(candidate_id: str):
    """Get candidate by candidate_id"""
    conn = get_conn()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM candidates WHERE candidate_id = %s", (candidate_id,))
                return cur.fetchone()
    except Exception as e:
        logger.exception(f"Error getting candidate {candidate_id}")
        return None
    finally:
        conn.close()


def get_all_candidates():
    """Get all candidates"""
    conn = get_conn()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM candidates ORDER BY created_at DESC")
                return cur.fetchall()
    except Exception as e:
        logger.exception("Error getting all candidates")
        return []
    finally:
        conn.close()


def find_candidates_by_name(name: str):
    """Find candidates by name (partial match)"""
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
    except Exception as e:
        logger.exception(f"Error finding candidates by name: {name}")
        return []
    finally:
        conn.close()


def update_candidate_form_data(candidate_id: str, form_data: dict) -> bool:
    """Update candidate form data"""
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
    except Exception as e:
        logger.exception(f"Error updating form data for candidate {candidate_id}")
        return False
    finally:
        conn.close()


def update_candidate_resume_link(candidate_id: str, resume_link: str) -> bool:
    """Update candidate resume link"""
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
    except Exception as e:
        logger.exception(f"Error updating resume link for candidate {candidate_id}")
        return False
    finally:
        conn.close()


def set_candidate_permission(candidate_id: str, can_edit: bool) -> bool:
    """Set candidate edit permission"""
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
    except Exception as e:
        logger.exception(f"Error setting permission for candidate {candidate_id}")
        return False
    finally:
        conn.close()


# Interview management functions
def create_interview(candidate_id: str, scheduled_at: datetime, interviewer: str, result: str = None,
                     notes: str = None):
    """Create new interview record"""
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                            INSERT INTO interviews (candidate_id, scheduled_at, interviewer, result, notes)
                            VALUES (%s, %s, %s, %s, %s) RETURNING id;
                            """, (candidate_id, scheduled_at, interviewer, result, notes))
                return cur.fetchone()[0]
    except Exception as e:
        logger.exception(f"Error creating interview for candidate {candidate_id}")
        return None
    finally:
        conn.close()


def get_interviews_for_candidate(candidate_id: str):
    """Get all interviews for a candidate"""
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
    except Exception as e:
        logger.exception(f"Error getting interviews for candidate {candidate_id}")
        return []
    finally:
        conn.close()


def get_all_interviews():
    """Get all interviews with candidate info"""
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
    except Exception as e:
        logger.exception("Error getting all interviews")
        return []
    finally:
        conn.close()


def search_candidates_by_name_or_email(query: str):
    """Search candidates by name or email"""
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
    except Exception as e:
        logger.exception(f"Error searching candidates with query: {query}")
        return []
    finally:
        conn.close()


def seed_sample_users():
    """Create sample users for testing"""
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
                    # Check if user already exists
                    cur.execute("SELECT id FROM users WHERE email = %s", (email,))
                    if not cur.fetchone():
                        password_hash = hash_password(password)
                        cur.execute("""
                                    INSERT INTO users (email, password_hash, role)
                                    VALUES (%s, %s, %s)
                                    """, (email, password_hash, role))
                        logger.info(f"Created sample user: {email} with role: {role}")
    except Exception as e:
        logger.exception("Error creating sample users")
    finally:
        conn.close()

def get_all_users():
    """Get all users from the database"""
    conn = get_conn()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM users ORDER BY created_at DESC")
                return cur.fetchall()
    except Exception as e:
        logger.exception("Error getting all users")
        return []
    finally:
        conn.close()



# Statistics functions for CEO dashboard
def get_candidate_statistics():
    """Get candidate statistics for CEO dashboard"""
    conn = get_conn()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Total candidates
                cur.execute("SELECT COUNT(*) as total FROM candidates")
                total = cur.fetchone()['total']

                # Candidates with resumes
                cur.execute("SELECT COUNT(*) as with_resume FROM candidates WHERE resume_link IS NOT NULL")
                with_resume = cur.fetchone()['with_resume']

                # Candidates created today
                cur.execute("""
                            SELECT COUNT(*) as today
                            FROM candidates
                            WHERE DATE (created_at) = CURRENT_DATE
                            """)
                today = cur.fetchone()['today']

                # Interview statistics
                cur.execute("SELECT COUNT(*) as total_interviews FROM interviews")
                total_interviews = cur.fetchone()['total_interviews']

                cur.execute("""
                            SELECT COUNT(*) as passed
                            FROM interviews
                            WHERE result = 'pass'
                            """)
                passed = cur.fetchone()['passed']

                cur.execute("""
                            SELECT COUNT(*) as failed
                            FROM interviews
                            WHERE result = 'fail'
                            """)
                failed = cur.fetchone()['failed']

                cur.execute("""
                            SELECT COUNT(*) as pending
                            FROM interviews
                            WHERE result IN ('scheduled', 'completed')
                               OR result IS NULL
                            """)
                pending = cur.fetchone()['pending']

                return {
                    'total_candidates': total,
                    'candidates_with_resume': with_resume,
                    'candidates_today': today,
                    'total_interviews': total_interviews,
                    'interviews_passed': passed,
                    'interviews_failed': failed,
                    'interviews_pending': pending
                }
    except Exception as e:
        logger.exception("Error getting candidate statistics")
        return {}
    finally:
        conn.close()