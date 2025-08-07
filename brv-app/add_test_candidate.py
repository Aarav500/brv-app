import sys
import os

# Add the current directory to the path so we can import modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mysql_db import create_user, get_user_by_email

def add_test_candidate():
    """
    Add a test candidate user to the database.
    
    Username: candidate@example.com
    Password: password123
    Role: candidate
    """
    # Check if the user already exists
    existing_user = get_user_by_email("candidate@example.com")
    if existing_user:
        print("Test candidate user already exists.")
        return
    
    # Create the user
    user_id = create_user("candidate@example.com", "password123", "candidate")
    if user_id:
        print(f"Test candidate user created successfully with ID: {user_id}")
    else:
        print("Failed to create test candidate user.")

if __name__ == "__main__":
    add_test_candidate()