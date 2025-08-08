import sys
import os

# Add the current directory to the path so we can import modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from user_auth import authenticate_user, get_user_by_email

def test_candidate_authentication():
    """
    Test authentication with the candidate@example.com user.
    """
    print("\n🔄 Testing authentication for candidate@example.com...")
    
    # First check if the user exists
    user = get_user_by_email("candidate@example.com")
    if user:
        print("✅ User candidate@example.com exists in the database.")
        print(f"   Username: {user.get('username')}")
        print(f"   Role: {user.get('role')}")
    else:
        print("❌ User candidate@example.com does not exist in the database.")
        print("   Please run init_db.py to initialize the database with default users.")
        return
    
    # Test authentication
    success, user_data, message = authenticate_user("candidate@example.com", "password123")
    
    if success:
        print("✅ Authentication successful!")
        print(f"   Message: {message}")
        print(f"   User data: {user_data}")
    else:
        print("❌ Authentication failed!")
        print(f"   Message: {message}")

if __name__ == "__main__":
    test_candidate_authentication()