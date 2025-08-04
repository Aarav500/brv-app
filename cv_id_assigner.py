#!/usr/bin/env python3
"""
CV ID Assigner

This script scans a Google Drive folder for CV files and assigns unique Candidate IDs
in the format CAND-XXXX. The mapping between Candidate IDs, file names, and Google Drive
file IDs is stored in a Google Sheet.

The script can be rerun without duplicating IDs for already-processed files.
"""

import os
import re
from googleapiclient.discovery import build
from google.oauth2 import service_account
import gspread
import pandas as pd

# Try to import dotenv, install if not available
try:
    from dotenv import load_dotenv
except ImportError:
    import subprocess
    import sys
    print("Installing python-dotenv...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "python-dotenv"])
    from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
SCOPES = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/spreadsheets']
SERVICE_ACCOUNT_FILE = 'google_key.json'
DRIVE_FOLDER_ID = os.getenv('DRIVE_FOLDER_ID')
SHEET_ID = os.getenv('MAPPING_SHEET_ID')
SHEET_NAME = os.getenv('MAPPING_SHEET_NAME', 'Candidate ID Mapping')

def setup_credentials():
    """
    Set up Google API credentials.
    
    Returns:
        tuple: (drive_service, sheet_client)
    """
    try:
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        
        # Create Drive API client
        drive_service = build('drive', 'v3', credentials=creds)
        
        # Create Sheets API client
        sheet_client = gspread.authorize(creds)
        
        return drive_service, sheet_client
    except Exception as e:
        print(f"Error setting up credentials: {e}")
        return None, None

def get_or_create_sheet(sheet_client):
    """
    Get or create the mapping sheet.
    
    Args:
        sheet_client: Authorized gspread client
        
    Returns:
        gspread.Worksheet: The worksheet object
    """
    try:
        # Try to open the existing sheet
        spreadsheet = sheet_client.open_by_key(SHEET_ID)
        
        # Check if the worksheet exists
        try:
            worksheet = spreadsheet.worksheet(SHEET_NAME)
            print(f"Using existing worksheet: {SHEET_NAME}")
        except gspread.exceptions.WorksheetNotFound:
            # Create a new worksheet if it doesn't exist
            worksheet = spreadsheet.add_worksheet(title=SHEET_NAME, rows=1000, cols=3)
            # Add header row
            worksheet.append_row(["Candidate ID", "File Name", "Google Drive File ID"])
            print(f"Created new worksheet: {SHEET_NAME}")
        
        return worksheet
    except Exception as e:
        print(f"Error getting or creating sheet: {e}")
        return None

def get_next_candidate_id(existing_ids):
    """
    Generate the next Candidate ID based on existing IDs.
    
    Args:
        existing_ids (list): List of existing Candidate IDs
        
    Returns:
        str: The next Candidate ID in the format CAND-XXXX
    """
    if not existing_ids:
        return "CAND-0001"
    
    # Extract numbers from existing IDs
    numbers = []
    for id in existing_ids:
        match = re.match(r'CAND-(\d+)', id)
        if match:
            numbers.append(int(match.group(1)))
    
    if not numbers:
        return "CAND-0001"
    
    # Get the next number
    next_number = max(numbers) + 1
    
    # Format the ID
    return f"CAND-{next_number:04d}"

def list_drive_files(drive_service, folder_id):
    """
    List all files in the specified Google Drive folder.
    
    Args:
        drive_service: Authorized Drive API service
        folder_id (str): ID of the Google Drive folder
        
    Returns:
        list: List of file objects with id, name, mimeType, createdTime, modifiedTime, and webViewLink
    """
    try:
        results = drive_service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="files(id, name, mimeType, createdTime, modifiedTime, webViewLink)"
        ).execute()
        
        files = results.get('files', [])
        
        # Filter for document and PDF files
        doc_files = [f for f in files if f['mimeType'] in [
            'application/pdf',
            'application/vnd.google-apps.document',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        ]]
        
        return doc_files
    except Exception as e:
        print(f"Error listing Drive files: {e}")
        return []

def is_valid_candidate_id(candidate_id):
    """
    Check if a Candidate ID is valid (follows the format CAND-XXXX).
    
    Args:
        candidate_id (str): The Candidate ID to check
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not candidate_id:
        return False
    
    # Check if the ID follows the format CAND-XXXX
    pattern = r'^CAND-\d{4}$'
    return bool(re.match(pattern, candidate_id))

def is_candidate_id_unique(candidate_id, existing_ids):
    """
    Check if a Candidate ID is unique.
    
    Args:
        candidate_id (str): The Candidate ID to check
        existing_ids (list): List of existing Candidate IDs
        
    Returns:
        bool: True if unique, False otherwise
    """
    return candidate_id not in existing_ids

def rename_file_in_drive(drive_service, file_id, new_name):
    """
    Rename a file in Google Drive.
    
    Args:
        drive_service: Authorized Drive API service
        file_id (str): The ID of the file to rename
        new_name (str): The new name for the file
        
    Returns:
        tuple: (success, message, updated_file)
    """
    try:
        # Update the file metadata
        file = drive_service.files().update(
            fileId=file_id,
            body={'name': new_name},
            fields='id, name, mimeType, webViewLink'
        ).execute()
        
        return True, f"Successfully renamed file to {new_name}", file
    except Exception as e:
        print(f"Error renaming file in Drive: {e}")
        return False, f"Error renaming file: {str(e)}", None

def assign_manual_candidate_id(file_id, file_name, candidate_id, rename_file=True):
    """
    Assign a manually entered Candidate ID to a CV file.
    
    Args:
        file_id (str): The Google Drive file ID
        file_name (str): The file name
        candidate_id (str): The manually entered Candidate ID
        rename_file (bool): Whether to rename the file in Google Drive
        
    Returns:
        tuple: (success, message)
    """
    print(f"Assigning manual Candidate ID {candidate_id} to {file_name}...")
    
    # Set up credentials
    drive_service, sheet_client = setup_credentials()
    if not drive_service or not sheet_client:
        return False, "Failed to set up credentials."
    
    # Check if required environment variables are set
    if not SHEET_ID:
        return False, "MAPPING_SHEET_ID environment variable is not set."
    
    # Get or create the mapping sheet
    worksheet = get_or_create_sheet(sheet_client)
    if not worksheet:
        return False, "Failed to get or create worksheet."
    
    # Get existing mappings
    existing_data = worksheet.get_all_records()
    existing_file_ids = {row['Google Drive File ID']: row['Candidate ID'] for row in existing_data}
    existing_candidate_ids = [row['Candidate ID'] for row in existing_data]
    
    # Check if the file ID already has a Candidate ID assigned
    if file_id in existing_file_ids:
        old_id = existing_file_ids[file_id]
        return False, f"File already has Candidate ID {old_id} assigned."
    
    # Validate the Candidate ID
    if not is_valid_candidate_id(candidate_id):
        return False, f"Invalid Candidate ID format. Must be in the format CAND-XXXX."
    
    # Check if the Candidate ID is unique
    if not is_candidate_id_unique(candidate_id, existing_candidate_ids):
        return False, f"Candidate ID {candidate_id} is already in use."
    
    # Rename the file in Google Drive if requested
    if rename_file:
        # Get file extension from original filename
        file_ext = os.path.splitext(file_name)[1] if '.' in file_name else '.pdf'
        new_file_name = f"BRV-CID-{candidate_id}{file_ext}"
        
        rename_success, rename_message, updated_file = rename_file_in_drive(
            drive_service, file_id, new_file_name
        )
        
        if rename_success:
            print(f"Renamed file to {new_file_name}")
            # Use the updated file name for the mapping
            file_name = updated_file['name']
        else:
            print(f"Warning: {rename_message}")
            # Continue with the original filename
    
    # Add to the sheet
    worksheet.append_row([candidate_id, file_name, file_id])
    
    print(f"Assigned {candidate_id} to {file_name}")
    return True, f"Successfully assigned {candidate_id} to {file_name}"

def assign_candidate_ids(auto_generate=True):
    """
    Main function to assign Candidate IDs to CV files in Google Drive.
    
    Args:
        auto_generate (bool): Whether to auto-generate IDs (True) or skip unassigned files (False)
    """
    print("Starting CV ID Assigner...")
    
    # Set up credentials
    drive_service, sheet_client = setup_credentials()
    if not drive_service or not sheet_client:
        print("Failed to set up credentials. Exiting.")
        return
    
    # Check if required environment variables are set
    if not DRIVE_FOLDER_ID:
        print("DRIVE_FOLDER_ID environment variable is not set. Exiting.")
        return
    
    if not SHEET_ID:
        print("MAPPING_SHEET_ID environment variable is not set. Exiting.")
        return
    
    # Get or create the mapping sheet
    worksheet = get_or_create_sheet(sheet_client)
    if not worksheet:
        print("Failed to get or create worksheet. Exiting.")
        return
    
    # Get existing mappings
    existing_data = worksheet.get_all_records()
    existing_file_ids = {row['Google Drive File ID']: row['Candidate ID'] for row in existing_data}
    existing_candidate_ids = [row['Candidate ID'] for row in existing_data]
    
    # List files in the Drive folder
    files = list_drive_files(drive_service, DRIVE_FOLDER_ID)
    if not files:
        print("No files found in the specified Google Drive folder.")
        return
    
    print(f"Found {len(files)} files in the Drive folder.")
    print(f"Found {len(existing_data)} existing mappings in the sheet.")
    
    # Process files
    new_mappings = 0
    for file in files:
        file_id = file['id']
        file_name = file['name']
        
        # Skip if already processed
        if file_id in existing_file_ids:
            print(f"Skipping already processed file: {file_name}")
            continue
        
        # Skip if not auto-generating
        if not auto_generate:
            print(f"Skipping unassigned file: {file_name} (auto-generate is disabled)")
            continue
        
        # Generate a new Candidate ID
        candidate_id = get_next_candidate_id(existing_candidate_ids)
        
        # Add to the sheet
        worksheet.append_row([candidate_id, file_name, file_id])
        
        # Update tracking variables
        existing_file_ids[file_id] = candidate_id
        existing_candidate_ids.append(candidate_id)
        new_mappings += 1
        
        print(f"Assigned {candidate_id} to {file_name}")
    
    print(f"Assigned {new_mappings} new Candidate IDs.")
    print("CV ID assignment complete.")

if __name__ == "__main__":
    assign_candidate_ids()