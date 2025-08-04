# Testing Instructions

To test the solution to the "streamlit is not recognized" error, follow these steps:

## Test 1: Running the Installation Script

1. Open a command prompt in the project directory (C:\Users\aarav\Desktop\BRV)
2. Run the installation script:
   ```
   .\install.bat
   ```
3. Expected behavior:
   - The script should check if Python is installed
   - Create or use the existing virtual environment (.venv)
   - Activate the virtual environment
   - Install all required packages from requirements.txt
   - Verify that Streamlit is installed, and install it specifically if needed
   - Display a success message and instructions to run the application

## Test 2: Running the Application

1. After successful installation, run the application:
   ```
   .\run_app.bat
   ```
2. Expected behavior:
   - The script should activate the virtual environment
   - Check if Streamlit is available in the PATH
   - If not, use the direct path to Streamlit in the virtual environment
   - Start the Streamlit application with main.py as the entry point
   - The Streamlit application should open in your default web browser

## Test 3: Direct Command Test (Optional)

This test demonstrates why the original error occurred:

1. Open a new command prompt (without activating the virtual environment)
2. Try to run Streamlit directly:
   ```
   streamlit run main.py
   ```
3. Expected behavior:
   - You should get the same error as before: "streamlit is not recognized as a command"
   - This confirms that Streamlit is only available in the virtual environment

## Verification

The solution is working correctly if:

1. Running `.\install.bat` completes without errors
2. Running `.\run_app.bat` starts the Streamlit application without the "streamlit is not recognized" error
3. The application opens in your web browser and functions as expected

## Troubleshooting

If you encounter issues:

1. **Error: "streamlit is not recognized"**
   - Make sure you're using `.\run_app.bat` to run the application, not direct commands
   - Try running `.\install.bat` again to reinstall all packages

2. **Error: "Failed to activate virtual environment"**
   - Make sure Python is installed and in your PATH
   - Try deleting the `.venv` directory and running `.\install.bat` again to create a fresh environment

3. **Error: "streamlit.exe not found in .venv\Scripts"**
   - Run `.\install.bat` again to ensure Streamlit is properly installed
   - Check if the `.venv\Scripts\streamlit.exe` file exists

4. **Application starts but shows errors**
   - Make sure all dependencies are installed by running `.\install.bat`
   - Check the console output for specific error messages

Remember that the application must always be run using `.\run_app.bat` to ensure the virtual environment is properly activated and Streamlit is available.