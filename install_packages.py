import subprocess
import sys
import os

def install_packages():
    """
    Install all required packages for the BRV Applicant Management System.
    """
    print("Installing required packages for BRV Applicant Management System...")
    
    # Check if requirements.txt exists
    if not os.path.exists("requirements.txt"):
        print("Error: requirements.txt not found.")
        return False
    
    try:
        # Install packages from requirements.txt
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("All packages installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error installing packages: {e}")
        return False

if __name__ == "__main__":
    install_packages()