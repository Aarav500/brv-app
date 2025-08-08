import sys
import os

# Add the current directory to the path so we can import modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from user_auth import create_user, get_user_by_email

def add_oracle_test_candidate():
    """
    Add a test candidate user to the Oracle database.
    
    Username: candidate@example.com
    Email: candidate@example.com
    Password: password123
    Role: candidate
    """
    # Check if the user already exists
    existing_user = get_user_by_email("candidate@example.com")
    if existing_user:
        print("Test candidate user already exists in Oracle DB.")
        return
    
    # Create the user
    success, user_id, message = create_user("candidate", "candidate@example.com", "password123", "candidate")
    if success:
        print(f"Test candidate user created successfully in Oracle DB with ID: {user_id}")
        print(f"Message: {message}")
    else:
        print(f"Failed to create test candidate user in Oracle DB: {message}")

if __name__ == "__main__":
    add_oracle_test_candidate()