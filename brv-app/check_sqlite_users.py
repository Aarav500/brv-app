import sqlite3
import json

def check_sqlite_users():
    """Check the users table in the SQLite database."""
    try:
        # Connect to the SQLite database
        conn = sqlite3.connect('data/brv_applicants.db')
        cursor = conn.cursor()
        
        # Check if the users table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not cursor.fetchone():
            print("❌ Users table does not exist in the SQLite database.")
            return
        
        # Get the column names of the users table
        cursor.execute("PRAGMA table_info(users)")
        columns = cursor.fetchall()
        print("Users table columns:")
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")
        
        # Get all users
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()
        
        if not users:
            print("❌ No users found in the SQLite database.")
            return
        
        print(f"\nFound {len(users)} users in the SQLite database:")
        
        # Create a list of column names for easier reference
        column_names = [col[1] for col in columns]
        
        # Print each user's details
        for user in users:
            user_dict = {column_names[i]: user[i] for i in range(len(column_names))}
            print("\nUser:")
            for key, value in user_dict.items():
                print(f"  - {key}: {value}")
        
        # Check for specific users
        test_emails = [
            "reception@bluematrixit.com",
            "interview@bluematrixit.com",
            "nikhil.shah@bluematrixit.com"
        ]
        
        print("\nChecking for specific users:")
        for email in test_emails:
            cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
            user = cursor.fetchone()
            if user:
                user_dict = {column_names[i]: user[i] for i in range(len(column_names))}
                print(f"\nFound user with email {email}:")
                for key, value in user_dict.items():
                    print(f"  - {key}: {value}")
            else:
                print(f"❌ User with email {email} not found.")
        
        conn.close()
    
    except Exception as e:
        print(f"Error checking SQLite users: {e}")

if __name__ == "__main__":
    check_sqlite_users()