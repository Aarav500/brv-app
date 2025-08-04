# Oracle Cloud Migration Guide

This document provides comprehensive instructions for migrating the BRV Applicant Management System to Oracle Cloud Autonomous Database (Always Free Tier).

## Table of Contents

1. [Overview](#overview)
2. [Oracle Cloud Setup](#oracle-cloud-setup)
3. [Database Configuration](#database-configuration)
4. [Wallet Configuration](#wallet-configuration)
5. [Environment Variables](#environment-variables)
6. [Database Auto-Scaling](#database-auto-scaling)
7. [Troubleshooting](#troubleshooting)
8. [Migration Checklist](#migration-checklist)

## Overview

The BRV Applicant Management System has been migrated from a combination of Firebase, Planetscale (MySQL), and SQLite to Oracle Cloud Autonomous Database (Always Free Tier). This migration provides several benefits:

- Centralized data storage in Oracle Cloud
- Improved security with bcrypt password hashing
- Automatic database scaling when storage reaches 90% capacity
- Continued integration with Google Drive for resume storage
- Streamlined codebase with removal of multiple database dependencies

## Oracle Cloud Setup

### 1. Create Oracle Cloud Account

1. Go to [Oracle Cloud](https://www.oracle.com/cloud/free/) and sign up for a free account
2. Verify your email address and complete the registration process
3. Log in to the Oracle Cloud Console

### 2. Create Autonomous Database

1. In the Oracle Cloud Console, click on the hamburger menu and select **Oracle Database** > **Autonomous Database**
2. Click **Create Autonomous Database**
3. Fill in the following details:
   - **Compartment**: Select your compartment
   - **Display name**: `brv_db_1`
   - **Database name**: `brv_db_1`
   - **Workload type**: Transaction Processing
   - **Deployment type**: Shared Infrastructure
   - **Always Free**: Yes
   - **Admin password**: Create a secure password (save this for later)
   - **Network access**: Allow secure access from everywhere
   - **License type**: License Included
4. Click **Create Autonomous Database**
5. Wait for the database to be provisioned (this may take a few minutes)

## Database Configuration

### 1. Download Wallet

1. In the Oracle Cloud Console, go to your Autonomous Database
2. Click on **DB Connection**
3. Click **Download Wallet**
4. Enter a password for the wallet (save this for later)
5. Save the wallet ZIP file

### 2. Extract Wallet

1. Create a `wallet` directory in your BRV application root folder
2. Extract the contents of the wallet ZIP file into this directory
3. Ensure the following files are present:
   - `cwallet.sso`
   - `ewallet.p12`
   - `keystore.jks`
   - `ojdbc.properties`
   - `sqlnet.ora`
   - `tnsnames.ora`
   - `truststore.jks`

### 3. Initialize Database

1. Set up the required environment variables (see [Environment Variables](#environment-variables))
2. Run the database initialization script:
   ```
   python init_db.py
   ```
3. This will create the necessary tables and add default users

## Wallet Configuration

The wallet files are used to establish a secure connection to your Oracle Autonomous Database.

### 1. Update sqlnet.ora

1. Open the `sqlnet.ora` file in the wallet directory
2. Update the `DIRECTORY` parameter to point to your wallet directory using an absolute path:
   ```
   WALLET_LOCATION = (SOURCE = (METHOD = file) (METHOD_DATA = (DIRECTORY="C:\path\to\your\wallet")))
   ```

### 2. Verify Connection

1. Run the following command to test the connection:
   ```
   python -c "import oracle_db; oracle_db.test_connection()"
   ```
2. You should see a message indicating that the connection was successful

## Environment Variables

Create a `.env` file in your application root directory with the following variables:

```
# Oracle Database Configuration
ORACLE_USER=admin
ORACLE_PASSWORD=your_admin_password
ORACLE_DSN=brv_db_1_high
ORACLE_WALLET_LOCATION=wallet

# Google Drive Configuration
GOOGLE_DRIVE_FOLDER_ID=your_folder_id
GOOGLE_SERVICE_ACCOUNT_FILE=google_key.json
```

Replace the placeholder values with your actual credentials.

## Database Auto-Scaling

The application includes an automatic database scaling feature that creates a new database when the current one reaches 90% capacity.

### How Auto-Scaling Works

1. The `db_auto_scaling.py` module monitors database storage usage
2. When a database reaches 90% capacity, a new database is automatically created
3. The new database is initialized with the same schema
4. The application starts writing new data to the new database
5. Reads are performed across all databases to ensure all data is accessible

### Managing Multiple Databases

The application uses a configuration file (`db_config.json`) to track all databases:

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

### Monitoring Database Usage

To check the current database usage:

```
python -c "import db_auto_scaling; db_auto_scaling.update_storage_usage()"
```

## Troubleshooting

### Connection Issues

1. **Wallet Configuration**
   - Ensure the wallet files are in the correct directory
   - Verify that `sqlnet.ora` has the correct path to the wallet directory
   - Check that the wallet password is correct

2. **Environment Variables**
   - Verify that all environment variables are set correctly
   - Check that `ORACLE_USER` and `ORACLE_PASSWORD` match your database credentials
   - Ensure `ORACLE_DSN` is set to the correct connection string (e.g., `brv_db_1_high`)

3. **Network Issues**
   - Check if your network allows connections to Oracle Cloud
   - Verify that your IP is allowed in the database's access control list

### Database Errors

1. **Table Creation Errors**
   - Check the error message for specific issues
   - Verify that the user has the necessary privileges to create tables
   - Ensure that the tables don't already exist with different schemas

2. **Query Errors**
   - Verify that the SQL syntax is compatible with Oracle Database
   - Check for Oracle-specific data type issues
   - Ensure that named parameters use the correct format (`:param_name`)

### Auto-Scaling Issues

1. **Storage Monitoring**
   - Verify that the application can query storage usage information
   - Check if the user has the necessary privileges to view tablespace usage

2. **New Database Creation**
   - Ensure that you have the necessary Oracle Cloud API credentials
   - Verify that you haven't reached your Oracle Cloud resource limits
   - Check for any errors in the database creation process

## Migration Checklist

Use this checklist to ensure a successful migration:

- [ ] Create Oracle Cloud account
- [ ] Provision Autonomous Database (brv_db_1)
- [ ] Download and configure wallet files
- [ ] Set up environment variables
- [ ] Initialize database schema
- [ ] Test database connection
- [ ] Verify user authentication
- [ ] Test candidate data management
- [ ] Confirm Google Drive integration
- [ ] Validate database auto-scaling
- [ ] Update application interfaces
- [ ] Remove legacy database code
- [ ] Final testing of all functionality