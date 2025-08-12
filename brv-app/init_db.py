import asyncio
import uuid
from datetime import datetime
import asyncpg
from env_config import get_credentials

async def get_connection():
    creds = get_credentials()
    return await asyncpg.connect(
        host=creds["host"],
        port=creds["port"],
        user=creds["user"],
        password=creds["password"],
        database=creds["database"]
    )

async def create_users_table(conn):
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id UUID PRIMARY KEY,
            username TEXT UNIQUE,
            email TEXT UNIQUE,
            password_hash TEXT,
            role TEXT,
            last_password_change TIMESTAMP,
            force_password_reset BOOLEAN
        )
    """)
    print("✅ Users table created or already exists")

async def create_candidates_table(conn):
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS candidates (
            candidate_id UUID PRIMARY KEY,
            full_name TEXT,
            email TEXT,
            phone TEXT,
            additional_phone TEXT,
            dob DATE,
            caste TEXT,
            sub_caste TEXT,
            marital_status TEXT,
            qualification TEXT,
            work_experience TEXT,
            referral TEXT,
            resume_link TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            interview_status TEXT
        )
    """)
    print("✅ Candidates table created or already exists")

async def create_interviews_table(conn):
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS interviews (
            interview_id UUID PRIMARY KEY,
            candidate_id UUID REFERENCES candidates(candidate_id),
            interviewer_id UUID REFERENCES users(user_id),
            scheduled_time TIMESTAMP,
            feedback TEXT,
            status TEXT,
            result TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("✅ Interviews table created or already exists")

async def create_settings_table(conn):
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("✅ Settings table created or already exists")

async def create_activity_log_table(conn):
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            log_id UUID PRIMARY KEY,
            user_id UUID REFERENCES users(user_id),
            action TEXT,
            details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("✅ Activity log table created or already exists")

async def create_resumes_metadata_table(conn):
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS resumes_metadata (
            resume_id UUID PRIMARY KEY,
            candidate_id UUID REFERENCES candidates(candidate_id),
            filename TEXT,
            file_size BIGINT,
            mime_type TEXT,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resume_link TEXT
        )
    """)
    print("✅ Resumes metadata table created or already exists")

async def add_default_settings(conn):
    defaults = [
        ("password_expiry_days", "30"),
        ("storage_threshold_percent", "90")
    ]
    for key, value in defaults:
        await conn.execute("""
            INSERT INTO settings (key, value, updated_at)
            VALUES ($1, $2, CURRENT_TIMESTAMP)
            ON CONFLICT (key)
            DO UPDATE SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP
        """, key, value)
    print("✅ Default settings added/updated")

async def add_default_users(conn):
    count = await conn.fetchval("SELECT COUNT(*) FROM users")
    if count == 0:
        from user_auth import hash_password
        now = datetime.now()
        default_users = [
            ("ceo", "ceo@bluematrixit.com", "password123", "ceo", False),
            ("interviewer", "interviewer@bluematrixit.com", "password123", "interviewer", True),
            ("receptionist", "receptionist@bluematrixit.com", "password123", "receptionist", True),
            ("candidate", "candidate@example.com", "password123", "candidate", False)
        ]
        for username, email, password, role, force_reset in default_users:
            password_hash, _ = hash_password(password)
            await conn.execute("""
                INSERT INTO users (
                    user_id, username, email, password_hash, role, last_password_change, force_password_reset
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            """, uuid.uuid4(), username, email, password_hash, role, now, force_reset)
        print(f"✅ Added {len(default_users)} default users")
    else:
        print("✅ Users already exist in the database")

async def initialize_database():
    print("\n🔄 Initializing PostgreSQL database...")
    conn = await get_connection()

    await create_users_table(conn)
    await create_candidates_table(conn)
    await create_interviews_table(conn)
    await create_settings_table(conn)
    await create_activity_log_table(conn)
    await create_resumes_metadata_table(conn)

    await add_default_settings(conn)
    await add_default_users(conn)

    await conn.close()
    print("\n✅ Database initialization complete!")

if __name__ == "__main__":
    asyncio.run(initialize_database())
