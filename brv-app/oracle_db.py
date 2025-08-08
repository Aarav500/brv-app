import os
import json
import uuid
import bcrypt
from datetime import datetime
import oracledb
from typing import Dict, List, Optional, Any, Tuple, Union
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Oracle DB config
DB_USER = os.getenv("ORACLE_USER")
DB_PASSWORD = os.getenv("ORACLE_PASSWORD")
DB_DSN = os.getenv("ORACLE_DSN")
WALLET_PATH = os.getenv("ORACLE_WALLET_LOCATION")
LIB_DIR = os.getenv("ORACLE_CLIENT_LIB_DIR")

# Required by oracledb to find tnsnames.ora
if WALLET_PATH:
    os.environ["TNS_ADMIN"] = WALLET_PATH

# Initialize Oracle Client early with env-driven configuration
print(f"🔍 Using Oracle Wallet Path: {WALLET_PATH}")
print(f"🔍 Using Oracle Client Lib Dir: {LIB_DIR}")
try:
    oracledb.init_oracle_client(lib_dir=LIB_DIR, config_dir=WALLET_PATH)
except Exception as e:
    # Avoid crashing import if already initialized or libs are not present.
    # In such cases, operations may still proceed in Thin mode where supported.
    if "already called" in str(e).lower():
        print("ℹ️ Oracle client already initialized.")
    else:
        print(f"⚠️ Could not initialize Oracle client: {e}")

# Import configuration from env_config.py
from env_config import (
    DB_CONFIG_FILE,
    get_db_config as env_get_db_config,
    update_db_config as env_update_db_config
)

# Global connection pool
connection_pool = None

def get_oracle_connection():
    """
    Get a direct connection to Oracle DB.
    
    Returns:
        oracledb.Connection: The database connection
    """
    try:
        conn = oracledb.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            dsn=DB_DSN,
            config_dir=WALLET_PATH,
            wallet_location=WALLET_PATH,
            wallet_password=None  # Only needed if wallet is password-protected
        )
        return conn
    except Exception as e:
        print(f"❌ Error connecting to Oracle DB: {e}")
        return None

def init_oracle_client():
    """
    Initialize the Oracle client using environment variables.
    Safe to call multiple times. This will not force thin mode.
    """
    try:
        wallet_dir = WALLET_PATH
        lib_dir = LIB_DIR
        print(f"🔍 Using Oracle Wallet Path: {wallet_dir}")
        print(f"🔍 Using Oracle Client Lib Dir: {lib_dir}")
        if wallet_dir:
            os.environ["TNS_ADMIN"] = wallet_dir
            print(f"TNS_ADMIN set to: {os.environ['TNS_ADMIN']}")
        oracledb.init_oracle_client(lib_dir=lib_dir, config_dir=wallet_dir)
        print("✅ Oracle client initialized successfully")
        return True
    except Exception as e:
        if "already called" in str(e).lower():
            print("ℹ️ Oracle client already initialized.")
            return True
        print(f"⚠️ Could not initialize Oracle client: {e}")
        return False

def get_db_config():
    """
    Get the current database configuration from the config file.
    If the file doesn't exist, create it with default values.
    
    Returns:
        dict: The database configuration
    """
    try:
        if os.path.exists(DB_CONFIG_FILE):
            with open(DB_CONFIG_FILE, 'r') as f:
                return json.load(f)
        else:
            # Create default config
            config = {
                "current_write_db": "brvdb1_low",
                "databases": ["brvdb1_low"]
            }
            with open(DB_CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
            return config
    except Exception as e:
        print(f"❌ Error reading/writing DB config: {e}")
        # Return default config if there's an error
        return {
            "current_write_db": "brvdb1_low",
            "databases": ["brvdb1_low"]
        }

def update_db_config(config):
    """
    Update the database configuration file.
    
    Args:
        config (dict): The new configuration
    """
    try:
        with open(DB_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print(f"❌ Error updating DB config: {e}")
        return False

def get_connection_pool(db_name=None):
    """
    Get or create a connection pool for the specified database.
    If no database is specified, use the current write database.
    
    Args:
        db_name (str, optional): The database name. Defaults to None.
        
    Returns:
        oracledb.ConnectionPool: The connection pool
    """
    global connection_pool
    
    if connection_pool is not None:
        return connection_pool
    
    try:
        # Initialize Oracle client if not already initialized (env-driven)
        init_oracle_client()
        
        # If no db_name is provided, use the current write database
        if db_name is None:
            config = get_db_config()
            db_name = config["current_write_db"]
        
        # Create the connection pool
        connection_pool = oracledb.create_pool(
            user=DB_USER,
            password=DB_PASSWORD,
            dsn=db_name,
            config_dir=WALLET_PATH,
            wallet_location=WALLET_PATH,
            wallet_password=None,  # Only needed if wallet is password-protected
            min=2,
            max=5,
            increment=1
        )
        
        return connection_pool
    except Exception as e:
        print(f"❌ Error creating connection pool for {db_name}: {e}")
        return None

def get_db_connection(db_name=None):
    """
    Get a connection from the pool for the specified database.
    If no database is specified, use the current write database.
    
    Args:
        db_name (str, optional): The database name. Defaults to None.
        
    Returns:
        oracledb.Connection: The database connection
    """
    try:
        pool = get_connection_pool(db_name)
        if pool:
            return pool.acquire()
        return None
    except Exception as e:
        print(f"❌ Error getting connection from pool: {e}")
        return None

def close_connection(connection):
    """
    Release a connection back to the pool.
    
    Args:
        connection: The connection to release
    """
    if connection:
        try:
            connection.close()
        except Exception as e:
            print(f"❌ Error closing connection: {e}")

def execute_query(query, params=None, db_name=None, fetchone=False, commit=False):
    """
    Execute a query on the specified database.
    
    Args:
        query (str): The SQL query to execute
        params (tuple, optional): The parameters for the query. Defaults to None.
        db_name (str, optional): The database name. Defaults to None.
        fetchone (bool, optional): Whether to fetch one result. Defaults to False.
        commit (bool, optional): Whether to commit the transaction. Defaults to False.
        
    Returns:
        list or dict: The query results
    """
    connection = get_db_connection(db_name)
    if not connection:
        return None
    
    try:
        cursor = connection.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        if fetchone:
            result = cursor.fetchone()
            if result:
                columns = [col[0] for col in cursor.description]
                return dict(zip(columns, result))
            return None
        else:
            results = cursor.fetchall()
            if results:
                columns = [col[0] for col in cursor.description]
                return [dict(zip(columns, row)) for row in results]
            return []
    except Exception as e:
        print(f"❌ Error executing query: {e}")
        return None
    finally:
        if commit and connection:
            connection.commit()
        close_connection(connection)

def execute_across_all_dbs(query, params=None, fetchone=False):
    """
    Execute a query across all databases and combine the results.
    
    Args:
        query (str): The SQL query to execute
        params (tuple, optional): The parameters for the query. Defaults to None.
        fetchone (bool, optional): Whether to fetch one result. Defaults to False.
        
    Returns:
        list or dict: The combined query results
    """
    config = get_db_config()
    all_results = []
    
    for db_name in config["databases"]:
        results = execute_query(query, params, db_name, fetchone)
        if fetchone and results:
            return results
        elif not fetchone and results:
            all_results.extend(results)
    
    return all_results if not fetchone else None

# Basic functions for the initial implementation
# More functions will be added as needed

def test_connection():
    """
    Test the connection to the Oracle database.
    
    Returns:
        bool: True if the connection is successful, False otherwise
    """
    try:
        print("\n🔄 Testing Oracle database connection...")
        
        # Initialize Oracle client if not already initialized
        init_oracle_client()
        
        # Get the current database configuration
        config = get_db_config()
        current_db = config["current_write_db"]
        
        # Test connection to the current write database
        connection = get_db_connection(current_db)
        if connection:
            print(f"\n✅ Successfully connected to Oracle database: {current_db}")
            
            # Test a simple query
            cursor = connection.cursor()
            cursor.execute("SELECT 1 FROM DUAL")
            result = cursor.fetchone()
            
            if result and result[0] == 1:
                print("✅ Query executed successfully")
                close_connection(connection)
                return True
            else:
                print("❌ Query execution failed")
                close_connection(connection)
                return False
        else:
            print(f"\n❌ Failed to connect to Oracle database: {current_db}")
            return False
    except Exception as e:
        print(f"\n❌ Error testing connection: {e}")
        return False