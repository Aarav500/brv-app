import sqlite3
import os
from security import hash_password

def add_salt_column():
    """
    Add a salt column to the users table and generate salts for existing users.
    """
    print("Adding salt column to users table...")
    
    # Connect to the database
    conn = sqlite3.connect('data/brv_applicants.db')
    c = conn.cursor()
    
    # Check if salt column exists, add it if it doesn't
    try:
        c.execute("SELECT salt FROM users LIMIT 1")
        print("Salt column already exists.")
    except sqlite3.OperationalError:
        print("Adding salt column...")
        c.execute("ALTER TABLE users ADD COLUMN salt BLOB")
        print("Salt column added successfully.")
    
    # Get all users without salts
    c.execute("SELECT id, username, password FROM users WHERE salt IS NULL")
    users_without_salt = c.fetchall()
    
    if not users_without_salt:
        print("All users already have salts.")
    else:
        print(f"Found {len(users_without_salt)} users without salts. Generating salts...")
        
        # Generate salts and update passwords for each user
        for user_id, username, password in users_without_salt:
            # Generate a new salt and hash the password
            hashed_password, salt = hash_password(password)
            
            # Update the user record with the new salt and hashed password
            c.execute(
                "UPDATE users SET password = ?, salt = ? WHERE id = ?",
                (hashed_password, salt, user_id)
            )
            print(f"Updated user: {username}")
    
    # Commit changes and close connection
    conn.commit()
    conn.close()
    
    print("Salt column update complete!")

if __name__ == "__main__":
    add_salt_column()