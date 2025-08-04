import os
import json
import uuid
import bcrypt
from datetime import datetime

# Import Oracle DB connection
import oracledb
from env_config import (
    ORACLE_USER,
    ORACLE_PASSWORD,
    ORACLE_DSN,
    ORACLE_WALLET_LOCATION,
    get_db_config,
    update_db_config
)

def init_oracle_client():
    """
    Initialize the Oracle client in thin mode.
    This must be called before any database operations.
    """
    try:
        # Set TNS_ADMIN environment variable
        wallet_location = ORACLE_WALLET_LOCATION
        os.environ["TNS_ADMIN"] = os.path.join(os.getcwd(), wallet_location)
        print(f"TNS_ADMIN set to: {os.environ['TNS_ADMIN']}")
        
        # Force the use of Thin mode (which doesn't need an external Oracle Client)
        oracledb.thin = True
        print("✅ Oracle client initialized successfully (thin mode)")
        return True
    except Exception as e:
        print(f"❌ Error initializing Oracle client: {e}")
        return False

def get_connection():
    """
    Get a connection to the Oracle database.
    
    Returns:
        oracledb.Connection: The database connection
    """
    try:
        # Initialize Oracle client if not already initialized
        init_oracle_client()
        
        # Get the current database configuration
        config = get_db_config()
        current_db = config["current_write_db"]
        
        # Connect to the database
        connection = oracledb.connect(
            user=ORACLE_USER,
            password=ORACLE_PASSWORD,
            dsn=current_db
        )
        
        return connection
    except Exception as e:
        print(f"❌ Error connecting to Oracle database: {e}")
        return None

def close_connection(connection):
    """
    Close the database connection.
    
    Args:
        connection: The connection to close
    """
    if connection:
        try:
            connection.close()
        except Exception as e:
            print(f"❌ Error closing connection: {e}")

def create_users_table():
    """
    Create the users table in the Oracle database.
    
    Returns:
        bool: True if successful, False otherwise
    """
    connection = get_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        
        # Create users table
        cursor.execute("""
        BEGIN
            EXECUTE IMMEDIATE 'CREATE TABLE users (
                user_id VARCHAR2(36) PRIMARY KEY,
                username VARCHAR2(100) UNIQUE,
                email VARCHAR2(255) UNIQUE,
                password_hash VARCHAR2(255),
                role VARCHAR2(50),
                last_password_change TIMESTAMP,
                force_password_reset NUMBER(1)
            )';
        EXCEPTION
            WHEN OTHERS THEN
                IF SQLCODE = -955 THEN
                    NULL; -- Table already exists
                ELSE
                    RAISE;
                END IF;
        END;
        """)
        
        connection.commit()
        print("✅ Users table created or already exists")
        return True
    except Exception as e:
        print(f"❌ Error creating users table: {e}")
        return False
    finally:
        close_connection(connection)

def create_candidates_table():
    """
    Create the candidates table in the Oracle database.
    
    Returns:
        bool: True if successful, False otherwise
    """
    connection = get_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        
        # Create candidates table
        cursor.execute("""
        BEGIN
            EXECUTE IMMEDIATE 'CREATE TABLE candidates (
                candidate_id VARCHAR2(36) PRIMARY KEY,
                full_name VARCHAR2(255),
                email VARCHAR2(255),
                phone VARCHAR2(20),
                additional_phone VARCHAR2(20),
                dob DATE,
                caste VARCHAR2(50),
                sub_caste VARCHAR2(50),
                marital_status VARCHAR2(50),
                qualification VARCHAR2(100),
                work_experience VARCHAR2(100),
                referral VARCHAR2(255),
                resume_link VARCHAR2(500),
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                interview_status VARCHAR2(50)
            )';
        EXCEPTION
            WHEN OTHERS THEN
                IF SQLCODE = -955 THEN
                    NULL; -- Table already exists
                ELSE
                    RAISE;
                END IF;
        END;
        """)
        
        connection.commit()
        print("✅ Candidates table created or already exists")
        return True
    except Exception as e:
        print(f"❌ Error creating candidates table: {e}")
        return False
    finally:
        close_connection(connection)

def create_interviews_table():
    """
    Create the interviews table in the Oracle database.
    
    Returns:
        bool: True if successful, False otherwise
    """
    connection = get_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        
        # Create interviews table
        cursor.execute("""
        BEGIN
            EXECUTE IMMEDIATE 'CREATE TABLE interviews (
                interview_id VARCHAR2(36) PRIMARY KEY,
                candidate_id VARCHAR2(36),
                interviewer_id VARCHAR2(36),
                scheduled_time TIMESTAMP,
                feedback CLOB,
                status VARCHAR2(50),
                result VARCHAR2(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_candidate
                    FOREIGN KEY (candidate_id)
                    REFERENCES candidates(candidate_id),
                CONSTRAINT fk_interviewer
                    FOREIGN KEY (interviewer_id)
                    REFERENCES users(user_id)
            )';
        EXCEPTION
            WHEN OTHERS THEN
                IF SQLCODE = -955 THEN
                    NULL; -- Table already exists
                ELSE
                    RAISE;
                END IF;
        END;
        """)
        
        connection.commit()
        print("✅ Interviews table created or already exists")
        return True
    except Exception as e:
        print(f"❌ Error creating interviews table: {e}")
        return False
    finally:
        close_connection(connection)

def create_settings_table():
    """
    Create the settings table in the Oracle database.
    
    Returns:
        bool: True if successful, False otherwise
    """
    connection = get_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        
        # Create settings table
        cursor.execute("""
        BEGIN
            EXECUTE IMMEDIATE 'CREATE TABLE settings (
                key VARCHAR2(255) PRIMARY KEY,
                value CLOB,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )';
        EXCEPTION
            WHEN OTHERS THEN
                IF SQLCODE = -955 THEN
                    NULL; -- Table already exists
                ELSE
                    RAISE;
                END IF;
        END;
        """)
        
        connection.commit()
        print("✅ Settings table created or already exists")
        return True
    except Exception as e:
        print(f"❌ Error creating settings table: {e}")
        return False
    finally:
        close_connection(connection)

def create_activity_log_table():
    """
    Create the activity_log table in the Oracle database.
    
    Returns:
        bool: True if successful, False otherwise
    """
    connection = get_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        
        # Create activity_log table
        cursor.execute("""
        BEGIN
            EXECUTE IMMEDIATE 'CREATE TABLE activity_log (
                log_id VARCHAR2(36) PRIMARY KEY,
                user_id VARCHAR2(36),
                action VARCHAR2(255),
                details CLOB,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_user_log
                    FOREIGN KEY (user_id)
                    REFERENCES users(user_id)
            )';
        EXCEPTION
            WHEN OTHERS THEN
                IF SQLCODE = -955 THEN
                    NULL; -- Table already exists
                ELSE
                    RAISE;
                END IF;
        END;
        """)
        
        connection.commit()
        print("✅ Activity log table created or already exists")
        return True
    except Exception as e:
        print(f"❌ Error creating activity log table: {e}")
        return False
    finally:
        close_connection(connection)

def create_resumes_metadata_table():
    """
    Create the resumes_metadata table in the Oracle database.
    
    Returns:
        bool: True if successful, False otherwise
    """
    connection = get_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        
        # Create resumes_metadata table
        cursor.execute("""
        BEGIN
            EXECUTE IMMEDIATE 'CREATE TABLE resumes_metadata (
                resume_id VARCHAR2(36) PRIMARY KEY,
                candidate_id VARCHAR2(36),
                filename VARCHAR2(255),
                file_size NUMBER,
                mime_type VARCHAR2(100),
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resume_link VARCHAR2(500),
                CONSTRAINT fk_candidate_resume
                    FOREIGN KEY (candidate_id)
                    REFERENCES candidates(candidate_id)
            )';
        EXCEPTION
            WHEN OTHERS THEN
                IF SQLCODE = -955 THEN
                    NULL; -- Table already exists
                ELSE
                    RAISE;
                END IF;
        END;
        """)
        
        connection.commit()
        print("✅ Resumes metadata table created or already exists")
        return True
    except Exception as e:
        print(f"❌ Error creating resumes metadata table: {e}")
        return False
    finally:
        close_connection(connection)

def add_default_settings():
    """
    Add default settings to the settings table.
    
    Returns:
        bool: True if successful, False otherwise
    """
    connection = get_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        
        # Add default password expiry setting
        cursor.execute("""
        MERGE INTO settings s
        USING (SELECT 'password_expiry_days' as key, '30' as value FROM dual) d
        ON (s.key = d.key)
        WHEN MATCHED THEN
            UPDATE SET s.value = d.value, s.updated_at = CURRENT_TIMESTAMP
        WHEN NOT MATCHED THEN
            INSERT (key, value, updated_at)
            VALUES (d.key, d.value, CURRENT_TIMESTAMP)
        """)
        
        # Add default storage threshold setting
        cursor.execute("""
        MERGE INTO settings s
        USING (SELECT 'storage_threshold_percent' as key, '90' as value FROM dual) d
        ON (s.key = d.key)
        WHEN MATCHED THEN
            UPDATE SET s.value = d.value, s.updated_at = CURRENT_TIMESTAMP
        WHEN NOT MATCHED THEN
            INSERT (key, value, updated_at)
            VALUES (d.key, d.value, CURRENT_TIMESTAMP)
        """)
        
        connection.commit()
        print("✅ Default settings added")
        return True
    except Exception as e:
        print(f"❌ Error adding default settings: {e}")
        return False
    finally:
        close_connection(connection)

def add_default_users():
    """
    Add default users to the users table.
    
    Returns:
        bool: True if successful, False otherwise
    """
    connection = get_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        
        # Check if users table is empty
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]
        
        if count == 0:
            # Import hash_password from user_auth
            from user_auth import hash_password
            
            # Current timestamp
            now = datetime.now().isoformat()
            
            # Default users
            default_users = [
                ("ceo", "ceo@bluematrixit.com", "password123", "ceo", 0),
                ("interviewer", "interviewer@bluematrixit.com", "password123", "interviewer", 1),
                ("receptionist", "receptionist@bluematrixit.com", "password123", "receptionist", 1)
            ]
            
            # Add default users
            for username, email, password, role, force_reset in default_users:
                # Hash the password
                password_hash, _ = hash_password(password)
                
                # Generate a UUID for the user
                user_id = str(uuid.uuid4())
                
                # Insert the user
                cursor.execute("""
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
                    TO_TIMESTAMP(:last_password_change, 'YYYY-MM-DD"T"HH24:MI:SS.FF'),
                    :force_password_reset
                )
                """, {
                    "user_id": user_id,
                    "username": username,
                    "email": email,
                    "password_hash": password_hash,
                    "role": role,
                    "last_password_change": now,
                    "force_password_reset": force_reset
                })
            
            connection.commit()
            print(f"✅ Added {len(default_users)} default users")
        else:
            print("✅ Users already exist in the database")
        
        return True
    except Exception as e:
        print(f"❌ Error adding default users: {e}")
        return False
    finally:
        close_connection(connection)

def initialize_database():
    """
    Initialize the Oracle database by creating tables and adding default data.
    
    Returns:
        bool: True if successful, False otherwise
    """
    print("\n🔄 Initializing Oracle database...")
    
    # Create tables
    if not create_users_table():
        return False
    
    if not create_candidates_table():
        return False
    
    if not create_interviews_table():
        return False
    
    if not create_settings_table():
        return False
    
    if not create_activity_log_table():
        return False
    
    if not create_resumes_metadata_table():
        return False
    
    # Add default data
    if not add_default_settings():
        return False
    
    if not add_default_users():
        return False
    
    print("\n✅ Database initialization complete!")
    return True

if __name__ == "__main__":
    # Initialize the database
    initialize_database()