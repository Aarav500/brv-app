# BRV Applicant Management System - New Location Setup Guide

This guide will help you set up the BRV Applicant Management System after changing its location on your computer.

## Prerequisites

- Python 3.7 or higher installed on your system
- Internet connection to download required packages

## Setup Process

### Automatic Setup (Recommended)

1. Double-click on the `setup_new_location.bat` file
2. The script will:
   - Install all required Python packages
   - Initialize the Firebase database
   - Set up default users if needed

### Manual Setup

If the automatic setup doesn't work, you can follow these steps manually:

1. Open a command prompt in the project directory
2. Install required packages:
   ```
   python install_packages.py
   ```
   or
   ```
   pip install -r requirements.txt
   ```
3. Initialize the database:
   ```
   python -c "from firebase_db import init_db, init_users; init_db(); init_users()"
   ```

## Running the Application

After setup is complete, you can run the application using one of these methods:

1. Double-click on `run_app.bat`
2. Or run the following command in the project directory:
   ```
   streamlit run main.py
   ```

## Important Files

- `google_key.json` - Firebase credentials file (must be in the project root directory)
- `requirements.txt` - List of required Python packages
- `main.py` - Main application entry point
- `run_app.bat` - Script to run the application

## Troubleshooting

### Missing Dependencies

If you encounter errors about missing packages, try running:
```
pip install -r requirements.txt --force-reinstall
```

### Firebase Connection Issues

If you have issues connecting to Firebase:
1. Ensure `google_key.json` is in the project root directory
2. Check your internet connection
3. Verify that the Firebase project is still active

### Streamlit Issues

If Streamlit fails to start:
1. Try reinstalling it: `pip install streamlit==1.22.0 --force-reinstall`
2. Make sure port 8501 is not in use by another application

## Default Users

The system comes with these default users:
- CEO: nikhil.shah@bluematrixit.com (password: 345)
- Receptionist: reception@bluematrixit.com (password: 123)
- Interviewer: interview@bluematrixit.com (password: 234)

You will be prompted to change these passwords on first login.