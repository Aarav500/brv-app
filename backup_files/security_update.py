import hashlib
import os
import secrets

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