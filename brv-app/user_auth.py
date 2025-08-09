import bcrypt
import uuid
from datetime import datetime
from typing import Dict, Optional, Tuple, Any

# Import from oracle_db.py
from oracle_db import execute_query, execute_across_all_dbs

def hash_password(password: str) -> Tuple[str, str]:
    """
    Hash a password using bcrypt.
    
    Args:
        password (str): The password to hash
        
    Returns:
        Tuple[str, str]: (password_hash, salt)
    """
    # Generate a salt
    salt = bcrypt.gensalt()
    
    # Hash the password with the salt
    password_hash = bcrypt.hashpw(password.encode('utf-8'), salt)
    
    # Return the hash and salt as strings
    return password_hash.decode('utf-8'), salt.decode('utf-8')

def verify_password(password: str, password_hash: str) -> bool:
    """
    Verify a password against a hash.
    
    Args:
        password (str): The password to verify
        password_hash (str): The stored password hash
        
    Returns:
        bool: True if the password matches the hash, False otherwise
    """
    try:
        # Check if the password matches the hash
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    except Exception as e:
        print(f"❌ Error verifying password: {e}")
        return False

def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """
    Get a user by email.
    
    Args:
        email (str): The user's email
        
    Returns:
        Optional[Dict[str, Any]]: User data or None if not found
    """
    query = """
    SELECT 
        user_id, 
        username, 
        email, 
        password_hash, 
        role, 
        last_password_change,
        force_password_reset
    FROM users 
    WHERE email = :email
    """
    
    return execute_across_all_dbs(query, {"email": email}, fetchone=True)

def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """
    Get a user by username.
    
    Args:
        username (str): The username
        
    Returns:
        Optional[Dict[str, Any]]: User data or None if not found
    """
    query = """
    SELECT 
        user_id, 
        username, 
        email, 
        password_hash, 
        role, 
        last_password_change,
        force_password_reset
    FROM users 
    WHERE username = :username
    """
    
    return execute_across_all_dbs(query, {"username": username}, fetchone=True)

def authenticate_user(username_or_email: str, password: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """
    Authenticate a user with username/email and password.
    
    Args:
        username_or_email (str): The user's username or email
        password (str): The user's password
        
    Returns:
        Tuple[bool, Optional[Dict[str, Any]], str]: (success, user_data, message)
    """
    # Try to get the user by email first
    user = get_user_by_email(username_or_email)
    
    # If not found, try by username
    if not user:
        user = get_user_by_username(username_or_email)
    
    # If still not found, authentication fails
    if not user:
        return False, None, "Invalid username/email or password"
    
    # Verify the password
    if not verify_password(password, user["password_hash"]):
        return False, None, "Invalid username/email or password"
    
    # Don't return the password hash
    if "password_hash" in user:
        del user["password_hash"]
    
    # Check if password reset is required
    if user.get("force_password_reset", 0) == 1:
        return True, user, "Password reset required"
    
    # Check if password has expired
    if user.get("last_password_change"):
        last_change = datetime.fromisoformat(user["last_password_change"].replace('Z', '+00:00'))
        days_since_change = (datetime.now() - last_change).days
        
        # Get password expiry days from settings (default 30)
        expiry_days = 30  # This should come from settings
        
        if days_since_change > expiry_days:
            # Update force_password_reset flag
            update_force_password_reset(user["user_id"], True)
            return True, user, "Password has expired and must be reset"
    
    return True, user, "Authentication successful"

def create_user(username: str, email: str, password: str, role: str) -> Tuple[bool, Optional[str], str]:
    """
    Create a new user.
    
    Args:
        username (str): The username
        email (str): The user's email
        password (str): The user's password
        role (str): The user's role
        
    Returns:
        Tuple[bool, Optional[str], str]: (success, user_id, message)
    """
    # Check if user already exists
    existing_user = get_user_by_email(email)
    if existing_user:
        return False, None, f"User with email {email} already exists"
    
    existing_user = get_user_by_username(username)
    if existing_user:
        return False, None, f"User with username {username} already exists"
    
    # Hash the password
    password_hash, _ = hash_password(password)
    
    # Generate a UUID for the user
    user_id = str(uuid.uuid4())
    
    # Current timestamp
    now = datetime.now().isoformat()
    
    # Force password reset for new users (except CEO)
    force_reset = 1 if role.lower() != "ceo" else 0
    
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
    
    params = {
        "user_id": user_id,
        "username": username,
        "email": email,
        "password_hash": password_hash,
        "role": role,
        "last_password_change": now,
        "force_password_reset": force_reset
    }
    
    result = execute_query(query, params, commit=True)
    
    if result is not None:
        return True, user_id, "User created successfully"
    else:
        return False, None, "Failed to create user"

def update_password(user_id: str, new_password: str) -> Tuple[bool, str]:
    """
    Update a user's password.
    
    Args:
        user_id (str): The ID of the user
        new_password (str): The new password
        
    Returns:
        Tuple[bool, str]: (success, message)
    """
    # Hash the new password
    password_hash, _ = hash_password(new_password)
    
    # Current timestamp
    now = datetime.now().isoformat()
    
    query = """
    UPDATE users 
    SET 
        password_hash = :password_hash, 
        last_password_change = :last_password_change,
        force_password_reset = 0
    WHERE user_id = :user_id
    """
    
    params = {
        "password_hash": password_hash,
        "last_password_change": now,
        "user_id": user_id
    }
    
    result = execute_query(query, params, commit=True)
    
    if result is not None:
        return True, "Password updated successfully"
    else:
        return False, "Failed to update password"

def update_force_password_reset(user_id: str, force_reset: bool) -> bool:
    """
    Update the force_password_reset flag for a user.
    
    Args:
        user_id (str): The ID of the user
        force_reset (bool): Whether to force a password reset
        
    Returns:
        bool: True if successful, False otherwise
    """
    query = """
    UPDATE users 
    SET force_password_reset = :force_reset
    WHERE user_id = :user_id
    """
    
    params = {
        "force_reset": 1 if force_reset else 0,
        "user_id": user_id
    }
    
    result = execute_query(query, params, commit=True)
    
    return result is not None

def force_password_reset_all(exclude_roles=None) -> Tuple[bool, str]:
    """
    Force all users to reset their passwords on next login.
    
    Args:
        exclude_roles (list, optional): Roles to exclude from the reset. Defaults to None.
        
    Returns:
        Tuple[bool, str]: (success, message)
    """
    if exclude_roles is None:
        exclude_roles = []
    
    query = """
    UPDATE users 
    SET force_password_reset = 1
    """
    
    # Add WHERE clause if there are roles to exclude
    if exclude_roles:
        placeholders = ", ".join([f":role{i}" for i in range(len(exclude_roles))])
        query += f" WHERE role NOT IN ({placeholders})"
        
        # Create params dictionary
        params = {f"role{i}": role for i, role in enumerate(exclude_roles)}
    else:
        params = None
    
    result = execute_query(query, params, commit=True)
    
    if result is not None:
        return True, "Password reset forced for all users"
    else:
        return False, "Failed to force password reset"

def get_all_users() -> list:
    """
    Get all users.
    
    Returns:
        list: List of all users
    """
    query = """
    SELECT 
        user_id, 
        username, 
        email, 
        role, 
        last_password_change,
        force_password_reset
    FROM users
    ORDER BY username
    """
    
    return execute_across_all_dbs(query) or []

def delete_user(user_id: str) -> Tuple[bool, str]:
    """
    Delete a user.
    
    Args:
        user_id (str): The ID of the user
        
    Returns:
        Tuple[bool, str]: (success, message)
    """
    query = """
    DELETE FROM users 
    WHERE user_id = :user_id
    """
    
    result = execute_query(query, {"user_id": user_id}, commit=True)
    
    if result is not None:
        return True, "User deleted successfully"
    else:
        return False, "Failed to delete user"

def update_user_role(user_id: str, new_role: str) -> Tuple[bool, str]:
    """
    Update a user's role.
    
    Args:
        user_id (str): The ID of the user
        new_role (str): The new role
        
    Returns:
        Tuple[bool, str]: (success, message)
    """
    query = """
    UPDATE users 
    SET role = :new_role
    WHERE user_id = :user_id
    """
    
    params = {
        "new_role": new_role,
        "user_id": user_id
    }
    
    result = execute_query(query, params, commit=True)
    
    if result is not None:
        return True, f"User role updated to {new_role}"
    else:
        return False, "Failed to update user role"

def update_user_email(user_id: str, new_email: str) -> Tuple[bool, str]:
    """
    Update a user's email.
    
    Args:
        user_id (str): The ID of the user
        new_email (str): The new email
        
    Returns:
        Tuple[bool, str]: (success, message)
    """
    # Check if email is already in use
    existing_user = get_user_by_email(new_email)
    if existing_user and existing_user["user_id"] != user_id:
        return False, f"Email {new_email} is already in use"
    
    query = """
    UPDATE users 
    SET email = :new_email
    WHERE user_id = :user_id
    """
    
    params = {
        "new_email": new_email,
        "user_id": user_id
    }
    
    result = execute_query(query, params, commit=True)
    
    if result is not None:
        return True, "User email updated successfully"
    else:
        return False, "Failed to update user email"

def update_user_username(user_id: str, new_username: str) -> Tuple[bool, str]:
    """
    Update a user's username.
    
    Args:
        user_id (str): The ID of the user
        new_username (str): The new username
        
    Returns:
        Tuple[bool, str]: (success, message)
    """
    # Check if username is already in use
    existing_user = get_user_by_username(new_username)
    if existing_user and existing_user["user_id"] != user_id:
        return False, f"Username {new_username} is already in use"
    
    query = """
    UPDATE users 
    SET username = :new_username
    WHERE user_id = :user_id
    """
    
    params = {
        "new_username": new_username,
        "user_id": user_id
    }
    
    result = execute_query(query, params, commit=True)
    
    if result is not None:
        return True, "Username updated successfully"
    else:
        return False, "Failed to update username"