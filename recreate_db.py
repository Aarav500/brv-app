import sqlite3
import os
import sys
import subprocess
import datetime
from pathlib import Path

def main():
    """
    Recreate the users.db database with all required tables and columns.
    This script should be run once to set up the database correctly.
    """
    print("Recreating users.db with all required columns...")
    
    # Ensure data directory exists
    Path("data").mkdir(exist_ok=True)
    Path("data/resumes").mkdir(exist_ok=True)
    
    # Step 1: Run setup_users_db.py to recreate the users table
    print("\nStep 1: Recreating users table...")
    try:
        subprocess.run([sys.executable, "setup_users_db.py"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running setup_users_db.py: {e}")
        return
    
    # Step 2: Create the other required tables
    print("\nStep 2: Creating other required tables...")
    conn = sqlite3.connect('data/brv_applicants.db')
    c = conn.cursor()
    
    # Create candidates table
    print("Creating candidates table...")
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
    
    # Create interviews table
    print("Creating interviews table...")
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
    
    # Create first_interview table
    print("Creating first_interview table...")
    c.execute('''
    CREATE TABLE IF NOT EXISTS first_interview (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_id INTEGER,
        data TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(candidate_id) REFERENCES candidates(id)
    )
    ''')
    
    # Create settings table
    print("Creating settings table...")
    c.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Add default password expiry policy
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("""
    INSERT OR REPLACE INTO settings (key, value, updated_at)
    VALUES (?, ?, ?)
    """, ("password_expiry_days", "30", current_time))
    
    # Step 3: Add additional default users (reception, interview)
    print("\nStep 3: Adding additional default users...")
    
    # Import hash_password function from security module
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from security import hash_password
    
    # Check if reception and interview users already exist
    c.execute("SELECT COUNT(*) FROM users WHERE username IN ('reception', 'interview')")
    if c.fetchone()[0] < 2:
        print("Adding reception and interview users...")
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Add default users with salted passwords
        default_users = []
        for username, password, role in [
            ("reception", "123", "receptionist"),
            ("interview", "234", "interviewer")
        ]:
            # Generate salted password
            hashed_password, salt = hash_password(password)
            
            # Check if user already exists
            c.execute("SELECT COUNT(*) FROM users WHERE username = ?", (username,))
            if c.fetchone()[0] == 0:
                c.execute("""
                    INSERT INTO users (username, password, role, salt, created, last_password_change, force_password_reset)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (username, hashed_password, role, salt, current_time, current_time, 1))
                print(f"Added user: {username}")
            else:
                print(f"User {username} already exists.")
    else:
        print("Reception and interview users already exist.")
    
    conn.commit()
    conn.close()
    
    print("\n✅ Database recreation complete!")
    print("The database now has all required tables and columns.")
    print("You can log in with the following credentials:")
    print("   Username: ceo")
    print("   Password: admin123")

if __name__ == "__main__":
    main()