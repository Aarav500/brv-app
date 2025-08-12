import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# PostgreSQL configuration (Railway)
PGHOST = os.getenv("PGHOST")
PGPORT = os.getenv("PGPORT")
PGUSER = os.getenv("PGUSER")
PGPASSWORD = os.getenv("PGPASSWORD")
PGDATABASE = os.getenv("PGDATABASE")

# Google Drive Configuration
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")


def get_credentials():
    """
    Returns a dictionary with PostgreSQL database credentials.
    """
    return {
        "host": PGHOST,
        "port": PGPORT,
        "user": PGUSER,
        "password": PGPASSWORD,
        "database": PGDATABASE
    }


def validate_environment():
    """
    Checks if all required environment variables are set.
    """
    missing_vars = []
    required_vars = [
        "PGHOST", "PGPORT", "PGUSER", "PGPASSWORD", "PGDATABASE",
        "GOOGLE_DRIVE_FOLDER_ID", "GOOGLE_SERVICE_ACCOUNT_FILE"
    ]

    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        return False

    print("✅ All required environment variables are set.")
    return True


def get_google_drive_config():
    """
    Returns a dictionary with Google Drive configuration.
    """
    return {
        "folder_id": GOOGLE_DRIVE_FOLDER_ID,
        "service_account_file": GOOGLE_SERVICE_ACCOUNT_FILE
    }


if __name__ == "__main__":
    validate_environment()
