# BRV Applicant Management System: Updated Architecture Details

## Table of Contents
1. [System Overview](#system-overview)
2. [Component Architecture](#component-architecture)
3. [Database Architecture](#database-architecture)
4. [Authentication Flow](#authentication-flow)
5. [Cloud Integration](#cloud-integration)
6. [Auto-Scaling Architecture](#auto-scaling-architecture)
7. [Deployment Architecture](#deployment-architecture)
8. [Migration Status](#migration-status)

## System Overview

The BRV Applicant Management System is a comprehensive solution for managing walk-in applicants, interviews, and hiring processes. The system has recently undergone a significant architectural change, migrating from a combination of Firebase, Planetscale (MySQL), and SQLite to Oracle Cloud Autonomous Database while maintaining Google Drive integration for resume storage.

### Core Functionality

The system provides four distinct user interfaces:

1. **Candidate View**: Allows applicants to fill out their information and upload their CV directly in the application
2. **Receptionist View**: Enables management of walk-in applicants, form editing, and viewing all candidates
3. **Interviewer View**: Facilitates scheduling and conducting interviews, recording results, and making hiring decisions
4. **CEO View**: Provides overall statistics, applicant data, and interview results

### Current Architecture

The updated architecture uses:

- **Oracle Cloud Autonomous Database**: For all data storage (users, candidates, interviews)
- **Google Drive**: For storing and retrieving CV files
- **Streamlit**: As the user interface framework
- **Python**: As the primary programming language

### Key Benefits of the New Architecture

- **Centralized Data Storage**: All data now stored in Oracle Cloud
- **Improved Security**: Implemented bcrypt password hashing
- **Auto-Scaling**: Automatic database creation when storage reaches 90% capacity
- **Simplified Architecture**: Removed dependencies on multiple database systems
- **Maintained Functionality**: Preserved all existing features while improving the backend

## Component Architecture

The system is composed of several key components that work together to provide the complete functionality:

### Core Components

1. **Database Layer**
   - `oracle_db.py`: Core database connection and query execution
   - `db_auto_scaling.py`: Monitors storage and creates new databases when needed
   - `env_config.py`: Manages environment variables and configuration

2. **Authentication System**
   - `auth.py`: Handles user login, session management, and password resets
   - `user_auth.py`: Manages user accounts and authentication with Oracle

3. **Candidate Management**
   - `oracle_candidates.py`: CRUD operations for candidate data
   - `candidate_view.py`: UI for candidates to submit applications
   - `reception_view.py`: UI for receptionists to manage candidates

4. **Interview Management**
   - `interviewer.py`: UI for interviewers to manage interviews
   - `schedule_interview.py`: Functionality for scheduling interviews

5. **Administration**
   - `ceo.py`: UI for CEO to view statistics and reports
   - `admin.py`: Administrative functions

6. **Cloud Storage**
   - `cloud_storage.py`: Handles CV file storage in Google Drive
   - `google_drive.py`: Google Drive API integration

7. **Application Entry Points**
   - `app.py`: Main Streamlit application
   - `main.py`: Alternative entry point used by run_app.bat

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Interfaces                           │
├───────────────┬───────────────┬───────────────┬─────────────────┤
│ Candidate View│Receptionist   │ Interviewer   │   CEO View      │
│ candidate_view│reception_view │ interviewer.py│   ceo.py        │
└───────┬───────┴───────┬───────┴───────┬───────┴────────┬────────┘
        │               │               │                │
        ▼               ▼               ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Business Logic                              │
├───────────────┬───────────────┬───────────────┬─────────────────┤
│ Authentication│ Candidate     │ Interview     │ Administration  │
│ auth.py       │ Management    │ Management    │ admin.py        │
│ user_auth.py  │ oracle_cand...│ schedule_int..│                 │
└───────┬───────┴───────┬───────┴───────┬───────┴────────┬────────┘
        │               │               │                │
        ▼               ▼               ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Data Access Layer                           │
├───────────────────────────────┬───────────────────────────────┐ │
│     Database Access           │      Cloud Storage            │ │
│     oracle_db.py              │      cloud_storage.py         │ │
│     db_auto_scaling.py        │      google_drive.py          │ │
└───────────────────────────────┴───────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
        │                                       │
        ▼                                       ▼
┌─────────────────────┐             ┌─────────────────────────┐
│  Oracle Cloud       │             │      Google Drive       │
│  Autonomous DB      │             │      (CV Storage)       │
└─────────────────────┘             └─────────────────────────┘
```

## Database Architecture

The system uses Oracle Cloud Autonomous Database for all data storage, with a well-defined schema to support all functionality.

### Database Schema

#### Users Table
```sql
CREATE TABLE users (
    user_id VARCHAR2(36) PRIMARY KEY,
    username VARCHAR2(100) UNIQUE,
    email VARCHAR2(255) UNIQUE,
    password_hash VARCHAR2(255),
    role VARCHAR2(50),
    last_password_change TIMESTAMP,
    force_password_reset NUMBER(1)
);
```

#### Candidates Table
```sql
CREATE TABLE candidates (
    candidate_id VARCHAR2(36) PRIMARY KEY,
    full_name VARCHAR2(255),
    email VARCHAR2(255),
    phone VARCHAR2(20),
    additional_phone VARCHAR2(20),
    dob DATE,
    caste VARCHAR2(50),
    sub_caste VARCHAR2(50),
    marital_status VARCHAR2(50),
    qualification VARCHAR2(100),
    work_experience VARCHAR2(100),
    referral VARCHAR2(255),
    resume_link VARCHAR2(500),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    interview_status VARCHAR2(50)
);
```

#### Interviews Table
```sql
CREATE TABLE interviews (
    interview_id VARCHAR2(36) PRIMARY KEY,
    candidate_id VARCHAR2(36),
    interviewer_id VARCHAR2(36),
    scheduled_time TIMESTAMP,
    feedback CLOB,
    status VARCHAR2(50),
    result VARCHAR2(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_candidate
        FOREIGN KEY (candidate_id)
        REFERENCES candidates(candidate_id),
    CONSTRAINT fk_interviewer
        FOREIGN KEY (interviewer_id)
        REFERENCES users(user_id)
);
```

#### Settings Table
```sql
CREATE TABLE settings (
    key VARCHAR2(255) PRIMARY KEY,
    value CLOB,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Database Connection

The system uses the `oracledb` Python package to connect to Oracle Cloud Autonomous Database. The connection is managed through the `oracle_db.py` module, which provides functions for:

- Establishing secure connections using Oracle wallet
- Connection pooling for efficiency
- Query execution with parameter binding
- Error handling and fallback mechanisms

## Authentication Flow

The authentication system has been completely redesigned to use Oracle Database and bcrypt for password hashing.

### Authentication Process

1. User enters username/email and password in the login form
2. System retrieves user from Oracle database
3. Password is verified using bcrypt
4. If password is correct, system checks if password reset is required
5. If reset is required, user is redirected to password reset page
6. Otherwise, user is authenticated and granted access based on role
7. Session is established with appropriate permissions

### Password Security

- All passwords are hashed using bcrypt
- Passwords expire after a configurable period (default: 30 days)
- Administrators can force users to reset their passwords
- Password strength validation is enforced

### Role-Based Access Control

Different roles have different access levels:

- **CEO**: Access to all data and reports
- **Interviewer**: Access to candidate data and interview management
- **Receptionist**: Access to candidate management and form editing
- **Candidate**: Access to their own application only

## Cloud Integration

The system integrates with cloud services for data storage and file management.

### Oracle Cloud Integration

- **Autonomous Database**: Used for all structured data storage
- **Wallet Authentication**: Secure connection using Oracle wallet
- **Auto-Scaling**: Automatic database creation when storage reaches 90% capacity

### Google Drive Integration

- **Resume Storage**: All resumes are stored in Google Drive
- **Service Account Authentication**: Secure access using Google service account
- **Folder Management**: Automatic folder creation and organization
- **File Operations**: Upload, download, and deletion of resume files

### Integration Flow

1. **Resume Upload**:
   - User uploads resume file
   - System uploads file to Google Drive using service account
   - Google Drive returns a link to the file
   - Link is stored in Oracle database associated with candidate

2. **Resume Download**:
   - User requests to view a resume
   - System retrieves link from Oracle database
   - System downloads file from Google Drive
   - File is presented to the user

## Auto-Scaling Architecture

The system includes an innovative auto-scaling solution that automatically creates new databases when the current one reaches 90% capacity.

### Auto-Scaling Process

1. **Monitoring**: System regularly checks storage usage of all databases
2. **Threshold Detection**: When a database reaches 90% capacity, auto-scaling is triggered
3. **Database Creation**: A new database is created with the same schema
4. **Configuration Update**: The system configuration is updated to include the new database
5. **Query Routing**: New writes are directed to the new database, reads span all databases

### Database Configuration Management

The system uses a configuration file (`db_config.json`) to track all databases:

```json
{
  "current_write_db": "brv_db_2",
  "databases": ["brv_db_1", "brv_db_2"],
  "storage_usage": {
    "brv_db_1": {
      "total_gb": 20,
      "used_gb": 18.5,
      "percentage": 92.5,
      "last_checked": "2025-07-28T16:03:45.123456"
    },
    "brv_db_2": {
      "total_gb": 20,
      "used_gb": 2.3,
      "percentage": 11.5,
      "last_checked": "2025-07-28T16:03:45.123456"
    }
  }
}
```

### Query Routing

- **Write Operations**: Directed to the current write database (newest)
- **Read Operations**: Executed across all databases and results combined
- **Consistency**: Ensures all data is accessible regardless of which database it's stored in

## Deployment Architecture

The system is designed for easy deployment in various environments.

### Local Deployment

For development and testing:

1. Clone the repository
2. Create a virtual environment
3. Install dependencies using `install.bat` or `pip install -r requirements.txt`
4. Configure environment variables in `.env` file
5. Initialize the database using `python init_db.py`
6. Run the application using `run_app.bat` or `streamlit run app.py`

### Production Deployment

For production environments:

1. Set up Oracle Cloud Autonomous Database
2. Configure Google Drive API and service account
3. Deploy the application on a server with Python installed
4. Set up environment variables for production
5. Use a process manager (e.g., Supervisor) to keep the application running
6. Optionally, set up a reverse proxy (e.g., Nginx) for HTTPS support

### Executable Deployment

For desktop deployment:

1. Build the executable using `python build_exe.py`
2. Distribute the executable to users
3. Configure the application to connect to the production database
4. Ensure users have internet access for cloud services

## Migration Status

The migration from the previous architecture (Firebase, Planetscale, SQLite) to Oracle Cloud is in progress. The following components have been fully migrated:

- ✅ Database schema and structure
- ✅ Authentication system
- ✅ Candidate management
- ✅ Resume storage integration
- ✅ Auto-scaling functionality

The following components are still in transition:

- ⚠️ User interfaces (still reference mysql_db in some places)
- ⚠️ Data migration from old systems
- ⚠️ Testing and validation

### Migration Checklist

- [x] Create Oracle Cloud account
- [x] Provision Autonomous Database (brv_db_1)
- [x] Download and configure wallet files
- [x] Set up environment variables
- [x] Initialize database schema
- [x] Test database connection
- [x] Verify user authentication
- [x] Test candidate data management
- [x] Confirm Google Drive integration
- [x] Validate database auto-scaling
- [ ] Update application interfaces
- [ ] Remove legacy database code
- [ ] Final testing of all functionality

---

*This architecture document was last updated on August 1, 2025.*