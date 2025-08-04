# Planetscale and Google Drive Setup Guide

This guide provides instructions for setting up and configuring the BRV Applicant Management System with Planetscale for database storage and Google Drive for CV storage.

## Current Setup

The BRV Applicant Management System now uses:

- **Planetscale (MySQL)**: for user logins and candidate data
- **Google Drive**: for storing CVs
- **Streamlit**: as the interface connected to both

## 1. Planetscale Setup

[Planetscale](https://planetscale.com/) is a MySQL-compatible database platform built on Vitess, which provides horizontal scaling for MySQL.

### 1.1 Create a Planetscale Account

1. Go to [Planetscale](https://planetscale.com/) and sign up for an account
2. Create a new database called `brv_db` (or your preferred name)
3. Create a new branch (e.g., `main`)

### 1.2 Create a Connection

1. In your Planetscale dashboard, go to your database
2. Click on "Connect"
3. Select "Connect with" and choose "General"
4. Note down the following connection details:
   - Host
   - Username
   - Password
   - Database name

### 1.3 Configure Environment Variables

Set the following environment variables on your system:

```
PLANETSCALE_HOST=<your-planetscale-host>
PLANETSCALE_USERNAME=<your-planetscale-username>
PLANETSCALE_PASSWORD=<your-planetscale-password>
PLANETSCALE_DATABASE=<your-planetscale-database>
```

For Windows:
```
setx PLANETSCALE_HOST "<your-planetscale-host>"
setx PLANETSCALE_USERNAME "<your-planetscale-username>"
setx PLANETSCALE_PASSWORD "<your-planetscale-password>"
setx PLANETSCALE_DATABASE "<your-planetscale-database>"
```

For Linux/Mac:
```
export PLANETSCALE_HOST=<your-planetscale-host>
export PLANETSCALE_USERNAME=<your-planetscale-username>
export PLANETSCALE_PASSWORD=<your-planetscale-password>
export PLANETSCALE_DATABASE=<your-planetscale-database>
```

### 1.4 Initialize the Database

Run the following command to initialize the database:

```
python init_db.py
```

This will create the necessary tables and add default users to the database.

## 2. Google Drive Setup

### 2.1 Create a Google Cloud Project

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable the Google Drive API for your project

### 2.2 Create a Service Account

1. In your Google Cloud project, go to "IAM & Admin" > "Service Accounts"
2. Click "Create Service Account"
3. Enter a name and description for the service account
4. Grant the service account the "Drive File" role
5. Click "Create Key" and select JSON
6. Download the JSON key file and save it as `google_key.json` in your project root directory

### 2.3 Create a Google Drive Folder

1. Go to [Google Drive](https://drive.google.com/)
2. Create a new folder for storing CV files
3. Right-click on the folder and select "Share"
4. Add the service account email (found in the JSON key file) with "Editor" access
5. Note down the folder ID (the long string in the URL when you open the folder)

### 2.4 Configure Environment Variables

Set the following environment variables on your system:

```
GOOGLE_DRIVE_FOLDER_ID=<your-folder-id>
GOOGLE_SERVICE_ACCOUNT_FILE=google_key.json
```

For Windows:
```
setx GOOGLE_DRIVE_FOLDER_ID "<your-folder-id>"
setx GOOGLE_SERVICE_ACCOUNT_FILE "google_key.json"
```

For Linux/Mac:
```
export GOOGLE_DRIVE_FOLDER_ID=<your-folder-id>
export GOOGLE_SERVICE_ACCOUNT_FILE=google_key.json
```

## 3. Testing the Setup

### 3.1 Test Database Connection

Run the following command to test the database connection:

```
python -c "import mysql_db; mysql_db.test_connection()"
```

You should see a message indicating that the MySQL connection was successful.

### 3.2 Test Google Drive Connection

Run the following command to test the Google Drive connection:

```
python -c "import cloud_storage; cloud_storage.init_storage()"
```

You should see a message indicating that the Google Drive storage was initialized successfully.

## 4. Troubleshooting

### 4.1 Planetscale Connection Issues

- Verify that your environment variables are set correctly
- Check if your IP address is allowed in Planetscale's network settings
- Ensure that your Planetscale database is active

### 4.2 Google Drive Connection Issues

- Verify that your `google_key.json` file is in the correct location
- Check if the service account has the necessary permissions
- Ensure that the Google Drive API is enabled in your Google Cloud project

## 5. Additional Configuration

### 5.1 SSL Configuration for Planetscale

If you need to use SSL for your Planetscale connection, you can set the following environment variable:

```
PLANETSCALE_SSL_CA=<path-to-ssl-ca-certificate>
```

### 5.2 Google Drive API Quotas

Be aware of Google Drive API quotas. If you're uploading or downloading a large number of files, you may hit API limits. Consider implementing rate limiting or batch processing for large operations.

## 6. Migration from Previous Setup

If you're migrating from a previous setup (local MySQL and Supabase/other storage):

1. Export your data from the local MySQL database
2. Import the data into Planetscale
3. Upload your CV files to Google Drive
4. Update the CV URLs in the database to point to the Google Drive files

## 7. Environment Variables Summary

Here's a summary of all the environment variables used in the application:

| Variable | Description | Default Value |
|----------|-------------|---------------|
| PLANETSCALE_HOST | Planetscale host | 127.0.0.1 |
| PLANETSCALE_USERNAME | Planetscale username | root |
| PLANETSCALE_PASSWORD | Planetscale password | password |
| PLANETSCALE_DATABASE | Planetscale database name | brv_db |
| PLANETSCALE_SSL_CA | Path to SSL CA certificate | None |
| GOOGLE_DRIVE_FOLDER_ID | Google Drive folder ID for storing CVs | "" |
| GOOGLE_SERVICE_ACCOUNT_FILE | Path to Google service account key file | google_key.json |