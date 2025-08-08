#!/usr/bin/env python3
"""
Seed script to create test user accounts in the Oracle database.
This script creates the following test accounts:
- ceo@bluematrixit.com / password123 / role=ceo
- interviewer@bluematrixit.com / password123 / role=interviewer
- receptionist@bluematrixit.com / password123 / role=receptionist
- candidate@example.com / password123 / role=candidate
"""

import os
import sys
from dotenv import load_dotenv

# Add the parent directory to the path so we can import from the brv-app package
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the necessary functions from user_auth.py
from user_auth import create_user, get_user_by_email

# Load environment variables from .env file
load_dotenv()

def seed_test_users():
    """
    Seed the Oracle database with test user accounts.
    """
    # Define the test accounts
    test_accounts = [
        {
            "username": "ceo",
            "email": "ceo@bluematrixit.com",
            "password": "password123",
            "role": "ceo"
        },
        {
            "username": "interviewer",
            "email": "interviewer@bluematrixit.com",
            "password": "password123",
            "role": "interviewer"
        },
        {
            "username": "receptionist",
            "email": "receptionist@bluematrixit.com",
            "password": "password123",
            "role": "receptionist"
        },
        {
            "username": "candidate",
            "email": "candidate@example.com",
            "password": "password123",
            "role": "candidate"
        }
    ]
    
    # Insert each test account
    for account in test_accounts:
        # Check if the user already exists
        existing_user = get_user_by_email(account["email"])
        if existing_user:
            print(f"User {account['email']} already exists, skipping...")
            continue
        
        # Create the user
        success, user_id, message = create_user(
            username=account["username"],
            email=account["email"],
            password=account["password"],
            role=account["role"]
        )
        
        if success:
            print(f"Created user {account['email']} with role {account['role']}")
        else:
            print(f"Failed to create user {account['email']}: {message}")

if __name__ == "__main__":
    print("Seeding test users in Oracle database...")
    seed_test_users()
    print("Done!")