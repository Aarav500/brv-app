# BRV Applicant Management Application - Audit Report

This document provides a detailed audit of the BRV Applicant Management Application, focusing on its features, database integration, user roles, and environment configuration. The goal is to ensure the application functions correctly in production with Oracle DB.

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Top Priority Fixes](#top-priority-fixes)
3. [Feature Status Table](#feature-status-table)
4. [Database Integration Analysis](#database-integration-analysis)
5. [Test Accounts](#test-accounts)
6. [Google Drive CV Integration](#google-drive-cv-integration)
7. [Environment Variables Analysis](#environment-variables-analysis)
8. [Role-Based Access Control (RBAC) Analysis](#role-based-access-control-rbac-analysis)
9. [Recommendations](#recommendations)

## Executive Summary

This audit report provides a comprehensive analysis of the BRV Applicant Management Application, examining its features, database integration, user roles, and environment configuration. The audit reveals several critical issues that need to be addressed to ensure the application functions correctly in production with Oracle DB.

## Top Priority Fixes

1. **Database Integration Inconsistency**: The application has both Oracle DB and MySQL implementations, but all UI components use MySQL functions while environment variables are configured for Oracle. This must be resolved by updating all view files to use the Oracle database functions.

2. **Resume Linker Integration**: The resume_linker.py file uses MySQL functions instead of Oracle functions, causing CV uploads to be stored in the wrong database.

3. **Missing Environment Variables**: Several environment variables mentioned in the template are missing from the actual .env file, potentially breaking functionality.

4. **README Documentation Mismatch**: The README describes a MySQL/Planetscale implementation, but the actual code uses Oracle DB. The documentation needs to be updated.

5. **Test Account Verification**: While default test accounts exist in the Oracle implementation, they may not be properly accessible due to the database inconsistency.

## Feature Status Table

| Feature | Status | Evidence (files/lines) | Fix Instructions | Oracle DB Notes | Test Account |
|---------|--------|------------------------|------------------|-----------------|--------------|
| **Candidate Features** |
| Direct in-app form filling | Working but with wrong DB | candidate_view.py (11-390) | Update imports to use oracle_candidates.py instead of mysql_db.py | Form data is stored in MySQL, not Oracle | candidate@example.com / password123 |
| CV upload from local PC to cloud storage | Needs Fix | resume_linker.py (52-94), cloud_storage.py (95-174) | Update resume_linker.py to use Oracle functions | CV metadata stored in MySQL, not Oracle | N/A |
| Auto-generated Candidate ID | Working but with wrong DB | mysql_db.py (560-636) | Update to use Oracle candidate creation functions | IDs generated in MySQL, not Oracle | N/A |
| Ability to edit application with Receptionist assistance | Working but with wrong DB | reception_view.py (31-75) | Update imports to use oracle_candidates.py | Edits stored in MySQL, not Oracle | N/A |
| **Receptionist Features** |
| Allow candidates to edit their application | Working but with wrong DB | reception_view.py (31-75), receptionist_panel.py (42-60) | Update imports to use oracle_candidates.py | Edits stored in MySQL, not Oracle | receptionist@bluematrixit.com / password123 |
| View all candidates with filtering options | Working but with wrong DB | reception_view.py (77-142), receptionist_panel.py (330-489) | Update imports to use oracle_candidates.py | Viewing MySQL data, not Oracle | N/A |
| Manual form entry for walk-in applicants | Working but with wrong DB | reception_view.py (203-229) | Update imports to use oracle_candidates.py | Data stored in MySQL, not Oracle | N/A |
| Resume management through cloud storage | Needs Fix | receptionist_panel.py (8-40), cloud_storage.py (95-174) | Update to use Oracle functions for CV metadata | CV metadata stored in MySQL, not Oracle | N/A |
| Candidate profile management | Working but with wrong DB | receptionist_panel.py (62-92) | Update imports to use oracle_candidates.py | Profile data stored in MySQL, not Oracle | N/A |
| **Interviewer Features** |
| View scheduled interviews | Working but with wrong DB | interviewer.py (125-179) | Update imports to use oracle_candidates.py | Viewing MySQL data, not Oracle | interviewer@bluematrixit.com / password123 |
| Access applicant information and download CVs | Working but with wrong DB | interviewer.py (39-123) | Update imports to use oracle_candidates.py | Viewing MySQL data, not Oracle | N/A |
| Record interview notes and results | Working but with wrong DB | interviewer.py (181-401) | Update imports to use oracle_candidates.py | Data stored in MySQL, not Oracle | N/A |
| View past interview history | Working but with wrong DB | interviewer.py (181-401) | Update imports to use oracle_candidates.py | Viewing MySQL data, not Oracle | N/A |
| **CEO Features** |
| Dashboard with applicant statistics | Working but with wrong DB | ceo.py (22-80) | Update imports to use oracle_candidates.py | Stats from MySQL, not Oracle | ceo@bluematrixit.com / password123 |
| Comprehensive view of all candidates | Working but with wrong DB | ceo.py (82-186) | Update imports to use oracle_candidates.py | Viewing MySQL data, not Oracle | N/A |
| Interview result analysis | Working but with wrong DB | ceo.py (188-276) | Update imports to use oracle_candidates.py | Analysis from MySQL, not Oracle | N/A |
| Filtering and searching capabilities | Working but with wrong DB | ceo.py (82-186) | Update imports to use oracle_candidates.py | Searching MySQL data, not Oracle | N/A |

## Database Integration Analysis

The application has multiple database implementations:

1. **Oracle Database (Primary)**: 
   - Files: oracle_db.py, oracle_candidates.py, init_db.py
   - Environment variables configured for Oracle in .env
   - Database configuration in db_config.json points to Oracle

2. **MySQL Database (Legacy)**:
   - File: mysql_db.py
   - Used by all UI components (candidate_view.py, reception_view.py, interviewer.py, ceo.py)
   - No environment variables configured for MySQL

3. **SQLite Database (Fallback)**:
   - File: database.py
   - Appears to be a fallback implementation

The critical issue is that while the application is configured to use Oracle DB, all UI components are importing and using MySQL functions. This means that data entered through the UI is being stored in MySQL (or failing if MySQL is not configured), while the Oracle DB remains unused despite being configured.

## Test Accounts

The application has default test accounts for all four roles:

| Role | Email | Password | Status |
|------|-------|----------|--------|
| CEO | ceo@bluematrixit.com | password123 | Exists in Oracle DB but UI uses MySQL |
| Interviewer | interviewer@bluematrixit.com | password123 | Exists in Oracle DB but UI uses MySQL |
| Receptionist | receptionist@bluematrixit.com | password123 | Exists in Oracle DB but UI uses MySQL |
| Candidate | candidate@example.com | password123 | Exists in Oracle DB but UI uses MySQL |

To create these accounts in Oracle DB if they don't exist, the following SQL can be used:

```sql
-- Create CEO account
INSERT INTO users (
    user_id, 
    username, 
    email, 
    password_hash, 
    role, 
    last_password_change,
    force_password_reset
) VALUES (
    SYS_GUID(), 
    'ceo', 
    'ceo@bluematrixit.com', 
    '[bcrypt hash of password123]', 
    'ceo', 
    CURRENT_TIMESTAMP,
    0
);

-- Create Interviewer account
INSERT INTO users (
    user_id, 
    username, 
    email, 
    password_hash, 
    role, 
    last_password_change,
    force_password_reset
) VALUES (
    SYS_GUID(), 
    'interviewer', 
    'interviewer@bluematrixit.com', 
    '[bcrypt hash of password123]', 
    'interviewer', 
    CURRENT_TIMESTAMP,
    1
);

-- Create Receptionist account
INSERT INTO users (
    user_id, 
    username, 
    email, 
    password_hash, 
    role, 
    last_password_change,
    force_password_reset
) VALUES (
    SYS_GUID(), 
    'receptionist', 
    'receptionist@bluematrixit.com', 
    '[bcrypt hash of password123]', 
    'receptionist', 
    CURRENT_TIMESTAMP,
    1
);

-- Create Candidate account
INSERT INTO users (
    user_id, 
    username, 
    email, 
    password_hash, 
    role, 
    last_password_change,
    force_password_reset
) VALUES (
    SYS_GUID(), 
    'candidate', 
    'candidate@example.com', 
    '[bcrypt hash of password123]', 
    'candidate', 
    CURRENT_TIMESTAMP,
    0
);
```

Note: The bcrypt hash should be generated using the hash_password function from user_auth.py.

## Google Drive CV Integration

The application uses Google Drive for CV storage:

1. **Upload**: cloud_storage.py provides functions for uploading CVs to Google Drive
2. **Download**: cloud_storage.py provides functions for downloading CVs from Google Drive
3. **Linking**: resume_linker.py links CVs to candidates, but uses MySQL functions

The Google Drive integration appears functional, but the critical issue is that resume_linker.py uses MySQL functions to link CVs to candidates, not Oracle functions. This means that CV metadata is stored in MySQL, not Oracle, creating a data inconsistency.

## Environment Variables Analysis

The following environment variables are used in the code:

| Variable | Used In | Status |
|----------|---------|--------|
| ORACLE_USER | env_config.py, oracle_db.py, init_db.py | Present in .env |
| ORACLE_PASSWORD | env_config.py, oracle_db.py, init_db.py | Present in .env |
| ORACLE_DSN | env_config.py, oracle_db.py, init_db.py | Present in .env |
| ORACLE_WALLET_LOCATION | env_config.py, oracle_db.py, init_db.py | Present in .env |
| GOOGLE_DRIVE_FOLDER_ID | env_config.py, cloud_storage.py | Present in .env |
| GOOGLE_SERVICE_ACCOUNT_FILE | env_config.py, cloud_storage.py | Present in .env |
| MAPPING_SHEET_ID | utils.py | Missing from .env |
| MAPPING_SHEET_NAME | utils.py | Missing from .env |
| GOOGLE_FORM_ID | utils.py | Missing from .env |
| FORM_SHEET_ID | utils.py | Missing from .env |
| API_SECRET_KEY | Not found in code | Missing from .env |
| API_PORT | Not found in code | Missing from .env |
| API_HOST | Not found in code | Missing from .env |

Several environment variables mentioned in .env.template are missing from the actual .env file, potentially breaking functionality that depends on these variables.

## Role-Based Access Control (RBAC) Analysis

The application implements role-based access control through the user_auth.py and auth.py files. Each user has a role (CEO, Interviewer, Receptionist, or Candidate) that determines which views they can access.

No significant RBAC gaps were identified, but the database inconsistency issue may affect the proper functioning of the RBAC system if user data is stored in different databases.

## Recommendations

1. **Update UI Components**: Modify all view files (candidate_view.py, reception_view.py, interviewer.py, ceo.py) to import and use Oracle database functions instead of MySQL functions.

2. **Fix Resume Linker**: Update resume_linker.py to use Oracle functions for linking CVs to candidates.

3. **Update Environment Variables**: Add missing environment variables to the .env file or remove unused variables from the code.

4. **Update README**: Update the README to accurately reflect the Oracle database implementation.

5. **Database Migration**: Consider implementing a migration script to transfer data from MySQL to Oracle if both databases contain valuable data.

6. **Consolidate Database Code**: Consider consolidating the database code to use a single abstraction layer that can work with multiple database backends.

7. **Improve Error Handling**: Add better error handling for database operations to gracefully handle connection failures.

By addressing these issues, the BRV Applicant Management Application can function correctly with Oracle DB in production, ensuring data consistency and reliability.
```python
from functools import wraps
import os
import cx_Oracle

# Placeholder for DB connection; in real app, use a proper pool and config
def get_db_connection():
    dsn = os.environ.get("ORACLE_DSN", "host:1521/ORCLPDB1")
    user = os.environ.get("ORACLE_USER", "app_user")
    password = os.environ.get("ORACLE_PASSWORD", "password")
    return cx_Oracle.connect(user, password, dsn)

def _get_user_role_from_db(user_id):
    # In a real app, fetch from users table; here we simulate a simple query
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT role FROM users WHERE id = :id", {"id": user_id})
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        cur.close()
        conn.close()

def requires_role(role_name_or_list):
    if isinstance(role_name_or_list, str):
        allowed = {role_name_or_list}
    else:
        allowed = set(role_name_or_list)

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # In real app, extract current_user_id from session/context
            current_user_id = os.environ.get("CURRENT_USER_ID")
            if not current_user_id:
                raise PermissionError("Unauthorized: no user context available")

            user_role = _get_user_role_from_db(current_user_id)
            if user_role not in allowed:
                raise PermissionError(f"Forbidden: role '{user_role}' not allowed")

            return func(*args, **kwargs)
        return wrapper
    return decorator