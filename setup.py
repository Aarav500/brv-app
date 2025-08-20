#!/usr/bin/env python3
"""
Blue Matrix IT - Applicant Management System Setup Script
Run this to initialize the entire system
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv


def check_requirements():
    """Check if all required packages are installed"""
    print("🔍 Checking requirements...")

    required_packages = [
        'streamlit', 'psycopg2', 'bcrypt', 'python-dotenv',
        'jwt', 'google-api-python-client', 'oauth2client'
    ]

    missing_packages = []
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"✅ {package}")
        except ImportError:
            missing_packages.append(package)
            print(f"❌ {package}")

    if missing_packages:
        print(f"\n⚠️  Missing packages: {', '.join(missing_packages)}")
        print("Run: pip install -r requirements.txt")
        return False

    print("✅ All requirements satisfied!")
    return True


def check_environment():
    """Check environment variables"""
    print("\n🔍 Checking environment configuration...")

    load_dotenv()

    required_vars = ['DATABASE_URL', 'SECRET_KEY']
    optional_vars = ['GOOGLE_SERVICE_ACCOUNT_FILE', 'GOOGLE_DRIVE_FOLDER_ID']

    all_good = True

    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: {'*' * min(len(value), 20)}...")
        else:
            print(f"❌ {var}: Not set")
            all_good = False

    for var in optional_vars:
        value = os.getenv(var)
        if value:
            print(f"🔶 {var}: {'*' * min(len(value), 20)}... (optional)")
        else:
            print(f"⚪ {var}: Not set (optional)")

    return all_good


def test_database():
    """Test database connection"""
    print("\n🔍 Testing database connection...")

    try:
        from db_postgres import get_conn
        conn = get_conn()

        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                version = cur.fetchone()[0]
                print(f"✅ Database connected: {version.split(',')[0]}")

        conn.close()
        return True

    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("\n💡 Check your DATABASE_URL in .env file")
        print("   Format: postgresql://user:pass@host:port/dbname")
        return False


def initialize_database():
    """Initialize database tables"""
    print("\n🔨 Initializing database...")

    try:
        from db_postgres import init_db
        init_db()
        print("✅ Database tables created successfully!")
        return True
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False


def create_users():
    """Create custom test users"""
    print("\n👥 Creating test users...")

    try:
        from seed_custom_users import create_custom_users, delete_default_users
        delete_default_users()
        create_custom_users()
        print("✅ Test users created successfully!")
        return True
    except Exception as e:
        print(f"❌ User creation failed: {e}")
        return False


def test_google_drive():
    """Test Google Drive configuration"""
    print("\n☁️  Testing Google Drive configuration...")

    try:
        from google_drive import test_google_drive_connection
        success, message = test_google_drive_connection()

        if success:
            print(f"✅ Google Drive: {message}")
        else:
            print(f"⚠️  Google Drive: {message}")
            print("   This is optional - the app will use local storage fallback")

        return True
    except Exception as e:
        print(f"⚠️  Google Drive test failed: {e}")
        print("   This is optional - continuing with local storage")
        return True


def create_directories():
    """Create necessary directories"""
    print("\n📁 Creating directories...")

    directories = ['logs', 'storage', 'storage/resumes']

    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✅ Created: {directory}")

    return True


def show_summary():
    """Show setup summary and next steps"""
    print("\n" + "=" * 60)
    print("🎉 SETUP COMPLETED SUCCESSFULLY!")
    print("=" * 60)

    print("\n📋 TEST ACCOUNTS:")
    print("-" * 40)

    accounts = [
        ("admin@bluematrixit.com", "AdminPass123!", "admin"),
        ("ceo@bluematrixit.com", "CeoPass123!", "ceo"),
        ("interviewer@bluematrixit.com", "IntPass123!", "interviewer"),
            ("receptionist@bluematrixit.com", "RecPass123!", "receptionist"),
        ("candidate@example.com", "CandPass123!", "candidate")
    ]

    for email, password, role in accounts:
        print(f"📧 {email}")
        print(f"🔑 {password}")
        print(f"👤 {role.upper()}")
        print("-" * 30)

    print("\n🚀 NEXT STEPS:")
    print("1. Run the application:")
    print("   streamlit run main.py")
    print("\n2. Open your browser to:")
    print("   http://localhost:8501")
    print("\n3. Login with any of the test accounts above")

    print("\n📚 FEATURES BY ROLE:")
    print("• CANDIDATE: Submit applications, upload CV")
    print("• RECEPTIONIST: Manage candidates, grant permissions")
    print("• INTERVIEWER: Schedule interviews, record results")
    print("• CEO/ADMIN: View statistics, manage users")

    google_file = os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE')
    if not google_file or not os.path.exists(google_file):
        print("\n⚠️  OPTIONAL: Google Drive Setup")
        print("   See GOOGLE_DRIVE_SETUP.md for CV cloud storage")

    print("\n" + "=" * 60)


def main():
    """Main setup process"""
    print("🚀 Blue Matrix IT - Applicant Management System Setup")
    print("=" * 60)

    steps = [
        ("Check Requirements", check_requirements),
        ("Check Environment", check_environment),
        ("Test Database", test_database),
        ("Initialize Database", initialize_database),
        ("Create Directories", create_directories),
        ("Create Users", create_users),
        ("Test Google Drive", test_google_drive)
    ]

    failed_steps = []

    for step_name, step_function in steps:
        print(f"\n📋 {step_name}...")
        try:
            if not step_function():
                failed_steps.append(step_name)
        except Exception as e:
            print(f"❌ {step_name} failed: {e}")
            failed_steps.append(step_name)

    if failed_steps:
        print(f"\n⚠️  Some steps failed: {', '.join(failed_steps)}")
        print("Please fix the issues above and run the setup again.")
        sys.exit(1)

    show_summary()


if __name__ == "__main__":
    main()