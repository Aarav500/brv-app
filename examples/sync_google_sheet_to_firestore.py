"""
Google Sheet to Firestore Sync Script

This script demonstrates how to sync data from a Google Sheet to Firebase Firestore.
It includes examples of:
1. Fetching data from Google Sheets
2. Processing the data
3. Storing the data in Firestore
"""

import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import os
import uuid

def initialize_firebase():
    """Initialize Firebase with service account credentials"""
    print("Step 1: Initializing Firebase...")
    
    try:
        # Check if Firebase is already initialized
        firebase_admin.get_app()
        print("Firebase already initialized")
    except ValueError:
        # Initialize Firebase with service account credentials
        cred = credentials.Certificate("google_key.json")
        firebase_admin.initialize_app(cred)
        print("Firebase initialized successfully")
    
    # Get Firestore client
    db = firestore.client()
    print("Firestore client created")
    
    return db

def fetch_google_sheet_data(sheet_url=None):
    """
    Fetch data from a Google Sheet
    
    Args:
        sheet_url (str, optional): URL of the Google Sheet to fetch
        
    Returns:
        pandas.DataFrame: DataFrame containing the sheet data
    """
    print("\nStep 2: Fetching Google Sheet data...")
    
    try:
        # Set up credentials
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        
        # Check if credentials file exists
        if not os.path.exists('google_key.json'):
            print("Google API key file not found. Using sample data.")
            return get_sample_data()
        
        creds = ServiceAccountCredentials.from_json_keyfile_name('google_key.json', scope)
        client = gspread.authorize(creds)
        
        # Use the provided sheet URL or a default one
        if sheet_url:
            sheet = client.open_by_url(sheet_url)
        else:
            # Default spreadsheet ID
            spreadsheet_id = "1V0Sf65ZVrebpopBfg2vwk-_PjRxgqlbytIX-L2GImAE"
            sheet = client.open_by_key(spreadsheet_id)
        
        # Get the first worksheet
        worksheet = sheet.get_worksheet(0)
        
        # Get all records
        data = worksheet.get_all_records()
        
        # Convert to DataFrame
        df = pd.DataFrame(data)
        
        print(f"Fetched {len(df)} rows from Google Sheet")
        print(f"Columns: {df.columns.tolist()}")
        
        # If DataFrame is empty, return sample data
        if df.empty:
            print("No data found in Google Sheet, returning sample data")
            return get_sample_data()
        
        return df
        
    except Exception as e:
        print(f"Error fetching Google Sheet data: {e}")
        import traceback
        traceback.print_exc()
        
        # Return sample data if there's an error
        return get_sample_data()

def get_sample_data():
    """
    Returns sample data for testing when Google Sheets connection is not available.
    
    Returns:
        pandas.DataFrame: DataFrame containing sample data
    """
    print("Using sample data...")
    
    # Create sample data
    sample_data = [
        {
            "Timestamp": "2023-07-01 10:30:45",
            "Full Name": "John Doe",
            "Email": "john.doe@example.com",
            "Phone": "1234567890",
            "Resume Link": "https://drive.google.com/file/d/abc123/view",
            "Position": "Software Developer"
        },
        {
            "Timestamp": "2023-07-02 11:45:22",
            "Full Name": "Jane Smith",
            "Email": "jane.smith@example.com",
            "Phone": "0987654321",
            "Resume Link": "https://drive.google.com/file/d/def456/view",
            "Position": "Project Manager"
        },
        {
            "Timestamp": "2023-07-03 09:15:33",
            "Full Name": "Bob Johnson",
            "Email": "bob.johnson@example.com",
            "Phone": "5556667777",
            "Resume Link": "https://drive.google.com/file/d/ghi789/view",
            "Position": "UI/UX Designer"
        }
    ]
    
    return pd.DataFrame(sample_data)

def process_data(df):
    """
    Process the data from the Google Sheet
    
    Args:
        df (pandas.DataFrame): DataFrame containing the sheet data
        
    Returns:
        list: List of dictionaries containing processed data
    """
    print("\nStep 3: Processing data...")
    
    processed_data = []
    
    # Find email column
    email_column = None
    for col in df.columns:
        if 'email' in col.lower():
            email_column = col
            break
    
    if not email_column:
        print("No email column found in data")
        return processed_data
    
    # Find resume column
    resume_column = None
    for col in df.columns:
        if 'resume' in col.lower() or 'cv' in col.lower() or 'file' in col.lower():
            resume_column = col
            break
    
    # Process each row
    for _, row in df.iterrows():
        # Convert row to dict
        row_dict = row.to_dict()
        
        # Extract email
        email = row_dict.get(email_column)
        
        if not email:
            continue
        
        # Create candidate data
        candidate_data = {
            "id": str(uuid.uuid4()),
            "email": email,
            "form_data": row_dict,
            "status": "New",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Add resume link if available
        if resume_column and row_dict.get(resume_column):
            candidate_data["resume_link"] = row_dict.get(resume_column)
        
        processed_data.append(candidate_data)
    
    print(f"Processed {len(processed_data)} candidates")
    return processed_data

def sync_to_firestore(db, candidates):
    """
    Sync the processed data to Firestore
    
    Args:
        db (firestore.Client): Firestore client
        candidates (list): List of candidate dictionaries
        
    Returns:
        tuple: (added_count, updated_count)
    """
    print("\nStep 4: Syncing data to Firestore...")
    
    added_count = 0
    updated_count = 0
    
    for candidate in candidates:
        email = candidate.get("email")
        
        if not email:
            continue
        
        # Check if candidate exists
        candidate_ref = db.collection("candidates").document(email)
        candidate_doc = candidate_ref.get()
        
        if candidate_doc.exists:
            # Update existing candidate
            update_data = {
                "form_data": candidate.get("form_data"),
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Update resume link if available
            if "resume_link" in candidate:
                update_data["resume_link"] = candidate.get("resume_link")
            
            candidate_ref.update(update_data)
            updated_count += 1
            print(f"Updated candidate: {email}")
        else:
            # Add new candidate
            candidate_ref.set(candidate)
            added_count += 1
            print(f"Added candidate: {email}")
    
    return added_count, updated_count

def main():
    """Main function to run the sync"""
    print("Google Sheet to Firestore Sync Script")
    print("====================================")
    
    # Step 1: Initialize Firebase
    db = initialize_firebase()
    
    # Step 2: Fetch Google Sheet data
    df = fetch_google_sheet_data()
    
    # Step 3: Process the data
    candidates = process_data(df)
    
    # Step 4: Sync to Firestore
    added, updated = sync_to_firestore(db, candidates)
    
    print("\nSync completed successfully!")
    print(f"Added {added} new candidates")
    print(f"Updated {updated} existing candidates")

if __name__ == "__main__":
    main()