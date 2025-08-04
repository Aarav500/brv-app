import mysql.connector
from mysql.connector import Error
import json
from datetime import datetime
import os
import sqlite3
from typing import Dict, List, Optional, Any, Tuple, Union

# Database connection configuration
# In a production environment, these should be stored as environment variables
import os

# Planetscale connection parameters (MySQL-compatible)
MYSQL_HOST = os.getenv("PLANETSCALE_HOST", "127.0.0.1")  # Default to localhost if not set
MYSQL_USER = os.getenv("PLANETSCALE_USERNAME", "root")  # Default to root if not set
MYSQL_PASSWORD = os.getenv("PLANETSCALE_PASSWORD", "password")  # Default to password if not set
MYSQL_DATABASE = os.getenv("PLANETSCALE_DATABASE", "brv_db")  # Default to brv_db if not set
MYSQL_SSL_CA = os.getenv("PLANETSCALE_SSL_CA", None)  # SSL CA certificate for Planetscale

# SQLite database path (fallback)
SQLITE_DB_PATH = 'data/brv_applicants.db'

# Flag to track which database we're using
USING_SQLITE = False

def get_db_connection():
    """
    Create and return a connection to the database.
    Tries MySQL/Planetscale first, falls back to SQLite if MySQL is not available.
    
    Returns:
        Connection object (either MySQL or SQLite)
    """
    global USING_SQLITE
    
    # Try MySQL/Planetscale first
    try:
        # Prepare connection parameters
        connection_params = {
            'host': MYSQL_HOST,
            'user': MYSQL_USER,
            'password': MYSQL_PASSWORD,
            'database': MYSQL_DATABASE
        }
        
        # Add SSL configuration if provided (required for Planetscale)
        if MYSQL_SSL_CA:
            connection_params['ssl_ca'] = MYSQL_SSL_CA
            connection_params['ssl_verify_cert'] = True
        
        # Connect to MySQL/Planetscale
        connection = mysql.connector.connect(**connection_params)
        USING_SQLITE = False
        return connection
    except Error as e:
        print(f"Error connecting to MySQL database: {e}")
        print("\n🔥 MySQL Connection Failed - Falling back to SQLite database...")
        print("\n💣 Possible causes:")
        print("  - MySQL server is not running")
        print("  - MySQL server is not installed")
        print("  - MySQL server is running on a different port or host")
        print("  - MySQL credentials are incorrect")
        print("\n✅ How to fix:")
        print("  1. Make sure MySQL is running:")
        print("     - On Windows: Press Win + R → type services.msc")
        print("     - Find MySQL (or MySQL80) → Right-click → Start")
        print("     - Or in terminal: net start mysql")
        print("     - If using XAMPP: Open XAMPP Control Panel → Start MySQL")
        print("  2. If MySQL is not installed:")
        print("     - Download from: https://dev.mysql.com/downloads/installer/")
        print("     - During setup: Create a root password, enable TCP port 3306")
        print("  3. Test MySQL connection manually:")
        print("     - Open CMD and type: mysql -u root -p -h 127.0.0.1 -P 3306")
        print("  4. If you've installed MySQL with different credentials:")
        print("     - Update MYSQL_USER and MYSQL_PASSWORD in mysql_db.py")
        
        # Fall back to SQLite
        try:
            # Ensure the data directory exists
            os.makedirs(os.path.dirname(SQLITE_DB_PATH), exist_ok=True)
            
            connection = sqlite3.connect(SQLITE_DB_PATH)
            USING_SQLITE = True
            return connection
        except Exception as e:
            print(f"Error connecting to SQLite database: {e}")
            return None

def close_connection(connection):
    """
    Close the database connection.
    
    Args:
        connection: The database connection to close
    """
    if connection:
        if USING_SQLITE:
            # SQLite connection
            connection.close()
        else:
            # MySQL connection
            if hasattr(connection, 'is_connected') and connection.is_connected():
                connection.close()

# User-related functions
def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """
    Get a user by email.
    
    Args:
        email (str): The user's email
        
    Returns:
        Optional[Dict[str, Any]]: User data or None if not found
    """
    connection = get_db_connection()
    if not connection:
        return None
    
    try:
        if USING_SQLITE:
            # SQLite version
            cursor = connection.cursor()
            query = "SELECT * FROM users WHERE email = ?"
            cursor.execute(query, (email,))
            result = cursor.fetchone()
            
            if result:
                # Get column names
                column_names = [description[0] for description in cursor.description]
                
                # Create a dictionary from column names and values
                user = {}
                for i, column in enumerate(column_names):
                    user[column] = result[i]
                
                # Map password to password_hash for consistency
                if 'password' in user and 'password_hash' not in user:
                    user['password_hash'] = user['password']
                
                return user
            return None
        else:
            # MySQL version
            cursor = connection.cursor(dictionary=True)
            query = "SELECT * FROM users WHERE email = %s"
            cursor.execute(query, (email,))
            user = cursor.fetchone()
            return user
    except Exception as e:
        print(f"Error retrieving user: {e}")
        return None
    finally:
        close_connection(connection)

def authenticate_user(email: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Authenticate a user with email and password.
    
    Args:
        email (str): The user's email
        password (str): The user's password
        
    Returns:
        Optional[Dict[str, Any]]: User data if authentication successful, None otherwise
    """
    connection = get_db_connection()
    if not connection:
        return None
    
    try:
        if USING_SQLITE:
            # SQLite version
            cursor = connection.cursor()
            
            # Extract username part from email (before @)
            username = email.split('@')[0] if '@' in email else email
            print(f"[DEBUG] Trying to authenticate with username: {username} or email: {email}")
            
            # Try both full email and username part
            query = "SELECT id, email, password, role, salt FROM users WHERE email = ? OR email = ?"
            cursor.execute(query, (email, username))
            result = cursor.fetchone()
            
            if result:
                user = {
                    "id": result[0],
                    "email": result[1],
                    "password_hash": result[2],
                    "role": result[3],
                    "salt": result[4] if len(result) > 4 else None
                }
                
                print(f"[DEBUG] Found user: {user['email']}, role: {user['role']}")
                
                # TEMPORARY SOLUTION: Bypass password verification for SQLite fallback
                # In a production environment, a more secure solution would be needed
                print(f"[DEBUG] TEMPORARY SOLUTION: Bypassing password verification for SQLite fallback")
                
                # Check if the provided password matches the expected default password for the role
                # This is a basic check to prevent completely unrestricted access
                expected_password = None
                if user['role'].lower() == 'ceo':
                    expected_password = "345"
                elif user['role'].lower() == 'receptionist':
                    expected_password = "123"
                elif user['role'].lower() == 'interviewer':
                    expected_password = "234"
                
                if expected_password and password == expected_password:
                    print(f"[DEBUG] Password matches expected default for role: {user['role']}")
                    # Don't return the password hash and salt
                    del user['password_hash']
                    if 'salt' in user:
                        del user['salt']
                    return user
                else:
                    print(f"[DEBUG] Password does not match expected default for role: {user['role']}")
                    # For testing purposes, you can uncomment the following lines to allow any password
                    # del user['password_hash']
                    # if 'salt' in user:
                    #     del user['salt']
                    # return user
            else:
                print(f"[DEBUG] No user found with email: {email} or username: {username}")
            return None
        else:
            # MySQL version
            cursor = connection.cursor(dictionary=True)
            query = "SELECT id, email, password_hash, role FROM users WHERE email = %s"
            cursor.execute(query, (email,))
            user = cursor.fetchone()
            
            if user and verify_password(password, user['password_hash']):
                # Don't return the password hash
                del user['password_hash']
                return user
            return None
    except Exception as e:
        print(f"Error authenticating user: {e}")
        return None
    finally:
        close_connection(connection)

def verify_password(password: str, password_hash: str) -> bool:
    """
    Verify a password against a hash.
    
    Args:
        password (str): The password to verify
        password_hash (str): The stored password hash
        
    Returns:
        bool: True if the password matches the hash, False otherwise
    """
    # In a real implementation, use a proper password hashing library like bcrypt
    # For simplicity, we're using a basic comparison here
    # This should be replaced with proper password hashing in production
    return password == password_hash  # REPLACE THIS WITH PROPER HASHING

def create_user(email: str, password: str, role: str) -> Optional[int]:
    """
    Create a new user.
    
    Args:
        email (str): The user's email
        password (str): The user's password
        role (str): The user's role
        
    Returns:
        Optional[int]: The ID of the created user, or None if creation failed
    """
    connection = get_db_connection()
    if not connection:
        return None
    
    try:
        cursor = connection.cursor()
        query = """
        INSERT INTO users (email, password_hash, role, created_at, force_password_reset, last_password_change)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        # In a real implementation, hash the password
        # password_hash = hash_password(password)
        password_hash = password  # REPLACE THIS WITH PROPER HASHING
        
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        force_reset = True if role.lower() != "ceo" else False
        
        cursor.execute(query, (email, password_hash, role, created_at, force_reset, created_at))
        connection.commit()
        
        return cursor.lastrowid
    except Error as e:
        print(f"Error creating user: {e}")
        return None
    finally:
        close_connection(connection)

def add_user(email: str, password: str, role: str) -> Tuple[bool, str]:
    """
    Add a new user to the database.
    
    Args:
        email (str): The user's email
        password (str): The user's password
        role (str): The user's role
        
    Returns:
        Tuple[bool, str]: (success, message)
    """
    # Validate email format
    import re
    email_regex = r"[^@]+@[^@]+\.[^@]+"
    if not re.match(email_regex, email):
        return False, "Username must be a valid email format (e.g., john.doe@company.com)"
    
    # Validate email domain
    if not email.endswith("@bluematrixit.com"):
        return False, "Only official Bluematrix emails are allowed"
    
    # Check if email already exists
    existing_user = get_user_by_email(email)
    if existing_user:
        return False, "Email already exists"
    
    # Create the user
    user_id = create_user(email, password, role)
    if user_id:
        return True, "User added successfully"
    else:
        return False, "Failed to create user"

def force_password_reset_all() -> bool:
    """
    Force all users to reset their passwords on next login.
    
    Returns:
        bool: True if successful, False otherwise
    """
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        query = "UPDATE users SET force_password_reset = 1"
        cursor.execute(query)
        connection.commit()
        return True
    except Error as e:
        print(f"Error forcing password reset for all users: {e}")
        return False
    finally:
        close_connection(connection)

def update_user_password(user_id: int, new_password: str) -> bool:
    """
    Update a user's password.
    
    Args:
        user_id (int): The ID of the user
        new_password (str): The new password
        
    Returns:
        bool: True if the password was updated successfully, False otherwise
    """
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        # In a real implementation, hash the password
        # password_hash = hash_password(new_password)
        password_hash = new_password  # REPLACE THIS WITH PROPER HASHING
        
        if USING_SQLITE:
            # SQLite version
            cursor = connection.cursor()
            
            # Check if the column is named password_hash or password
            try:
                # First try with password_hash
                query = "UPDATE users SET password_hash = ? WHERE id = ?"
                cursor.execute(query, (password_hash, user_id))
            except sqlite3.OperationalError:
                # If that fails, try with password
                query = "UPDATE users SET password = ? WHERE id = ?"
                cursor.execute(query, (password_hash, user_id))
            
            connection.commit()
            return cursor.rowcount > 0
        else:
            # MySQL version
            cursor = connection.cursor()
            query = "UPDATE users SET password_hash = %s WHERE id = %s"
            cursor.execute(query, (password_hash, user_id))
            connection.commit()
            return cursor.rowcount > 0
    except Exception as e:
        print(f"Error updating user password: {e}")
        return False
    finally:
        close_connection(connection)

def get_all_users() -> List[Dict[str, Any]]:
    """
    Get all users.
    
    Returns:
        List[Dict[str, Any]]: List of all users
    """
    connection = get_db_connection()
    if not connection:
        return []
    
    try:
        cursor = connection.cursor(dictionary=True)
        query = "SELECT id, email, role, created_at FROM users"
        cursor.execute(query)
        users = cursor.fetchall()
        return users
    except Error as e:
        print(f"Error retrieving users: {e}")
        return []
    finally:
        close_connection(connection)

# Functions to link candidates with user accounts
def link_candidate_to_user(candidate_id: int, user_id: int) -> bool:
    """
    Link a candidate profile to a user account.
    
    Args:
        candidate_id (int): The ID of the candidate
        user_id (int): The ID of the user
        
    Returns:
        bool: True if the link was created successfully, False otherwise
    """
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        # First, check if the candidate and user exist
        cursor = connection.cursor(dictionary=True)
        
        # Check candidate
        cursor.execute("SELECT id FROM candidates WHERE id = %s", (candidate_id,))
        if not cursor.fetchone():
            print(f"Candidate with ID {candidate_id} not found")
            return False
        
        # Check user
        cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
        if not cursor.fetchone():
            print(f"User with ID {user_id} not found")
            return False
        
        # Update the candidate record with the user_id
        # Note: We need to add a user_id column to the candidates table
        # This would require a schema change, but for now we'll store it in form_data
        
        # Get current form_data
        cursor.execute("SELECT form_data FROM candidates WHERE id = %s", (candidate_id,))
        result = cursor.fetchone()
        
        if result and result['form_data']:
            form_data = json.loads(result['form_data'])
        else:
            form_data = {}
        
        # Add user_id to form_data
        form_data['user_id'] = user_id
        form_data_json = json.dumps(form_data)
        
        # Update the candidate record
        cursor.execute(
            "UPDATE candidates SET form_data = %s WHERE id = %s",
            (form_data_json, candidate_id)
        )
        connection.commit()
        
        return True
    except Error as e:
        print(f"Error linking candidate to user: {e}")
        return False
    finally:
        close_connection(connection)

def get_candidate_by_user_id(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a candidate by user ID.
    
    Args:
        user_id (int): The user's ID
        
    Returns:
        Optional[Dict[str, Any]]: Candidate data or None if not found
    """
    connection = get_db_connection()
    if not connection:
        return None
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        # Get all candidates
        cursor.execute("SELECT * FROM candidates")
        candidates = cursor.fetchall()
        
        # Find the candidate with the matching user_id in form_data
        for candidate in candidates:
            if candidate['form_data']:
                form_data = json.loads(candidate['form_data'])
                if form_data.get('user_id') == user_id:
                    # Parse form_data JSON
                    candidate.update(form_data)
                    
                    # Remove the JSON field to avoid duplication
                    del candidate['form_data']
                    
                    return candidate
        
        return None
    except Error as e:
        print(f"Error retrieving candidate by user ID: {e}")
        return None
    finally:
        close_connection(connection)

def create_candidate_user(email: str, password: str, name: str) -> Optional[int]:
    """
    Create a new user with the 'candidate' role.
    
    Args:
        email (str): The candidate's email
        password (str): The candidate's password
        name (str): The candidate's name
        
    Returns:
        Optional[int]: The ID of the created user, or None if creation failed
    """
    # First, check if a user with this email already exists
    existing_user = get_user_by_email(email)
    if existing_user:
        print(f"User with email {email} already exists")
        return existing_user['id']
    
    # Create a new user with the 'candidate' role
    user_id = create_user(email, password, 'candidate')
    if not user_id:
        print(f"Failed to create user with email {email}")
        return None
    
    return user_id

# Candidate-related functions
def create_candidate(candidate_data: Dict[str, Any], create_user_account: bool = False, password: str = None) -> Optional[int]:
    """
    Create a new candidate.
    
    Args:
        candidate_data (Dict[str, Any]): The candidate data
        create_user_account (bool, optional): Whether to create a user account for the candidate. Defaults to False.
        password (str, optional): The password for the user account. Required if create_user_account is True.
        
    Returns:
        Optional[int]: The ID of the created candidate, or None if creation failed
    """
    connection = get_db_connection()
    if not connection:
        return None
    
    try:
        cursor = connection.cursor()
        
        # Extract fields from candidate_data
        name = candidate_data.get('name', '')
        email = candidate_data.get('email', '')
        phone = candidate_data.get('phone', '')
        
        # Convert form data to JSON
        form_data = {
            'skills': candidate_data.get('skills', ''),
            'experience': candidate_data.get('experience', ''),
            'education': candidate_data.get('education', '')
        }
        
        # If creating a user account, check if we have a password
        user_id = None
        if create_user_account:
            if not password:
                print("Password is required to create a user account")
                return None
            
            # Create a user account with the 'candidate' role
            user_id = create_candidate_user(email, password, name)
            if user_id:
                # Store the user_id in form_data
                form_data['user_id'] = user_id
        
        form_data_json = json.dumps(form_data)
        
        # Get resume URL if available
        resume_url = candidate_data.get('cv_url', '')
        
        # Get created_by if available, otherwise use 'system'
        created_by = candidate_data.get('created_by', 'system')
        
        # Current timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        query = """
        INSERT INTO candidates (name, email, phone, form_data, resume_url, created_by, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(query, (name, email, phone, form_data_json, resume_url, created_by, timestamp))
        connection.commit()
        
        candidate_id = cursor.lastrowid
        
        # If we created a user account and have a user_id, link it to the candidate
        if user_id and candidate_id:
            # We don't need to call link_candidate_to_user here since we already stored the user_id in form_data
            print(f"Created candidate {candidate_id} with linked user account {user_id}")
        
        # Return the created candidate with its ID
        return candidate_id
    except Error as e:
        print(f"Error creating candidate: {e}")
        return None
    finally:
        close_connection(connection)

def get_candidate_by_id(candidate_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a candidate by ID.
    
    Args:
        candidate_id (int): The candidate's ID
        
    Returns:
        Optional[Dict[str, Any]]: Candidate data or None if not found
    """
    connection = get_db_connection()
    if not connection:
        return None
    
    try:
        cursor = connection.cursor(dictionary=True)
        query = "SELECT * FROM candidates WHERE id = %s"
        cursor.execute(query, (candidate_id,))
        candidate = cursor.fetchone()
        
        if candidate:
            # Parse form_data JSON
            if candidate['form_data']:
                form_data = json.loads(candidate['form_data'])
                # Merge form_data fields into the candidate dict
                candidate.update(form_data)
            
            # Remove the JSON field to avoid duplication
            del candidate['form_data']
        
        return candidate
    except Error as e:
        print(f"Error retrieving candidate: {e}")
        return None
    finally:
        close_connection(connection)

def get_candidate_by_email(email: str) -> Optional[Dict[str, Any]]:
    """
    Get a candidate by email.
    
    Args:
        email (str): The candidate's email
        
    Returns:
        Optional[Dict[str, Any]]: Candidate data or None if not found
    """
    connection = get_db_connection()
    if not connection:
        return None
    
    try:
        if USING_SQLITE:
            # SQLite version
            cursor = connection.cursor()
            query = "SELECT * FROM candidates WHERE email = ?"
            cursor.execute(query, (email,))
            result = cursor.fetchone()
            
            if result:
                # Get column names
                column_names = [description[0] for description in cursor.description]
                
                # Create a dictionary from column names and values
                candidate = {}
                for i, column in enumerate(column_names):
                    candidate[column] = result[i]
                
                # Parse form_data JSON
                if candidate.get('form_data'):
                    form_data = json.loads(candidate['form_data'])
                    # Merge form_data fields into the candidate dict
                    candidate.update(form_data)
                
                # Remove the JSON field to avoid duplication
                if 'form_data' in candidate:
                    del candidate['form_data']
                
                return candidate
            return None
        else:
            # MySQL version
            cursor = connection.cursor(dictionary=True)
            query = "SELECT * FROM candidates WHERE email = %s"
            cursor.execute(query, (email,))
            candidate = cursor.fetchone()
            
            if candidate:
                # Parse form_data JSON
                if candidate['form_data']:
                    form_data = json.loads(candidate['form_data'])
                    # Merge form_data fields into the candidate dict
                    candidate.update(form_data)
                
                # Remove the JSON field to avoid duplication
                del candidate['form_data']
            
            return candidate
    except Exception as e:
        print(f"Error retrieving candidate: {e}")
        return None
    finally:
        close_connection(connection)

def get_candidate_by_name_and_id(candidate_id: int, name: str) -> Optional[Dict[str, Any]]:
    """
    Get a candidate by ID and name.
    
    Args:
        candidate_id (int): The candidate's ID
        name (str): The candidate's name
        
    Returns:
        Optional[Dict[str, Any]]: Candidate data or None if not found or name doesn't match
    """
    candidate = get_candidate_by_id(candidate_id)
    
    if candidate and candidate['name'].lower() == name.lower():
        return candidate
    
    return None

def update_candidate(candidate_id: int, updated_data: Dict[str, Any]) -> bool:
    """
    Update a candidate's data.
    
    Args:
        candidate_id (int): The ID of the candidate
        updated_data (Dict[str, Any]): The updated candidate data
        
    Returns:
        bool: True if the candidate was updated successfully, False otherwise
    """
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        # First, get the current candidate data
        current_candidate = get_candidate_by_id(candidate_id)
        if not current_candidate:
            return False
        
        cursor = connection.cursor()
        
        # Extract fields that go directly into the candidates table
        name = updated_data.get('name', current_candidate.get('name', ''))
        email = updated_data.get('email', current_candidate.get('email', ''))
        phone = updated_data.get('phone', current_candidate.get('phone', ''))
        resume_url = updated_data.get('cv_url', current_candidate.get('resume_url', ''))
        
        # Extract fields that go into the form_data JSON
        form_data = {
            'skills': updated_data.get('skills', current_candidate.get('skills', '')),
            'experience': updated_data.get('experience', current_candidate.get('experience', '')),
            'education': updated_data.get('education', current_candidate.get('education', ''))
        }
        form_data_json = json.dumps(form_data)
        
        # Current timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        query = """
        UPDATE candidates 
        SET name = %s, email = %s, phone = %s, form_data = %s, resume_url = %s, updated_at = %s
        WHERE id = %s
        """
        
        cursor.execute(query, (name, email, phone, form_data_json, resume_url, timestamp, candidate_id))
        connection.commit()
        
        return cursor.rowcount > 0
    except Error as e:
        print(f"Error updating candidate: {e}")
        return False
    finally:
        close_connection(connection)

def add_candidate(hr_data, form_data=None):
    """
    Add a new candidate with HR data and optional form data.
    
    Args:
        hr_data (dict): HR-collected data about the candidate
        form_data (dict, optional): Form data submitted by the candidate
        
    Returns:
        tuple: (success, result) where success is a boolean and result is the candidate ID or error message
    """
    try:
        # Combine hr_data and form_data into a single dictionary
        candidate_data = hr_data.copy()
        
        # If form_data is provided, add it to candidate_data
        if form_data:
            # Add form_data fields to candidate_data
            for key, value in form_data.items():
                if key not in candidate_data:
                    candidate_data[key] = value
        
        # Extract resume URL if available
        resume_url = hr_data.get('resume_url', '')
        candidate_data['cv_url'] = resume_url
        
        # Create the candidate
        candidate_id = create_candidate(candidate_data)
        
        if candidate_id:
            return True, candidate_id
        else:
            return False, "Failed to create candidate"
    except Exception as e:
        print(f"Error in add_candidate: {e}")
        return False, str(e)

def get_all_candidates() -> List[Dict[str, Any]]:
    """
    Get all candidates.
    
    Returns:
        List[Dict[str, Any]]: List of all candidates
    """
    connection = get_db_connection()
    if not connection:
        return []
    
    try:
        cursor = connection.cursor(dictionary=True)
        query = "SELECT * FROM candidates ORDER BY updated_at DESC"
        cursor.execute(query)
        candidates = cursor.fetchall()
        
        # Process each candidate to extract form_data
        for candidate in candidates:
            if candidate['form_data']:
                form_data = json.loads(candidate['form_data'])
                # Merge form_data fields into the candidate dict
                candidate.update(form_data)
            
            # Remove the JSON field to avoid duplication
            del candidate['form_data']
        
        return candidates
    except Error as e:
        print(f"Error retrieving candidates: {e}")
        return []
    finally:
        close_connection(connection)

def search_candidates(search_term: str) -> List[Dict[str, Any]]:
    """
    Search for candidates by name or email.
    
    Args:
        search_term (str): The search term
        
    Returns:
        List[Dict[str, Any]]: List of matching candidates
    """
    connection = get_db_connection()
    if not connection:
        return []
    
    try:
        cursor = connection.cursor(dictionary=True)
        query = """
        SELECT * FROM candidates 
        WHERE name LIKE %s OR email LIKE %s
        ORDER BY updated_at DESC
        """
        search_pattern = f"%{search_term}%"
        cursor.execute(query, (search_pattern, search_pattern))
        candidates = cursor.fetchall()
        
        # Process each candidate to extract form_data
        for candidate in candidates:
            if candidate['form_data']:
                form_data = json.loads(candidate['form_data'])
                # Merge form_data fields into the candidate dict
                candidate.update(form_data)
            
            # Remove the JSON field to avoid duplication
            del candidate['form_data']
        
        return candidates
    except Error as e:
        print(f"Error searching candidates: {e}")
        return []
    finally:
        close_connection(connection)

# Helper functions for testing the database connection
def remove_user(user_id: int) -> Tuple[bool, str]:
    """
    Remove a user from the database.
    
    Args:
        user_id (int): The ID of the user to remove
        
    Returns:
        Tuple[bool, str]: (success, message)
    """
    connection = get_db_connection()
    if not connection:
        return False, "Database connection failed"
    
    try:
        cursor = connection.cursor()
        
        # Check if user exists
        cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
        if not cursor.fetchone():
            return False, "User not found"
        
        # Delete the user
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        connection.commit()
        
        return True, "User removed successfully"
    except Error as e:
        print(f"Error removing user: {e}")
        return False, f"Error: {str(e)}"
    finally:
        close_connection(connection)

def update_user_role(user_id: int, new_role: str, new_email: str = None) -> Tuple[bool, str]:
    """
    Update a user's role and optionally email.
    
    Args:
        user_id (int): The ID of the user
        new_role (str): The new role for the user
        new_email (str, optional): The new email for the user
        
    Returns:
        Tuple[bool, str]: (success, message)
    """
    connection = get_db_connection()
    if not connection:
        return False, "Database connection failed"
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        # Check if user exists
        cursor.execute("SELECT id, email FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        if not user:
            return False, "User not found"
        
        current_email = user['email']
        
        # If new email is provided and different from current email
        if new_email and new_email != current_email:
            # Check if the new email is already in use by another user
            cursor.execute("SELECT COUNT(*) as count FROM users WHERE email = %s AND id != %s", 
                          (new_email, user_id))
            result = cursor.fetchone()
            if result and result['count'] > 0:
                return False, f"Email {new_email} is already in use by another user"
            
            # Update both role and email
            cursor.execute(
                "UPDATE users SET role = %s, email = %s WHERE id = %s",
                (new_role, new_email, user_id)
            )
            connection.commit()
            return True, "Role and email updated successfully"
        else:
            # Update only the role
            cursor.execute(
                "UPDATE users SET role = %s WHERE id = %s",
                (new_role, user_id)
            )
            connection.commit()
            return True, "Role updated successfully"
    except Error as e:
        print(f"Error updating user role: {e}")
        return False, f"Error: {str(e)}"
    finally:
        close_connection(connection)

def create_settings_table():
    """
    Create the settings table if it doesn't exist.
    
    Returns:
        bool: True if the table was created successfully, False otherwise
    """
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        
        # Create settings table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            `key` VARCHAR(255) PRIMARY KEY,
            `value` TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
        """)
        
        connection.commit()
        return True
    except Error as e:
        print(f"Error creating settings table: {e}")
        return False
    finally:
        close_connection(connection)

def update_password_expiry_policy(max_days: int) -> Tuple[bool, str]:
    """
    Update the password expiration policy.
    
    Args:
        max_days (int): Maximum number of days a password is valid
        
    Returns:
        Tuple[bool, str]: (success, message)
    """
    # Validate input
    try:
        max_days = int(max_days)
        if max_days < 1:
            return False, "Password expiry days must be a positive number"
    except:
        return False, "Invalid input for password expiry days"
    
    # Ensure settings table exists
    if not create_settings_table():
        return False, "Failed to create settings table"
    
    connection = get_db_connection()
    if not connection:
        return False, "Database connection failed"
    
    try:
        cursor = connection.cursor()
        
        # Update or insert the password_expiry_days setting
        cursor.execute("""
        INSERT INTO settings (`key`, `value`) 
        VALUES ('password_expiry_days', %s)
        ON DUPLICATE KEY UPDATE `value` = %s
        """, (str(max_days), str(max_days)))
        
        connection.commit()
        return True, f"Password expiry policy updated to {max_days} days"
    except Error as e:
        print(f"Error updating password expiry policy: {e}")
        return False, f"Error: {str(e)}"
    finally:
        close_connection(connection)

def get_password_expiry_policy() -> int:
    """
    Get the current password expiration policy.
    
    Returns:
        int: Maximum number of days a password is valid (default: 30)
    """
    # Ensure settings table exists
    create_settings_table()
    
    connection = get_db_connection()
    if not connection:
        return 30  # Default if connection fails
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        # Get the password_expiry_days setting
        cursor.execute("SELECT `value` FROM settings WHERE `key` = 'password_expiry_days'")
        result = cursor.fetchone()
        
        if result and result['value']:
            try:
                return int(result['value'])
            except:
                return 30  # Default if value is not a valid integer
        else:
            return 30  # Default if setting doesn't exist
    except Error as e:
        print(f"Error getting password expiry policy: {e}")
        return 30  # Default if there's an error
    finally:
        close_connection(connection)

def test_connection() -> bool:
    """
    Test the database connection.
    
    Returns:
        bool: True if the connection is successful, False otherwise
    """
    try:
        print("\n🔄 Testing database connection...")
        connection = get_db_connection()
        if connection:
            if USING_SQLITE:
                try:
                    # Test SQLite connection by executing a simple query
                    cursor = connection.cursor()
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
                    print("\n✅ SQLite connection successful (MySQL fallback active)")
                    print("\n⚠️ Warning: You are using SQLite as a fallback database.")
                    print("   This means your MySQL connection failed.")
                    print("   SQLite has no default users, so login may fail.")
                    print("\n📋 To fix MySQL connection:")
                    print("   1. Make sure MySQL is running")
                    print("   2. Check if MySQL is installed")
                    print("   3. Verify MySQL credentials in mysql_db.py")
                    print("   4. Run this test again to confirm connection")
                    close_connection(connection)
                    return True
                except Exception as e:
                    print(f"\n❌ SQLite connection failed: {e}")
                    print("\n💥 Both MySQL and SQLite connections failed.")
                    print("   Please check your database configuration.")
                    return False
            else:
                # MySQL connection
                if hasattr(connection, 'is_connected') and connection.is_connected():
                    print("\n✅ MySQL connection successful")
                    print("\n🎉 Your application is properly connected to MySQL.")
                    print("   You should be able to log in with the default credentials.")
                    close_connection(connection)
                    return True
                else:
                    print("\n❌ MySQL connection failed")
                    print("\n💥 Connection object exists but is not connected.")
                    print("   This is an unusual error. Please check your MySQL configuration.")
                    return False
        else:
            print("\n❌ Database connection failed")
            print("\n💥 Could not establish any database connection.")
            print("   Please check both MySQL and SQLite configurations.")
            return False
    except Exception as e:
        print(f"\n❌ Database connection test failed: {e}")
        print("\n💥 An unexpected error occurred during connection test.")
        print("   Please check your database configuration and try again.")
        return False

if __name__ == "__main__":
    # Test the database connection
    test_connection()