import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import oracle_db module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from oracle_db import execute_query

def add_candidate_user_direct():
    """
    Directly add the candidate@example.com user to the Oracle database.
    
    Username: candidate
    Email: candidate@example.com
    Password: password123 (hashed)
    Role: candidate
    """
    # Generate a UUID for the user
    import uuid
    user_id = str(uuid.uuid4())
    
    # Hash the password
    import bcrypt
    password = "password123"
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    password_hash = bcrypt.hashpw(password_bytes, salt).decode('utf-8')
    
    # Current timestamp
    from datetime import datetime
    now = datetime.now().isoformat()
    
    # Force password reset for new users (except CEO)
    force_reset = 1
    
    # SQL query to insert the user
    query = """
    INSERT INTO users (
        user_id, 
        username, 
        email, 
        password_hash, 
        role, 
        last_password_change,
        force_password_reset
    ) VALUES (
        :user_id, 
        :username, 
        :email, 
        :password_hash, 
        :role, 
        :last_password_change,
        :force_password_reset
    )
    """
    
    # Parameters for the query
    params = {
        "user_id": user_id,
        "username": "candidate",
        "email": "candidate@example.com",
        "password_hash": password_hash,
        "role": "candidate",
        "last_password_change": now,
        "force_password_reset": force_reset
    }
    
    # Execute the query
    try:
        result = execute_query(query, params, commit=True)
        if result is not None:
            print(f"User candidate@example.com created successfully with ID: {user_id}")
        else:
            print("Failed to create user candidate@example.com")
    except Exception as e:
        print(f"Error creating user: {e}")

if __name__ == "__main__":
    add_candidate_user_direct()