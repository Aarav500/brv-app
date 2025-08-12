# db_postgres.py
import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import bcrypt

DATABASE_URL = os.getenv("DATABASE_URL")  # postgres://user:pass@host:5432/dbname

def get_conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL env var not set")
    return psycopg2.connect(DATABASE_URL, sslmode=os.getenv("PGSSLMODE", "require"))

def init_db():
    sql = """
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT now()
    );
    CREATE TABLE IF NOT EXISTS candidates (
        id SERIAL PRIMARY KEY,
        candidate_id TEXT UNIQUE NOT NULL,
        name TEXT,
        email TEXT,
        phone TEXT,
        form_data JSONB,
        resume_link TEXT,
        created_by TEXT,
        can_edit BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT now(),
        updated_at TIMESTAMP DEFAULT now()
    );
    CREATE TABLE IF NOT EXISTS roles (
        role_name TEXT PRIMARY KEY,
        description TEXT
    );
    """
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute(sql)
    conn.close()

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())

def seed_sample_users():
    sample_users = [
        ("admin@bluematrixit.com", "password123", "admin"),
        ("ceo@bluematrixit.com", "password123", "ceo"),
        ("receptionist@bluematrixit.com", "password123", "receptionist"),
        ("interviewer@bluematrixit.com", "password123", "interviewer"),
        ("candidate@example.com", "password123", "candidate")
    ]
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            for email, pwd, role in sample_users:
                cur.execute("SELECT id FROM users WHERE email=%s", (email,))
                if cur.fetchone():
                    continue
                h = hash_password(pwd)
                cur.execute("INSERT INTO users (email, password_hash, role) VALUES (%s,%s,%s)",
                            (email, h, role))
    conn.close()

# CRUD for candidates
def create_candidate_in_db(candidate_id: str, name: str, email: str, phone: str, form_data: dict, created_by: str):
    conn = get_conn()
    with conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO candidates (candidate_id, name, email, phone, form_data, created_by)
                VALUES (%s,%s,%s,%s,%s,%s)
                RETURNING *;
            """, (candidate_id, name, email, phone, json.dumps(form_data), created_by))
            res = cur.fetchone()
    conn.close()
    return res

def update_candidate_resume_link(candidate_id: str, resume_link: str):
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE candidates SET resume_link=%s, updated_at=now() WHERE candidate_id=%s
            """, (resume_link, candidate_id))
            return cur.rowcount > 0

def get_candidate_by_id(candidate_id):
    conn = get_conn()
    with conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM candidates WHERE candidate_id=%s", (candidate_id,))
            r = cur.fetchone()
    conn.close()
    return r

def find_candidates_by_name(name_query: str):
    conn = get_conn()
    with conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM candidates WHERE LOWER(name) LIKE LOWER(%s)", (f"%{name_query}%",))
            results = cur.fetchall()
    conn.close()
    return results

def set_candidate_permission(candidate_id: str, can_edit: bool):
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE candidates SET can_edit=%s, updated_at=now() WHERE candidate_id=%s
            """, (can_edit, candidate_id))
            return cur.rowcount > 0

def update_candidate_form_data(candidate_id: str, form_data: dict):
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE candidates SET form_data=%s, updated_at=now() WHERE candidate_id=%s AND can_edit=true
            """, (json.dumps(form_data), candidate_id))
            return cur.rowcount > 0

def get_all_candidates():
    conn = get_conn()
    with conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM candidates ORDER BY updated_at DESC")
            r = cur.fetchall()
    conn.close()
    return r

# Users
def get_user_by_email(email):
    conn = get_conn()
    with conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id,email,role,password_hash FROM users WHERE email=%s", (email,))
            r = cur.fetchone()
    conn.close()
    return r

def update_user_role(user_email, new_role):
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET role=%s WHERE email=%s", (new_role, user_email))
            return cur.rowcount > 0

def update_user_password(user_email, new_password):
    h = hash_password(new_password)
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET password_hash=%s WHERE email=%s", (h, user_email))
            return cur.rowcount > 0
