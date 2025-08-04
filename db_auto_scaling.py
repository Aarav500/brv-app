import os
import json
import time
from datetime import datetime
import traceback
from typing import Dict, List, Optional, Any, Tuple, Union

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
        oracledb.init_oracle_client(lib_dir=None)  # Force thin mode
        print("✅ Oracle client initialized successfully (thin mode)")
        return True
    except Exception as e:
        print(f"❌ Error initializing Oracle client: {e}")
        return False

def get_connection(db_name: str = None):
    """
    Get a connection to the Oracle database.
    
    Args:
        db_name (str, optional): The database name. If None, use the current write database.
        
    Returns:
        oracledb.Connection: The database connection
    """
    try:
        # Initialize Oracle client if not already initialized
        init_oracle_client()
        
        # Get the current database configuration
        config = get_db_config()
        current_db = db_name or config["current_write_db"]
        
        # Connect to the database
        connection = oracledb.connect(
            user=ORACLE_USER,
            password=ORACLE_PASSWORD,
            dsn=current_db
        )
        
        return connection
    except Exception as e:
        print(f"❌ Error connecting to Oracle database {db_name}: {e}")
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

def get_db_storage_usage(db_name: str) -> Tuple[bool, float, float, float]:
    """
    Get the storage usage of a database.
    
    Args:
        db_name (str): The database name
        
    Returns:
        Tuple[bool, float, float, float]: (success, used_gb, total_gb, percentage)
    """
    try:
        connection = get_connection(db_name)
        if not connection:
            return False, 0, 0, 0
        
        cursor = connection.cursor()
        
        # Query to get tablespace usage
        query = """
        SELECT
            df.tablespace_name,
            df.bytes / 1024 / 1024 / 1024 as total_gb,
            (df.bytes - fs.bytes) / 1024 / 1024 / 1024 as used_gb,
            ROUND(((df.bytes - fs.bytes) / df.bytes) * 100, 2) as percent_used
        FROM
            (SELECT tablespace_name, SUM(bytes) bytes FROM dba_data_files GROUP BY tablespace_name) df,
            (SELECT tablespace_name, SUM(bytes) bytes FROM dba_free_space GROUP BY tablespace_name) fs
        WHERE
            df.tablespace_name = fs.tablespace_name
        """
        
        try:
            cursor.execute(query)
            results = cursor.fetchall()
            
            # Sum up the usage across all tablespaces
            total_gb = 0
            used_gb = 0
            
            for row in results:
                total_gb += row[1]
                used_gb += row[2]
            
            # Calculate percentage
            percentage = (used_gb / total_gb * 100) if total_gb > 0 else 0
            
            return True, used_gb, total_gb, percentage
        except Exception as e:
            # If the above query fails (e.g., insufficient privileges), try a simpler approach
            print(f"⚠️ Could not get detailed tablespace usage: {e}")
            print("⚠️ Falling back to simplified storage check")
            
            # Query to get database size (simplified)
            query = """
            SELECT SUM(bytes) / 1024 / 1024 / 1024 as total_gb
            FROM user_segments
            """
            
            cursor.execute(query)
            result = cursor.fetchone()
            
            if result and result[0]:
                used_gb = result[0]
                # For Always Free tier, assume 20GB total
                total_gb = 20
                percentage = (used_gb / total_gb * 100)
                
                return True, used_gb, total_gb, percentage
            else:
                # If we still can't get the size, use the stored values
                config = get_db_config()
                if db_name in config.get("storage_usage", {}):
                    usage = config["storage_usage"][db_name]
                    used_gb = usage.get("used_gb", 0)
                    total_gb = usage.get("total_gb", 20)
                    percentage = (used_gb / total_gb * 100) if total_gb > 0 else 0
                    
                    return True, used_gb, total_gb, percentage
                else:
                    # Default values
                    return True, 0, 20, 0
    except Exception as e:
        print(f"❌ Error getting storage usage for {db_name}: {e}")
        traceback.print_exc()
        return False, 0, 0, 0
    finally:
        close_connection(connection)

def update_storage_usage():
    """
    Update the storage usage for all databases in the configuration.
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get the current database configuration
        config = get_db_config()
        
        # Initialize storage_usage if it doesn't exist
        if "storage_usage" not in config:
            config["storage_usage"] = {}
        
        # Update storage usage for each database
        for db_name in config["databases"]:
            success, used_gb, total_gb, percentage = get_db_storage_usage(db_name)
            
            if success:
                # Update the storage usage in the configuration
                config["storage_usage"][db_name] = {
                    "used_gb": used_gb,
                    "total_gb": total_gb,
                    "percentage": percentage,
                    "last_checked": datetime.now().isoformat()
                }
                
                print(f"✅ Updated storage usage for {db_name}: {used_gb:.2f} GB / {total_gb:.2f} GB ({percentage:.2f}%)")
            else:
                print(f"❌ Failed to update storage usage for {db_name}")
        
        # Save the updated configuration
        update_db_config(config)
        
        return True
    except Exception as e:
        print(f"❌ Error updating storage usage: {e}")
        traceback.print_exc()
        return False

def check_storage_threshold():
    """
    Check if any database has reached the storage threshold (90%).
    
    Returns:
        Tuple[bool, Optional[str]]: (threshold_reached, db_name)
    """
    try:
        # Update storage usage
        update_storage_usage()
        
        # Get the current database configuration
        config = get_db_config()
        
        # Check if any database has reached the threshold
        for db_name, usage in config.get("storage_usage", {}).items():
            percentage = usage.get("percentage", 0)
            
            if percentage >= 90:
                print(f"⚠️ Database {db_name} has reached the storage threshold: {percentage:.2f}%")
                return True, db_name
        
        return False, None
    except Exception as e:
        print(f"❌ Error checking storage threshold: {e}")
        traceback.print_exc()
        return False, None

def create_new_database(db_number: int) -> Tuple[bool, Optional[str]]:
    """
    Create a new Oracle Autonomous Database.
    
    Args:
        db_number (int): The database number (e.g., 2 for brv_db_2)
        
    Returns:
        Tuple[bool, Optional[str]]: (success, db_name)
    """
    try:
        # This function is a placeholder for the actual implementation
        # In a real implementation, you would use the Oracle Cloud API to create a new database
        # For now, we'll simulate the creation by adding the database to the configuration
        
        # Generate the new database name
        new_db_name = f"brv_db_{db_number}"
        
        print(f"🔄 Creating new Oracle Autonomous Database: {new_db_name}")
        print("⚠️ This is a simulated creation. In a real implementation, you would use the Oracle Cloud API.")
        
        # In a real implementation, you would:
        # 1. Use the Oracle Cloud API to create a new database
        # 2. Wait for the database to be provisioned
        # 3. Download the wallet files
        # 4. Configure the database with the required tables
        
        # For now, we'll just simulate a delay
        print("🔄 Simulating database creation...")
        time.sleep(2)
        
        print(f"✅ Database {new_db_name} created successfully")
        
        # Return the new database name
        return True, new_db_name
    except Exception as e:
        print(f"❌ Error creating new database: {e}")
        traceback.print_exc()
        return False, None

def initialize_new_database(db_name: str) -> bool:
    """
    Initialize a new database with the required tables.
    
    Args:
        db_name (str): The database name
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # This function is a placeholder for the actual implementation
        # In a real implementation, you would:
        # 1. Connect to the new database
        # 2. Create the required tables
        # 3. Copy any necessary data from the old database
        
        print(f"🔄 Initializing new database: {db_name}")
        print("⚠️ This is a simulated initialization. In a real implementation, you would create the required tables.")
        
        # For now, we'll just simulate a delay
        print("🔄 Simulating database initialization...")
        time.sleep(2)
        
        print(f"✅ Database {db_name} initialized successfully")
        
        return True
    except Exception as e:
        print(f"❌ Error initializing new database: {e}")
        traceback.print_exc()
        return False

def add_database_to_config(db_name: str) -> bool:
    """
    Add a new database to the configuration.
    
    Args:
        db_name (str): The database name
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get the current database configuration
        config = get_db_config()
        
        # Add the new database to the list if it's not already there
        if db_name not in config["databases"]:
            config["databases"].append(db_name)
        
        # Set the new database as the current write database
        config["current_write_db"] = db_name
        
        # Initialize storage usage for the new database
        if "storage_usage" not in config:
            config["storage_usage"] = {}
        
        config["storage_usage"][db_name] = {
            "used_gb": 0,
            "total_gb": 20,
            "percentage": 0,
            "last_checked": datetime.now().isoformat()
        }
        
        # Save the updated configuration
        update_db_config(config)
        
        print(f"✅ Database {db_name} added to configuration")
        print(f"✅ Current write database set to {db_name}")
        
        return True
    except Exception as e:
        print(f"❌ Error adding database to configuration: {e}")
        traceback.print_exc()
        return False

def auto_scale_database() -> bool:
    """
    Check if any database has reached the storage threshold and create a new one if needed.
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Check if any database has reached the threshold
        threshold_reached, db_name = check_storage_threshold()
        
        if threshold_reached:
            # Get the current database configuration
            config = get_db_config()
            
            # Get the number of databases
            db_count = len(config["databases"])
            
            # Create a new database
            success, new_db_name = create_new_database(db_count + 1)
            
            if success and new_db_name:
                # Initialize the new database
                if initialize_new_database(new_db_name):
                    # Add the new database to the configuration
                    if add_database_to_config(new_db_name):
                        print(f"✅ Auto-scaling successful: Created new database {new_db_name}")
                        return True
                    else:
                        print("❌ Failed to add new database to configuration")
                else:
                    print("❌ Failed to initialize new database")
            else:
                print("❌ Failed to create new database")
            
            return False
        else:
            print("✅ No database has reached the storage threshold")
            return True
    except Exception as e:
        print(f"❌ Error auto-scaling database: {e}")
        traceback.print_exc()
        return False

def get_current_write_db() -> str:
    """
    Get the current write database.
    
    Returns:
        str: The current write database name
    """
    config = get_db_config()
    return config["current_write_db"]

def get_all_db_names() -> List[str]:
    """
    Get all database names.
    
    Returns:
        List[str]: List of all database names
    """
    config = get_db_config()
    return config["databases"]

def write_to_latest_db(query: str, params: Dict[str, Any] = None, commit: bool = True) -> Any:
    """
    Execute a write query on the latest database.
    
    Args:
        query (str): The SQL query to execute
        params (Dict[str, Any], optional): The parameters for the query. Defaults to None.
        commit (bool, optional): Whether to commit the transaction. Defaults to True.
        
    Returns:
        Any: The query result
    """
    try:
        # Get the current write database
        db_name = get_current_write_db()
        
        # Get a connection to the database
        connection = get_connection(db_name)
        if not connection:
            return None
        
        try:
            cursor = connection.cursor()
            
            # Execute the query
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            # Commit if required
            if commit:
                connection.commit()
            
            # Return the result
            return cursor.rowcount
        finally:
            close_connection(connection)
    except Exception as e:
        print(f"❌ Error executing write query: {e}")
        traceback.print_exc()
        return None

def read_from_all_dbs(query: str, params: Dict[str, Any] = None, fetchone: bool = False) -> Any:
    """
    Execute a read query across all databases and combine the results.
    
    Args:
        query (str): The SQL query to execute
        params (Dict[str, Any], optional): The parameters for the query. Defaults to None.
        fetchone (bool, optional): Whether to fetch one result. Defaults to False.
        
    Returns:
        Any: The combined query results
    """
    try:
        # Get all database names
        db_names = get_all_db_names()
        
        # Initialize results
        all_results = []
        
        # Execute the query on each database
        for db_name in db_names:
            # Get a connection to the database
            connection = get_connection(db_name)
            if not connection:
                continue
            
            try:
                cursor = connection.cursor()
                
                # Execute the query
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                
                # Fetch the results
                if fetchone:
                    result = cursor.fetchone()
                    if result:
                        # Convert to dictionary
                        columns = [col[0] for col in cursor.description]
                        result_dict = dict(zip(columns, result))
                        
                        # Return the first result found
                        return result_dict
                else:
                    results = cursor.fetchall()
                    if results:
                        # Convert to list of dictionaries
                        columns = [col[0] for col in cursor.description]
                        result_dicts = [dict(zip(columns, row)) for row in results]
                        
                        # Add to all results
                        all_results.extend(result_dicts)
            finally:
                close_connection(connection)
        
        # Return the combined results
        return all_results if not fetchone else None
    except Exception as e:
        print(f"❌ Error executing read query: {e}")
        traceback.print_exc()
        return None if fetchone else []

def monitor_database_usage():
    """
    Monitor database usage and auto-scale if needed.
    This function should be called periodically.
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        print("🔄 Monitoring database usage...")
        
        # Update storage usage
        update_storage_usage()
        
        # Check if auto-scaling is needed
        return auto_scale_database()
    except Exception as e:
        print(f"❌ Error monitoring database usage: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Test the database auto-scaling
    monitor_database_usage()