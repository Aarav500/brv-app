@echo off
echo ===================================================
echo BRV Applicant Management System - New Location Setup
echo ===================================================
echo.
echo This script will set up the BRV Applicant Management System in its new location.
echo.
echo Step 1: Installing required packages...
python install_packages.py
echo.
echo Step 2: Checking if database initialization is needed...
python -c "from firebase_db import init_db, init_users; init_db(); init_users()"
echo.
echo ===================================================
echo Setup Complete!
echo.
echo To run the application:
echo 1. Double-click on run_app.bat
echo    OR
echo 2. Execute "streamlit run main.py" in the command line
echo ===================================================
echo.
pause