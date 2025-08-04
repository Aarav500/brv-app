# Database Recreation Script

This repository includes a script (`recreate_db.py`) that can be run once to recreate the users.db database with all required tables and columns.

## Purpose

The `recreate_db.py` script is designed to:
1. Recreate the users table with the correct schema
2. Create all other required tables (candidates, interviews, first_interview, settings)
3. Add default users and settings

This ensures that your database has the correct structure for the application to work properly.

## Usage

To recreate the database, simply run:

```bash
python recreate_db.py
```

This will:
1. Run `setup_users_db.py` to recreate the users table with the CEO user
2. Create the candidates, interviews, first_interview, and settings tables
3. Add a default password expiry policy to the settings table
4. Add the reception and interview users if they don't already exist

## Default Users

After running the script, you'll have the following default users:

1. CEO User:
   - Username: ceo
   - Password: admin123
   - Role: CEO

2. Reception User:
   - Username: reception
   - Password: 123
   - Role: receptionist

3. Interview User:
   - Username: interview
   - Password: 234
   - Role: interviewer

## Warning

Running this script will drop and recreate the users table, which means all existing user data will be lost. Only run this script if you're setting up a new installation or if you're okay with losing existing user data.

## Database Schema

The script creates the following tables:

1. **users** - Stores user authentication and role information
   - id (PRIMARY KEY)
   - username (UNIQUE)
   - password (hashed with salt)
   - role
   - salt
   - created
   - last_password_change
   - force_password_reset

2. **candidates** - Stores applicant information
   - id (PRIMARY KEY)
   - name
   - email
   - phone
   - address
   - form_data
   - hr_data
   - resume_path
   - status

3. **interviews** - Stores interview scheduling and feedback
   - id (PRIMARY KEY)
   - candidate_id (FOREIGN KEY)
   - interviewer_id
   - interviewer_name
   - scheduled_time
   - feedback
   - status
   - result
   - created_at
   - updated_at

4. **first_interview** - Stores first interview data
   - id (PRIMARY KEY)
   - candidate_id (FOREIGN KEY)
   - data
   - created_at

5. **settings** - Stores application settings
   - key (PRIMARY KEY)
   - value
   - updated_at