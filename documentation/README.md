# BRV Applicant Management System

A desktop application for managing walk-in applicants, interviews, and hiring processes with integrated cloud storage.

## Overview

The BRV Applicant Management System is designed to streamline the process of managing walk-in applicants for a company. It provides four different views:

1. **Candidate View**: For applicants to fill out their information and upload their CV directly in the app.
2. **Receptionist View**: For managing walk-in applicants, allowing form editing, and viewing all candidates.
3. **Interviewer View**: For scheduling and conducting interviews, recording results, and making hiring decisions.
4. **CEO View**: For viewing overall statistics, applicant data, and interview results.

### Current Setup

The BRV Applicant Management System now uses:

- **Planetscale (MySQL)**: for user logins and candidate data
- **Google Drive**: for storing CVs
- **Streamlit**: as the interface connected to both

For detailed setup instructions, see [Planetscale and Google Drive Setup Guide](PLANETSCALE_GOOGLE_DRIVE_SETUP.md).

## Features

### Candidate Features
- Direct in-app form filling (no more Google Forms)
- CV upload from local PC to cloud storage
- Auto-generated Candidate ID from MySQL database
- Ability to edit application with Receptionist assistance

### Receptionist Features
- Allow candidates to edit their application using Candidate ID + Name verification
- View all candidates with filtering options
- Manual form entry for walk-in applicants
- Resume management through cloud storage
- Candidate profile management

### Interviewer Features
- View scheduled interviews
- Access applicant information and download CVs from cloud storage
- Record interview notes and results (pass/fail/on hold)
- View past interview history

### CEO Features
- Dashboard with applicant statistics
- Comprehensive view of all candidates
- Interview result analysis
- Filtering and searching capabilities

## Installation

### Prerequisites
- Windows operating system
- Internet connection (required for cloud services)
- Database access:
  - Planetscale account (recommended) or
  - MySQL server (version 5.7 or higher) installed locally
- Cloud storage:
  - Google account with Google Drive access (recommended) or
  - Other cloud storage account (Supabase, AWS S3, etc.)
- Google Cloud project with Drive API enabled (for Google Drive storage)

### Database Setup (Planetscale)

The application now uses Planetscale, a MySQL-compatible database platform, for storing user logins and candidate data.

#### Option 1: Use Planetscale (Recommended)

Follow the detailed instructions in the [Planetscale and Google Drive Setup Guide](PLANETSCALE_GOOGLE_DRIVE_SETUP.md#1-planetscale-setup) to:

1. Create a Planetscale account
2. Create a database
3. Set up connection parameters
4. Configure environment variables
5. Initialize the database

#### Option 2: Use Local MySQL (Alternative)

If you prefer to use a local MySQL installation:

1. Install MySQL Server from [https://dev.mysql.com/downloads/mysql/](https://dev.mysql.com/downloads/mysql/)
2. During installation:
   - Set the root password to "password" (or update the connection details in mysql_db.py and init_db.py)
   - Enable TCP/IP networking and set the port to 3306
   - Configure MySQL to start automatically with Windows
3. Make sure the MySQL service is running:
   - Press Win + R → type `services.msc`
   - Find MySQL (or MySQL80) → Check if it's running
   - If not running, right-click → Start
4. Test your MySQL connection:
   - Open Command Prompt and run: `mysql -u root -p -h 127.0.0.1 -P 3306`
   - Enter your password when prompted
5. Run `python init_db.py` to create the necessary database and tables

### Troubleshooting Database Connection

1. **Testing Connection**:
   - Run `python -c "import mysql_db; mysql_db.test_connection()"` to test the database connection
   - This will show detailed information about your connection status

2. **Planetscale Connection Issues**:
   - Verify that your environment variables are set correctly
   - Check if your IP address is allowed in Planetscale's network settings
   - Ensure that your Planetscale database is active

3. **Local MySQL Connection Issues**:
   - Check if MySQL service is running in services.msc
   - Verify your credentials in mysql_db.py and init_db.py
   - Ensure TCP/IP networking is enabled on port 3306

4. **Fallback to SQLite**:
   - The application will automatically fall back to SQLite if MySQL/Planetscale connection fails
   - However, SQLite has no default users, so login will fail
   - Always ensure your database is properly configured for full functionality

### Cloud Storage Setup (Google Drive for CVs)

The application now uses Google Drive for storing and retrieving CV files.

#### Option 1: Use Google Drive (Recommended)

Follow the detailed instructions in the [Planetscale and Google Drive Setup Guide](PLANETSCALE_GOOGLE_DRIVE_SETUP.md#2-google-drive-setup) to:

1. Create a Google Cloud project
2. Create a service account
3. Create a Google Drive folder
4. Configure environment variables

#### Option 2: Use Other Cloud Storage (Alternative)

If you prefer to use a different cloud storage provider:

1. Create an account with your preferred cloud storage provider:
   - [Supabase](https://supabase.com/)
   - [AWS S3](https://aws.amazon.com/s3/)
   - [Google Cloud Storage](https://cloud.google.com/storage)
2. Create a storage bucket for candidate CVs
3. Modify `cloud_storage.py` to work with your chosen provider
4. Update the configuration with your credentials

### Testing Cloud Storage

Run the following command to test the Google Drive connection:

```
python -c "import cloud_storage; cloud_storage.init_storage()"
```

You should see a message indicating that the Google Drive storage was initialized successfully.

### Installation Steps
1. Download the latest release from the releases page
2. Run the installer (BRV_Applicant_System.exe)
3. Follow the on-screen instructions to complete the installation

### Development Setup
If you want to set up the development environment:

1. Clone this repository
2. Create a virtual environment:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   ```
3. Install dependencies (choose one method):

   **Method 1: Using the installation script (recommended)**
   ```
   install.bat
   ```
   Or run the Python installation script directly:
   ```
   python install_packages.py
   ```

   **Method 2: Using pip directly**
   ```
   pip install -r requirements.txt
   ```
4. Initialize the MySQL database:
   ```
   python init_db.py
   ```
5. Run the application:
   ```
   streamlit run app.py
   ```
   or
   ```
   run_app.bat
   ```

## Usage

### Default Login Credentials

The system comes with three default user accounts:

| Username                      | Password    | Role         |
|-------------------------------|-------------|--------------|
| ceo@bluematrixit.com          | password123 | CEO          |
| interviewer@bluematrixit.com  | password123 | Interviewer  |
| receptionist@bluematrixit.com | password123 | Receptionist |

**Note**: For security reasons, please change these passwords after the first login in a production environment.

### Candidate Access

Candidates can access the system in two ways:

1. **Without an Account**: Candidates can submit applications without creating an account. The form is publicly accessible for new applicants to submit their information.

2. **With an Account**: Candidates can register for an account, which allows them to:
   - Log in to view their application status
   - Edit their application information
   - Upload a new CV
   - Track their interview status

#### Default Candidate Credentials

For testing purposes, the system includes a default candidate account:

| Username               | Password    | Role      |
|------------------------|-------------|-----------|
| candidate@example.com  | password123 | Candidate |

**Note**: For security reasons, please change this password in a production environment.

### Workflow

1. **Candidate Application**:
   - Candidate fills out the application form directly in the app
   - System auto-generates a unique Candidate ID from the MySQL database
   - Candidate uploads their CV from their local PC
   - CV is stored in cloud storage and linked to the Candidate ID
   - Candidate receives confirmation with their Candidate ID for future reference

2. **Application Editing**:
   - If a candidate needs to edit their application, they visit the receptionist
   - Receptionist verifies the candidate using Candidate ID + Name
   - If verified, the candidate can edit their information and re-upload their CV
   - All changes are stored in the MySQL database with the same Candidate ID

3. **Walk-in Candidates**:
   - Receptionist can create a new application for walk-in candidates
   - System generates a Candidate ID for the walk-in candidate
   - Receptionist helps the candidate fill out the form and upload their CV
   - All data is stored in the MySQL database with proper linking

4. **Interview Process**:
   - Interviewer views all candidates and their information
   - Interviewer can download CVs directly from cloud storage
   - During the interview, the interviewer can access all candidate details
   - After the interview, results (pass/fail/on hold) are recorded
   - Notes and feedback are stored in the system

5. **Management Overview**:
   - CEO can view statistics on candidates and interviews
   - Detailed information on each candidate is available
   - Interview results can be analyzed and filtered
   - All data is retrieved from the central MySQL database

## Building the Executable

To build the standalone executable:

1. Ensure you have all dependencies installed (including PyInstaller):
   ```
   install.bat
   ```
   Or:
   ```
   pip install -r requirements.txt
   ```
2. Run the build script:
   ```
   python build_exe.py
   ```
3. The executable will be created in the `dist` directory

## Project Structure

```
BRV/
├── app.py                    # Main Streamlit app controller
├── init_db.py                # MySQL DB schema + init code
├── build_exe.py              # .exe bundler
├── requirements.txt          # Python dependencies
├── mysql_db.py               # All MySQL connection + CRUD logic
├── cloud_storage.py          # Upload/download CVs to cloud (e.g., Supabase/AWS)
├── candidate_view.py         # Candidate fills form + uploads CV
├── reception_view.py         # Receptionist unlocks/edit candidate form
├── interviewer.py            # View candidate info + CVs
├── ceo.py                    # Admin view of all users and candidates
├── auth.py                   # Handles login/authentication with roles from MySQL
├── session_utils.py          # Session management for logged-in users
├── resumes/                  # Local cache for CVs before upload
├── dist/                     # .exe build output
└── build/                    # Build artifacts
```

## MySQL Integration

In the updated architecture, MySQL is used for all data storage, including user authentication, candidate data, and CV metadata. This provides several benefits:

- Centralized data storage in a single database
- Simplified data management and querying
- Robust relational database capabilities
- Improved data integrity and consistency

### Database Schema

The MySQL database consists of two main tables:

1. **users table**
   - id (INT, Primary Key, Auto Increment)
   - email (VARCHAR, Unique)
   - password_hash (VARCHAR)
   - role (ENUM: 'ceo', 'interviewer', 'receptionist')
   - created_at (TIMESTAMP)

2. **candidates table**
   - id (INT, Primary Key, Auto Increment)
   - name (VARCHAR)
   - email (VARCHAR)
   - phone (VARCHAR, Optional)
   - form_data (JSON) - Stores form field data
   - resume_url (TEXT) - CV stored in cloud (linked)
   - created_by (VARCHAR)
   - updated_at (TIMESTAMP)

### Using MySQL in the Application

The application uses MySQL for:
- User authentication and role management
- Storing complete candidate form data
- Tracking candidate access for editing purposes
- Storing metadata for uploaded CVs

### User Authentication

MySQL handles all user authentication:

```python
from mysql_db import authenticate_user

# Authenticate a user
email = "ceo@bluematrixit.com"  # Example email
password = "password123"        # Example password
user = authenticate_user(email, password)
if user:
    # User authenticated successfully
    user_role = user.get("role")  # "ceo", "interviewer", or "receptionist"
```

## Cloud Storage Integration

The application uses cloud storage (Supabase, AWS S3, or Google Cloud Storage) for storing CVs, with metadata stored in MySQL. This provides several benefits:

- Secure and scalable file storage for CVs
- Improved data organization with direct linking between candidates and their CVs
- Better performance for large files

### Using Cloud Storage in the Application

The application uses cloud storage for:
- Storing and retrieving CV files
- Maintaining relationships between candidates and their documents

### CV Upload and Retrieval

```python
import streamlit as st
from cloud_storage import upload_cv
from mysql_db import update_candidate

# Upload a CV and link it to a candidate
candidate_id = 123  # Example candidate ID from MySQL
uploaded_file = st.file_uploader("Upload CV")
if uploaded_file:
    cv_url = upload_cv(candidate_id, uploaded_file.read(), uploaded_file.name)
    # Update the candidate record with the CV URL
    update_candidate(candidate_id, {'cv_url': cv_url})

# Later, download the CV
from cloud_storage import download_cv
cv_content = download_cv(cv_url)  # Returns the CV file content as bytes
```

## Troubleshooting

If you encounter the error "streamlit is not recognized as a command":

1. **Always use `.\run_app.bat`** to start the application, not direct commands
   - In PowerShell, you must use `.\run_app.bat` (with the dot-slash prefix)
   - In Command Prompt, you can use `run_app.bat` directly

2. **Reinstall if needed**:
   - If you're still having issues, run `.\install.bat` again to reinstall all packages
   - The script will verify that Streamlit is properly installed

3. **Check your environment**:
   - The application uses a virtual environment (.venv) where Streamlit is installed
   - If the virtual environment is corrupted, delete the `.venv` folder and run `.\install.bat` again

4. **Path issues**:
   - The updated `run_app.bat` will automatically use the direct path to Streamlit if it's not found in PATH
   - This ensures the application works even if there are PATH-related issues

## Future Enhancements

- Email notifications for interview scheduling
- Integration with calendar systems
- Advanced reporting and analytics
- Custom form builder for application forms
- Mobile application for candidates
- API integration with job boards
- Automated CV parsing and skills extraction
- Multi-language support for international candidates

## License

This project is proprietary and confidential. Unauthorized copying, distribution, or use is strictly prohibited.

## Contact

For support or inquiries, please contact [your-email@example.com](mailto:your-email@example.com).