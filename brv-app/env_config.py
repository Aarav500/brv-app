import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Base directory for the application
BASE_DIR = Path(__file__).resolve().parent

# Oracle Database Configuration
ORACLE_USER = os.getenv("ORACLE_USER", "admin")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD", "password")
ORACLE_DSN = os.getenv("ORACLE_DSN", "brv_db_1_high")
ORACLE_WALLET_LOCATION = os.getenv("ORACLE_WALLET_LOCATION", str(BASE_DIR / "wallet"))

# Google Drive Configuration
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", str(BASE_DIR / "google_key.json"))

# Database Configuration File
DB_CONFIG_FILE = str(BASE_DIR / "db_config.json")

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
                "current_write_db": "brv_db_1",
                "databases": ["brv_db_1"],
                "storage_usage": {
                    "brv_db_1": {
                        "total_gb": 20,
                        "used_gb": 0,
                        "last_checked": ""
                    }
                }
            }
            with open(DB_CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
            return config
    except Exception as e:
        print(f"❌ Error reading/writing DB config: {e}")
        # Return default config if there's an error
        return {
            "current_write_db": "brv_db_1",
            "databases": ["brv_db_1"],
            "storage_usage": {
                "brv_db_1": {
                    "total_gb": 20,
                    "used_gb": 0,
                    "last_checked": ""
                }
            }
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

def get_credentials():
    """
    Get all credentials as a dictionary.
    
    Returns:
        dict: All credentials
    """
    return {
        "oracle": {
            "user": ORACLE_USER,
            "password": ORACLE_PASSWORD,
            "dsn": ORACLE_DSN,
            "wallet_location": ORACLE_WALLET_LOCATION
        },
        "google_drive": {
            "folder_id": GOOGLE_DRIVE_FOLDER_ID,
            "service_account_file": GOOGLE_SERVICE_ACCOUNT_FILE
        }
    }

def validate_environment():
    """
    Validate that all required environment variables are set.
    
    Returns:
        tuple: (is_valid, missing_vars)
    """
    required_vars = [
        "ORACLE_USER",
        "ORACLE_PASSWORD",
        "ORACLE_DSN",
        "ORACLE_WALLET_LOCATION",
        "GOOGLE_DRIVE_FOLDER_ID",
        "GOOGLE_SERVICE_ACCOUNT_FILE"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    return len(missing_vars) == 0, missing_vars

def print_environment_status():
    """
    Print the status of the environment variables.
    """
    is_valid, missing_vars = validate_environment()
    
    if is_valid:
        print("✅ All required environment variables are set")
    else:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"  - {var}")
        print("\nPlease set these variables in your .env file or environment.")

if __name__ == "__main__":
    # Print environment status when run directly
    print_environment_status()
    
    # Print current database configuration
    config = get_db_config()
    print("\nCurrent Database Configuration:")
    print(f"  Current Write DB: {config['current_write_db']}")
    print(f"  Available Databases: {', '.join(config['databases'])}")
    
    # Print storage usage if available
    if "storage_usage" in config:
        print("\nStorage Usage:")
        for db, usage in config["storage_usage"].items():
            used_percent = (usage["used_gb"] / usage["total_gb"]) * 100 if usage["total_gb"] > 0 else 0
            print(f"  {db}: {usage['used_gb']:.2f} GB / {usage['total_gb']} GB ({used_percent:.1f}%)")
            if usage.get("last_checked"):
                print(f"    Last Checked: {usage['last_checked']}")