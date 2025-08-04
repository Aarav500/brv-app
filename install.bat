@echo off
echo Installing packages for BRV Applicant Management System...
echo.

REM Check if Python is installed
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Error: Python is not installed or not in the PATH.
    echo Please install Python and try again.
    pause
    exit /b 1
)

REM Check if virtual environment exists, create if not
if not exist .venv (
    echo Creating virtual environment...
    python -m venv .venv
    if %ERRORLEVEL% NEQ 0 (
        echo Error: Failed to create virtual environment.
        pause
        exit /b 1
    )
)

REM Activate the virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate.bat

REM Check if activation was successful
if %ERRORLEVEL% NEQ 0 (
    echo Error: Failed to activate virtual environment.
    pause
    exit /b 1
)

REM Install packages
echo Installing required packages...

REM First try using install_packages.py
python install_packages.py
if %ERRORLEVEL% NEQ 0 (
    echo Warning: install_packages.py failed, trying direct pip install...
    
    REM Check if requirements.txt exists
    if not exist requirements.txt (
        echo Error: requirements.txt not found.
        pause
        exit /b 1
    )
    
    REM Install packages directly with pip
    pip install -r requirements.txt
    if %ERRORLEVEL% NEQ 0 (
        echo Error: Failed to install required packages.
        pause
        exit /b 1
    )
)

REM Verify that streamlit is installed
where streamlit >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Warning: Streamlit not found in PATH after installation.
    echo Installing streamlit specifically...
    pip install streamlit==1.22.0
    if %ERRORLEVEL% NEQ 0 (
        echo Error: Failed to install Streamlit.
        pause
        exit /b 1
    )
)

echo All packages installed successfully!

REM Deactivate the virtual environment
call deactivate

echo.
echo Installation completed successfully!
echo.
echo To run the application, double-click on run_app.bat or execute "run_app.bat" in the command prompt.
echo.
pause