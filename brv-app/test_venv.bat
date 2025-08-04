@echo off
echo Testing virtual environment activation...
echo.

REM Activate the virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate.bat

REM Check if activation was successful
if %ERRORLEVEL% NEQ 0 (
    echo Error: Failed to activate virtual environment.
    pause
    exit /b 1
)

REM Check if streamlit is available
echo Checking if streamlit is available...
where streamlit
if %ERRORLEVEL% NEQ 0 (
    echo Error: Streamlit not found in PATH after activating virtual environment.
    echo Trying to run streamlit directly from its location...
    if exist .venv\Scripts\streamlit.exe (
        echo Found streamlit.exe in .venv\Scripts
        .venv\Scripts\streamlit.exe --version
    ) else (
        echo Error: streamlit.exe not found in .venv\Scripts
    )
) else (
    echo Success: Streamlit found in PATH.
)

REM Deactivate the virtual environment
call deactivate

echo.
pause