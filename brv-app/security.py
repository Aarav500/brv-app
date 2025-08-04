import hashlib
import yaml
from datetime import datetime, timedelta
import os
import secrets

USER_FILE = "users.yaml"
PASSWORD_EXPIRY_DAYS = 30

# Hashing

def hash_password(password, salt=None):
    """
    Hash a password using SHA-256 with a random salt.

    Args:
        password (str): The password to hash
        salt (str, optional): Salt to use. If None, a random salt is generated.

    Returns:
        tuple: (hashed_password, salt)
    """
    if salt is None:
        salt = secrets.token_hex(16)

    # Combine password and salt as strings, then hash
    hashed_password = hashlib.sha256((password + salt).encode()).hexdigest()

    return hashed_password, salt

# Simple hash for YAML storage
def _hash_password_simple(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Load users
def load_users():
    if not os.path.exists(USER_FILE):
        return {}
    with open(USER_FILE, "r") as f:
        return yaml.safe_load(f) or {}

# Save users
def save_users(users):
    with open(USER_FILE, "w") as f:
        yaml.dump(users, f)

# Check if password is expired
def is_password_expired(last_changed):
    return datetime.now() > datetime.strptime(last_changed, "%Y-%m-%d") + timedelta(days=PASSWORD_EXPIRY_DAYS)

# Auth logic
def authenticate(username, password):
    users = load_users()
    if username not in users:
        return False, "User does not exist"

    hashed = _hash_password_simple(password)
    if users[username]["password"] != hashed:
        return False, "Incorrect password"

    if users[username].get("force_reset", False):
        return False, "RESET_REQUIRED"

    if is_password_expired(users[username]["last_changed"]):
        return False, "EXPIRED"

    return True, users[username]["role"]

def verify_password(stored_password, provided_password, salt):
    """
    Verify a password against a stored hash.

    Args:
        stored_password (str): The stored hashed password
        provided_password (str): The password to verify
        salt (str): The salt used for hashing

    Returns:
        bool: True if the password matches, False otherwise
    """
    # Hash the provided password with the same salt
    hashed_provided = hashlib.sha256((provided_password + salt).encode()).hexdigest()

    # Compare the hashes
    return hashed_provided == stored_password

def needs_reset(force_reset, last_change_date, max_days=None):
    """
    Check if a password needs to be reset.

    Args:
        force_reset (bool): Flag indicating if a reset is forced
        last_change_date (str): The date the password was last changed
        max_days (int, optional): Maximum number of days a password is valid. If None, uses the system policy.

    Returns:
        bool: True if the password needs to be reset, False otherwise
    """
    # If force_reset is True, password needs to be reset
    if force_reset:
        return True

    # If last_change_date is not provided, consider the password expired
    if not last_change_date:
        return True

    # Check if password has expired
    try:
        # If max_days is not provided, use the default
        if max_days is None:
            max_days = PASSWORD_EXPIRY_DAYS

        # Try parsing as ISO format first
        try:
            last_change = datetime.fromisoformat(last_change_date)
            print(f"[DEBUG] Parsed date using ISO format: {last_change}")
        except (ValueError, TypeError):
            # If that fails, try the old format
            try:
                last_change = datetime.strptime(last_change_date, "%Y-%m-%d %H:%M:%S")
                print(f"[DEBUG] Parsed date using old format: {last_change}")
            except (ValueError, TypeError):
                # If both fail, consider the password expired
                print(f"[DEBUG] Failed to parse date: {last_change_date}")
                return True

        days_since_change = (datetime.now() - last_change).days
        print(f"[DEBUG] Days since password change: {days_since_change}, Max days: {max_days}")
        needs_reset = days_since_change > max_days
        print(f"[DEBUG] Password needs reset: {needs_reset}")
        return needs_reset
    except Exception as e:
        # If there's an error parsing the date, consider the password expired
        print(f"Error checking password expiry: {e}")
        return True

def generate_session_token():
    """
    Generate a random session token.

    Returns:
        str: A random session token
    """
    return hashlib.sha256(os.urandom(32)).hexdigest()

# Create user
def create_user(username, password, role="user"):
    users = load_users()
    users[username] = {
        "password": _hash_password_simple(password),
        "role": role,
        "last_changed": datetime.now().strftime("%Y-%m-%d"),
        "force_reset": True if role != "ceo" else False
    }
    save_users(users)

# Update password
def update_password(username, new_password):
    users = load_users()
    users[username]["password"] = _hash_password_simple(new_password)
    users[username]["last_changed"] = datetime.now().strftime("%Y-%m-%d")
    users[username]["force_reset"] = False
    save_users(users)

# Delete user
def delete_user(username):
    users = load_users()
    if username in users:
        del users[username]
    save_users(users)

# Force password reset (Admin)
def force_reset(username):
    users = load_users()
    if username in users:
        users[username]["force_reset"] = True
        save_users(users)

# Get user role
def get_user_role(username):
    users = load_users()
    return users.get(username, {}).get("role")

def validate_password_strength(password):
    """
    Validate the strength of a password.

    Args:
        password (str): The password to validate

    Returns:
        tuple: (is_valid, message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"

    # Check for at least one uppercase letter
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"

    # Check for at least one lowercase letter
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"

    # Check for at least one digit
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one digit"

    # Check for at least one special character
    special_chars = "!@#$%^&*()-_=+[]{}|;:,.<>?/"
    if not any(c in special_chars for c in password):
        return False, "Password must contain at least one special character"

    return True, "Password is strong"
