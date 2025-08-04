import sqlite3
import os
import uuid
import json
from datetime import datetime
from pathlib import Path
from utils import VALID_ROLES

# Ensure DB and resume folder exist
Path("data").mkdir(exist_ok=True)
Path("data/resumes").mkdir(exist_ok=True)

# Database setup
def create_or_update_interviews_table():
    conn = sqlite3.connect('data/brv_applicants.db')
    c = conn.cursor()

    # Create or alter the interviews table
    c.execute("""
    CREATE TABLE IF NOT EXISTS interviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_id INTEGER,
        interviewer_id TEXT,
        interviewer_name TEXT,
        scheduled_time TEXT,
        feedback TEXT,
        status TEXT DEFAULT 'scheduled',
        result TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(candidate_id) REFERENCES candidates(id)
    )
    """)
    conn.commit()
    conn.close()

# Use with caution – check if column exists before altering
def alter_users_table_if_needed():
    conn = sqlite3.connect('data/brv_applicants.db')
    c = conn.cursor()

    # Try to add missing columns one by one
    try:
        c.execute("ALTER TABLE users ADD COLUMN force_password_reset BOOLEAN DEFAULT 1")
    except sqlite3.OperationalError:
        pass  # Column already exists

    try:
        c.execute("ALTER TABLE users ADD COLUMN last_password_change TIMESTAMP")
    except sqlite3.OperationalError:
        pass

    try:
        c.execute("ALTER TABLE users ADD COLUMN salt BLOB")
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Add columns for OTP functionality
    try:
        c.execute("ALTER TABLE users ADD COLUMN otp TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists

    try:
        c.execute("ALTER TABLE users ADD COLUMN otp_expiry TIMESTAMP")
    except sqlite3.OperationalError:
        pass  # Column already exists

    try:
        c.execute("ALTER TABLE users ADD COLUMN otp_attempts INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Rename username column to email if it hasn't been done already
    try:
        # Check if email column exists
        c.execute("SELECT email FROM users LIMIT 1")
    except sqlite3.OperationalError:
        # Email column doesn't exist, so rename username to email
        try:
            c.execute("ALTER TABLE users RENAME COLUMN username TO email")
        except sqlite3.OperationalError:
            pass  # Either the rename failed or the column is already named email

    conn.commit()
    conn.close()

def alter_candidates_table_if_needed():
    conn = sqlite3.connect('data/brv_applicants.db')
    c = conn.cursor()

    # Try to add resume_link column
    try:
        c.execute("ALTER TABLE candidates ADD COLUMN resume_link TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists

    conn.commit()
    conn.close()

def alter_interviews_table_if_needed():
    conn = sqlite3.connect('data/brv_applicants.db')
    c = conn.cursor()

    # Try to add missing columns one by one
    try:
        c.execute("ALTER TABLE interviews ADD COLUMN candidate_id INTEGER")
    except sqlite3.OperationalError:
        pass  # Column already exists

    try:
        c.execute("ALTER TABLE interviews ADD COLUMN interviewer_id TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        c.execute("ALTER TABLE interviews ADD COLUMN interviewer_name TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        c.execute("ALTER TABLE interviews ADD COLUMN scheduled_time TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        c.execute("ALTER TABLE interviews ADD COLUMN feedback TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        c.execute("ALTER TABLE interviews ADD COLUMN status TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        c.execute("ALTER TABLE interviews ADD COLUMN result TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        c.execute("ALTER TABLE interviews ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    except sqlite3.OperationalError:
        pass

    try:
        c.execute("ALTER TABLE interviews ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

def init_db():
    conn = sqlite3.connect('data/brv_applicants.db')
    c = conn.cursor()

    # Create users table
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Create candidates table
    c.execute('''
    CREATE TABLE IF NOT EXISTS candidates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT,
        phone TEXT,
        address TEXT,
        form_data TEXT,        -- Data from QR Form (later)
        hr_data TEXT,          -- Data from receptionist
        resume_path TEXT,
        status TEXT DEFAULT 'Pending'
    )
    ''')

    # Create or update interviews table
    create_or_update_interviews_table()
    alter_interviews_table_if_needed()

    # Update users table if needed
    alter_users_table_if_needed()

    # Update candidates table if needed
    alter_candidates_table_if_needed()

    # Create first_interview table
    c.execute('''
    CREATE TABLE IF NOT EXISTS first_interview (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_id INTEGER,
        data TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(candidate_id) REFERENCES candidates(id)
    )
    ''')

    conn.commit()
    conn.close()

def init_users():
    conn = sqlite3.connect('data/brv_applicants.db')
    c = conn.cursor()

    # Check if default users already exist
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        print("Adding default users...")
        # Get current timestamp for last_password_change
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Import hash_password function from security module
        from security import hash_password

        # Add default users with salted passwords
        default_users = []
        for email, password, role in [
            ("reception@bluematrixit.com", "123", "receptionist"),
            ("interview@bluematrixit.com", "234", "interviewer"),
            ("nikhil.shah@bluematrixit.com", "345", "ceo")
        ]:
            # Generate salted password
            hashed_password, salt = hash_password(password)
            default_users.append((str(uuid.uuid4()), email, hashed_password, role, 1, current_time, salt))

        c.executemany("INSERT INTO users (id, email, password, role, force_password_reset, last_password_change, salt) VALUES (?, ?, ?, ?, ?, ?, ?)", default_users)
        print("Default users added successfully!")
    else:
        print("Default users already exist.")

    conn.commit()
    conn.close()

# Helper functions for candidates
def add_candidate(hr_data, form_data=None):
    # Save resume if uploaded
    resume_path = None
    resume_link = None

    # Handle resume file upload
    if 'resume' in hr_data and hr_data['resume']:
        resume_file = hr_data['resume']
        # Create a unique ID for the resume
        resume_id = str(uuid.uuid4())
        # Get the file extension
        if hasattr(resume_file, 'name'):
            extension = resume_file.name.split('.')[-1]
            resume_filename = f"{resume_id}.{extension}"
            resume_path = f"data/resumes/{resume_filename}"

            # Save the file
            with open(resume_path, "wb") as f:
                f.write(resume_file.getbuffer())

        # Remove the file object from hr_data before JSON serialization
        del hr_data['resume']
        # Add the path instead
        hr_data['resume_path'] = resume_path

    # Handle resume link
    if 'resume_link' in hr_data and hr_data['resume_link']:
        resume_link = hr_data['resume_link']

    # Convert hr_data to JSON
    hr_json = json.dumps(hr_data)

    # Convert form_data to JSON if provided
    form_json = json.dumps(form_data) if form_data else None

    # Save to database
    conn = sqlite3.connect('data/brv_applicants.db')
    c = conn.cursor()

    # Extract basic fields if available
    name = hr_data.get('name', '')
    email = hr_data.get('email', '')
    phone = hr_data.get('phone', '')
    address = hr_data.get('address', '')

    c.execute(
        "INSERT INTO candidates (name, email, phone, address, form_data, hr_data, resume_path, resume_link) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (name, email, phone, address, form_json, hr_json, resume_path, resume_link)
    )

    candidate_id = c.lastrowid
    conn.commit()
    conn.close()

    return candidate_id

def get_candidates(status=None):
    conn = sqlite3.connect('data/brv_applicants.db')
    c = conn.cursor()

    if status:
        query = "SELECT * FROM candidates WHERE status = ? ORDER BY id DESC"
        c.execute(query, (status,))
    else:
        query = "SELECT * FROM candidates ORDER BY id DESC"
        c.execute(query)

    candidates = c.fetchall()
    conn.close()
    return candidates

def get_all_candidates():
    conn = sqlite3.connect('data/brv_applicants.db')
    c = conn.cursor()
    c.execute("SELECT id, form_data, hr_data, resume_path, resume_link FROM candidates")
    rows = c.fetchall()
    conn.close()
    return [{"id": row[0], 
             "form_data": json.loads(row[1]) if row[1] else {}, 
             "hr_data": json.loads(row[2]) if row[2] else {},
             "resume_path": row[3],
             "resume_link": row[4]} for row in rows]

def update_candidate(candidate_id, status=None, hr_data=None, resume_link=None):
    conn = sqlite3.connect('data/brv_applicants.db')
    c = conn.cursor()

    if status and hr_data and resume_link:
        hr_json = json.dumps(hr_data)
        c.execute(
            "UPDATE candidates SET status = ?, hr_data = ?, resume_link = ? WHERE id = ?",
            (status, hr_json, resume_link, candidate_id)
        )
    elif status and hr_data:
        hr_json = json.dumps(hr_data)
        c.execute(
            "UPDATE candidates SET status = ?, hr_data = ? WHERE id = ?",
            (status, hr_json, candidate_id)
        )
    elif status and resume_link:
        c.execute(
            "UPDATE candidates SET status = ?, resume_link = ? WHERE id = ?",
            (status, resume_link, candidate_id)
        )
    elif hr_data and resume_link:
        hr_json = json.dumps(hr_data)
        c.execute(
            "UPDATE candidates SET hr_data = ?, resume_link = ? WHERE id = ?",
            (hr_json, resume_link, candidate_id)
        )
    elif status:
        c.execute(
            "UPDATE candidates SET status = ? WHERE id = ?",
            (status, candidate_id)
        )
    elif hr_data:
        hr_json = json.dumps(hr_data)
        c.execute(
            "UPDATE candidates SET hr_data = ? WHERE id = ?",
            (hr_json, candidate_id)
        )
    elif resume_link:
        c.execute(
            "UPDATE candidates SET resume_link = ? WHERE id = ?",
            (resume_link, candidate_id)
        )

    conn.commit()
    conn.close()

# Helper functions for interviews
def add_interview(candidate_id, interviewer_id, scheduled_time, notes=None):
    conn = sqlite3.connect('data/brv_applicants.db')
    c = conn.cursor()

    # Get interviewer name
    c.execute("SELECT email FROM users WHERE id = ?", (interviewer_id,))
    interviewer_name = c.fetchone()[0]

    c.execute(
        """
        INSERT INTO interviews 
        (candidate_id, interviewer_id, interviewer_name, scheduled_time, feedback, status) 
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (candidate_id, interviewer_id, interviewer_name, scheduled_time, notes, "scheduled")
    )

    interview_id = c.lastrowid

    # Update candidate status
    c.execute(
        "UPDATE candidates SET status = 'Interview Scheduled' WHERE id = ?",
        (candidate_id,)
    )

    conn.commit()
    conn.close()

    return interview_id

def save_interview_feedback(candidate_id, interviewer_name, feedback, result):
    conn = sqlite3.connect('data/brv_applicants.db')
    c = conn.cursor()

    c.execute("INSERT INTO interviews (candidate_id, interviewer_name, feedback, result, status) VALUES (?, ?, ?, ?, ?)",
              (candidate_id, interviewer_name, feedback, result, result))

    # Update candidate status in main table
    c.execute("UPDATE candidates SET status = ? WHERE id = ?", (result, candidate_id))
    conn.commit()
    conn.close()

def save_first_interview_feedback(candidate_id, feedback_data):
    conn = sqlite3.connect('data/brv_applicants.db')
    c = conn.cursor()
    c.execute("""
        INSERT INTO first_interview (candidate_id, data)
        VALUES (?, ?)
    """, (candidate_id, json.dumps(feedback_data)))
    conn.commit()
    conn.close()

# Get full candidate data with joined interview info
def get_candidate_stats():
    conn = sqlite3.connect('data/brv_applicants.db')
    c = conn.cursor()
    c.execute("""
        SELECT c.id, c.form_data, c.hr_data, c.resume_path, c.status,
               i.interviewer_name, i.feedback, i.result
        FROM candidates c
        LEFT JOIN interviews i ON c.id = i.candidate_id
    """)
    rows = c.fetchall()
    conn.close()

    result = []
    for row in rows:
        form_data = json.loads(row[1]) if row[1] else {}
        hr_data = json.loads(row[2]) if row[2] else {}
        result.append({
            "id": row[0],
            "form_data": form_data,
            "hr_data": hr_data,
            "resume_path": row[3],
            "status": row[4],
            "interviewer_name": row[5],
            "feedback": row[6],
            "result": row[7]
        })
    return result

# User management functions
def get_all_users():
    """Get all users from the database"""
    conn = sqlite3.connect('data/brv_applicants.db')
    c = conn.cursor()
    c.execute("SELECT id, email, role, force_password_reset, last_password_change FROM users")
    rows = c.fetchall()
    conn.close()

    users = []
    for row in rows:
        users.append({
            "id": row[0],
            "email": row[1],
            "username": row[1],  # Add username key that maps to email
            "role": row[2],
            "force_password_reset": row[3],
            "last_password_change": row[4]
        })
    return users

def add_user(email, password, role):
    """Add a new user to the database"""
    conn = sqlite3.connect('data/brv_applicants.db')
    c = conn.cursor()

    # Standardize role to lowercase
    role = role.lower()

    # Validate role against VALID_ROLES
    if role not in VALID_ROLES:
        conn.close()
        return False, f"Invalid role: {role}. Valid roles are: {', '.join(VALID_ROLES)}"

    # Validate email format using regex
    import re
    email_regex = r"[^@]+@[^@]+\.[^@]+"
    if not re.match(email_regex, email):
        conn.close()
        return False, "Username must be a valid email format (e.g., john.doe@company.com)"

    # Validate email domain
    if not email.endswith("@bluematrixit.com"):
        conn.close()
        return False, "Only official Bluematrix emails are allowed"

    # Check if email already exists
    c.execute("SELECT COUNT(*) FROM users WHERE email = ?", (email,))
    if c.fetchone()[0] > 0:
        conn.close()
        return False, "Email already exists"

    # Import hash_password function from security module
    from security import hash_password

    # Generate salted password
    hashed_password, salt = hash_password(password)

    # Add the user
    user_id = str(uuid.uuid4())
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute(
        "INSERT INTO users (id, email, password, role, force_password_reset, last_password_change, salt) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, email, hashed_password, role, 1, current_time, salt)
    )
    conn.commit()
    conn.close()
    return True, "User added successfully"

def remove_user(user_id):
    """Remove a user from the database"""
    conn = sqlite3.connect('data/brv_applicants.db')
    c = conn.cursor()

    # Check if user exists
    c.execute("SELECT COUNT(*) FROM users WHERE id = ?", (user_id,))
    if c.fetchone()[0] == 0:
        conn.close()
        return False, "User not found"

    # Remove the user
    c.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return True, "User removed successfully"

def reset_user_password(user_id, new_password=None):
    """Reset a user's password and force them to change it on next login"""
    conn = sqlite3.connect('data/brv_applicants.db')
    c = conn.cursor()

    # Check if user exists
    c.execute("SELECT COUNT(*) FROM users WHERE id = ?", (user_id,))
    if c.fetchone()[0] == 0:
        conn.close()
        return False, "User not found"

    # If no new password is provided, use a default one
    if not new_password:
        new_password = "changeme"

    # Import hash_password function from security module
    from security import hash_password

    # Generate salted password
    hashed_password, salt = hash_password(new_password)

    # Reset the password and force a change
    c.execute(
        "UPDATE users SET password = ?, salt = ?, force_password_reset = 1 WHERE id = ?",
        (hashed_password, salt, user_id)
    )
    conn.commit()
    conn.close()
    return True, "Password reset successfully"

def update_user_role(user_id, new_role, new_email=None):
    """Update a user's role and optionally email"""
    conn = sqlite3.connect('data/brv_applicants.db')
    c = conn.cursor()

    # Standardize role to lowercase
    new_role = new_role.lower()

    # Validate role against VALID_ROLES
    if new_role not in VALID_ROLES:
        conn.close()
        return False, f"Invalid role: {new_role}. Valid roles are: {', '.join(VALID_ROLES)}"

    # Check if user exists
    c.execute("SELECT email FROM users WHERE id = ?", (user_id,))
    user_result = c.fetchone()
    if not user_result:
        conn.close()
        return False, "User not found"

    current_email = user_result[0]

    # If new email is provided and different from current email
    if new_email and new_email != current_email:
        # Check if the new email is already in use by another user
        c.execute("SELECT COUNT(*) FROM users WHERE email = ? AND id != ?", (new_email, user_id))
        if c.fetchone()[0] > 0:
            conn.close()
            return False, f"Email {new_email} is already in use by another user"

        # Update both role and email
        c.execute(
            "UPDATE users SET role = ?, email = ? WHERE id = ?",
            (new_role, new_email, user_id)
        )
        conn.commit()
        conn.close()
        return True, "Role and email updated successfully"
    else:
        # Update only the role
        c.execute(
            "UPDATE users SET role = ? WHERE id = ?",
            (new_role, user_id)
        )
        conn.commit()
        conn.close()
        return True, "Role updated successfully"

def update_password_expiry_policy(max_days):
    """
    Update the password expiration policy.

    Args:
        max_days (int): Maximum number of days a password is valid

    Returns:
        tuple: (success, message)
    """
    # Validate input
    try:
        max_days = int(max_days)
        if max_days < 1:
            return False, "Password expiry days must be a positive number"
    except:
        return False, "Invalid input for password expiry days"

    # Store the policy in a settings table
    conn = sqlite3.connect('data/brv_applicants.db')
    c = conn.cursor()

    # Create settings table if it doesn't exist
    c.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Update or insert the password_expiry_days setting
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("""
    INSERT OR REPLACE INTO settings (key, value, updated_at)
    VALUES (?, ?, ?)
    """, ("password_expiry_days", str(max_days), current_time))

    conn.commit()
    conn.close()

    return True, f"Password expiry policy updated to {max_days} days"

def get_password_expiry_policy():
    """
    Get the current password expiration policy.

    Returns:
        int: Maximum number of days a password is valid (default: 30)
    """
    conn = sqlite3.connect('data/brv_applicants.db')
    c = conn.cursor()

    # Create settings table if it doesn't exist
    c.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Get the password_expiry_days setting
    c.execute("SELECT value FROM settings WHERE key = ?", ("password_expiry_days",))
    result = c.fetchone()

    conn.close()

    if result:
        try:
            return int(result[0])
        except:
            return 30  # Default if value is not a valid integer
    else:
        return 30  # Default if setting doesn't exist

# Initialize the database when imported
if __name__ == "__main__":
    print("Initializing database...")
    init_db()
    init_users()
    print("Database initialization complete!")
