# Salt Column Update for User Passwords

This update adds a salt column to the users table in the database and implements salt-based password hashing for improved security.

## What is a Salt?

A salt is a random value that is generated for each user and combined with their password before hashing. This ensures that even if two users have the same password, their hashed passwords will be different. This makes it much harder for attackers to use precomputed tables (rainbow tables) to crack passwords.

## Changes Made

1. Added a `salt` column to the `users` table in the database
2. Updated the authentication system to use salt-based password hashing
3. Generated salts for existing users
4. Updated user creation and password reset functions to use salt-based hashing

## How to Apply the Update

If you're installing the application for the first time, the salt column will be added automatically during database initialization.

If you're updating an existing installation, you need to run the `add_salt_column.py` script to add the salt column and generate salts for existing users:

```bash
python add_salt_column.py
```

This script will:
1. Add the salt column to the users table if it doesn't exist
2. Find all users without salts
3. Generate salts for these users and update their passwords
4. Print a message when the update is complete

## Technical Details

The salt-based password hashing is implemented in the `security.py` file. The `hash_password` function generates a random salt if none is provided and combines it with the password before hashing. The `verify_password` function verifies a password against a stored hash using the same salt.

The authentication system in `auth.py` has been updated to use these functions for password verification and changing.

The database functions in `database.py` have been updated to store and use salts when creating users and resetting passwords.

## Security Benefits

- Prevents rainbow table attacks
- Makes brute force attacks more difficult
- Ensures that even if two users have the same password, their hashed passwords will be different
- Improves overall security of the application