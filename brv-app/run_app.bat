@echo off
echo Starting BRV Applicant Management System...
echo.

REM Activate the virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate.bat

REM Check if activation was successful
if %ERRORLEVEL% NEQ 0 (
    echo Error: Failed to activate virtual environment.
    echo Please make sure you have set up the environment by running install.bat first.
    pause
    exit /b 1
)

REM Check if streamlit is installed
where streamlit >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Streamlit not found. Installing required packages...
    pip install -r requirements.txt
    if %ERRORLEVEL% NEQ 0 (
        echo Error: Failed to install required packages.
        pause
        exit /b 1
    )
)

echo.
echo Starting application...

REM Try to run streamlit from PATH first
where streamlit >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Streamlit not found in PATH, using direct path...
    if exist .venv\Scripts\streamlit.exe (
        echo Using streamlit.exe from .venv\Scripts
        .venv\Scripts\streamlit.exe run main.py
    ) else (
        echo Error: streamlit.exe not found in .venv\Scripts
        echo Please run install.bat to set up the environment properly.
        pause
        exit /b 1
    )
) else (
    echo Using streamlit from PATH
    streamlit run main.py
)

REM Deactivate the virtual environment when done
call deactivate

echo.
pause