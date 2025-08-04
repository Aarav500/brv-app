import sqlite3
import hashlib
import secrets
import datetime

def hash_password(password, salt):
    return hashlib.sha256((password + salt).encode()).hexdigest()

conn = sqlite3.connect("data/brv_applicants.db")
c = conn.cursor()

# Drop and recreate users table
c.execute("DROP TABLE IF EXISTS users")

c.execute("""
    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        salt TEXT,
        created TEXT,
        last_password_change TEXT,
        force_password_reset INTEGER
    )
""")

# Add CEO user
username = "ceo"
password = "admin123"
role = "CEO"
salt = secrets.token_hex(16)
hashed_password = hash_password(password, salt)
now = datetime.datetime.now().isoformat()

c.execute("""
    INSERT INTO users (username, password, role, salt, created, last_password_change, force_password_reset)
    VALUES (?, ?, ?, ?, ?, ?, ?)
""", (username, hashed_password, role, salt, now, now, 0))

conn.commit()
conn.close()

print("✅ Database created with CEO user.")
print("   Username: ceo")
print("   Password: admin123")
