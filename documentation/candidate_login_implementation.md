# Candidate Login Implementation

## Overview

This document describes the implementation of candidate login functionality for the BRV Applicant Management System. The changes allow candidates to log in to the system and access their application information.

## Changes Made

1. Added "candidate" to the list of valid roles in `utils.py`
2. Updated `main.py` to route users with the "candidate" role to `candidate_form_view()`
3. Created a script (`add_test_candidate.py`) to add a test candidate user to the database

## Test Candidate User

A test candidate user should be added to the database with the following credentials:

- **Username**: candidate@example.com
- **Password**: password123
- **Role**: candidate

## Adding the Test Candidate User

The database administrator should add the test candidate user using one of the following methods:

### Method 1: Using the MySQL Command Line

```sql
INSERT INTO users (email, password_hash, role, created_at, force_password_reset, last_password_change)
VALUES ('candidate@example.com', 'password123', 'candidate', NOW(), 0, NOW());
```

### Method 2: Using the add_test_candidate.py Script

The `add_test_candidate.py` script has been created to add the test candidate user to the database. To run the script:

1. Ensure the MySQL server is running
2. Navigate to the brv-app directory
3. Run the script:
   ```
   python add_test_candidate.py
   ```

## Testing

After adding the test candidate user, test the implementation by logging in with the following credentials:

- **Username**: candidate@example.com
- **Password**: password123

The user should be redirected to the candidate view after successful login.

## Troubleshooting

If the candidate login is not working as expected, check the following:

1. Verify that the user has been added to the database with the correct role ("candidate")
2. Check that "candidate" is included in the VALID_ROLES list in utils.py
3. Ensure that main.py is correctly routing users with the "candidate" role to candidate_form_view()
4. Check the application logs for any errors