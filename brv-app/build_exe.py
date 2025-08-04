import os
import subprocess
import sys
import shutil

def build_executable():
    print("Building executable for BRV Applicant Management System...")

    # Create directories for build artifacts if they don't exist
    os.makedirs("build", exist_ok=True)
    os.makedirs("dist", exist_ok=True)

    # Ensure data and resumes directories exist
    os.makedirs("data/resumes", exist_ok=True)

    # Initialize the database with default users
    print("Initializing database...")
    subprocess.run([sys.executable, "init_db.py"], check=True)

    # Build the executable using PyInstaller
    print("Building executable with PyInstaller...")
    subprocess.run([
        sys.executable,
        "-m",
        "pyinstaller",
        "--name=BRV_Applicant_System",
        "--onefile",
        "--windowed",
        "--add-data=google_key.json;.",
        "--add-data=login.py;.",
        "--add-data=database.py;.",
        "--add-data=firebase_db.py;.",
        "--add-data=receptionist.py;.",
        "--add-data=interviewer.py;.",
        "--add-data=ceo.py;.",
        "--icon=NONE",  # Replace with actual icon path if available
        "main.py"
    ], check=True)

    # Copy necessary files to the dist directory
    print("Copying additional files...")
    # Copy Firebase service account key
    if os.path.exists("google_key.json"):
        shutil.copy("google_key.json", os.path.join("dist", "google_key.json"))

    # Create an empty data/resumes directory in the dist folder
    os.makedirs(os.path.join("dist", "data", "resumes"), exist_ok=True)

    print("Build completed successfully!")
    print("Executable can be found in the 'dist' directory.")

if __name__ == "__main__":
    build_executable()
