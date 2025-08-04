import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from datetime import datetime

def update_google_sheet_by_candidate_id(identifier, updates):
    """
    Update a row in the Google Sheet based on an identifier (email, application_id).
    
    Args:
        identifier (str): The identifier (email, application_id) to identify the row to update
        updates (dict): Dictionary of column names and values to update
        
    Returns:
        tuple: (success, message) where success is a boolean and message is a string
    """
    if not identifier:
        return False, "No identifier provided"
    
    if not updates:
        return False, "No updates provided"
    
    try:
        # Set up credentials
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        
        if not os.path.exists('google_key.json'):
            return False, "Google API key file not found"
        
        creds = ServiceAccountCredentials.from_json_keyfile_name('google_key.json', scope)
        client = gspread.authorize(creds)
        
        # Open the Google Sheet
        sheet_url = "https://docs.google.com/spreadsheets/d/1V0Sf65ZVrebpopBfg2vwk-_PjRxgqlbytIX-L2GImAE/edit?resourcekey=&gid=1400567486"
        sheet = client.open_by_url(sheet_url)
        worksheet = sheet.worksheet("Form Responses 2")
        
        # Get all records
        records = worksheet.get_all_records()
        
        # Find the Candidate ID column
        candidate_id_col = None
        for record in records:
            for key in record.keys():
                if 'candidate id' in key.lower() or 'application id' in key.lower():
                    candidate_id_col = key
                    break
            if candidate_id_col:
                break
        
        # If no Candidate ID column found, try to find it in the header row
        if not candidate_id_col:
            header_row = worksheet.row_values(1)
            for i, header in enumerate(header_row):
                if 'candidate id' in header.lower() or 'application id' in header.lower():
                    candidate_id_col = header
                    break
        
        if not candidate_id_col:
            # If still not found, we need to add it
            return False, "No Candidate ID column found in the Google Sheet"
        
        # Find the row with the matching identifier
        row_index = None
        for i, record in enumerate(records):
            if record.get(candidate_id_col) == identifier:
                # Add 2 to account for header row and 0-indexing
                row_index = i + 2
                break
        
        if not row_index:
            return False, f"No row found with identifier: {identifier}"
        
        # Get the header row to find column indices
        header_row = worksheet.row_values(1)
        
        # Update each field
        for column_name, value in updates.items():
            # Find the column index
            col_index = None
            for i, header in enumerate(header_row):
                if header == column_name:
                    # Add 1 to account for 0-indexing
                    col_index = i + 1
                    break
            
            if col_index:
                # Update the cell
                worksheet.update_cell(row_index, col_index, value)
            else:
                print(f"Warning: Column '{column_name}' not found in the Google Sheet")
        
        return True, f"Successfully updated row for identifier: {identifier}"
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, f"Error updating Google Sheet: {str(e)}"

def get_google_sheet_row_by_candidate_id(identifier):
    """
    Get a row from the Google Sheet based on an identifier (email, application_id).
    
    Args:
        identifier (str): The identifier (email, application_id) to identify the row to retrieve
        
    Returns:
        tuple: (success, result) where success is a boolean and result is either a dict or an error message
    """
    if not identifier:
        return False, "No identifier provided"
    
    try:
        # Set up credentials
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        
        if not os.path.exists('google_key.json'):
            return False, "Google API key file not found"
        
        creds = ServiceAccountCredentials.from_json_keyfile_name('google_key.json', scope)
        client = gspread.authorize(creds)
        
        # Open the Google Sheet
        sheet_url = "https://docs.google.com/spreadsheets/d/1V0Sf65ZVrebpopBfg2vwk-_PjRxgqlbytIX-L2GImAE/edit?resourcekey=&gid=1400567486"
        sheet = client.open_by_url(sheet_url)
        worksheet = sheet.worksheet("Form Responses 2")
        
        # Get all records
        records = worksheet.get_all_records()
        
        # Find the Candidate ID column
        candidate_id_col = None
        for record in records:
            for key in record.keys():
                if 'candidate id' in key.lower() or 'application id' in key.lower():
                    candidate_id_col = key
                    break
            if candidate_id_col:
                break
        
        # If no Candidate ID column found, try to find it in the header row
        if not candidate_id_col:
            header_row = worksheet.row_values(1)
            for i, header in enumerate(header_row):
                if 'candidate id' in header.lower() or 'application id' in header.lower():
                    candidate_id_col = header
                    break
        
        if not candidate_id_col:
            return False, "No Candidate ID column found in the Google Sheet"
        
        # Find the row with the matching identifier
        for record in records:
            if record.get(candidate_id_col) == identifier:
                return True, record
        
        return False, f"No row found with identifier: {identifier}"
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, f"Error retrieving row from Google Sheet: {str(e)}"

def log_cv_view_in_firestore(candidate_identifier, interviewer_email, cv_url=None):
    """
    Log CV view access in Firestore.
    
    Args:
        candidate_identifier (str): The identifier (email, application_id) of the candidate whose CV is being viewed
        interviewer_email (str): The email of the interviewer viewing the CV
        cv_url (str, optional): The URL of the CV being viewed
        
    Returns:
        tuple: (success, message) where success is a boolean and message is a string
    """
    if not candidate_identifier or not interviewer_email:
        return False, "Candidate identifier and interviewer email are required"
    
    try:
        from firebase_admin import firestore
        db = firestore.client()
        
        # Create a log entry
        log_entry = {
            "candidate_identifier": candidate_identifier,
            "interviewer_email": interviewer_email,
            "timestamp": firestore.SERVER_TIMESTAMP,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "time": datetime.now().strftime("%H:%M:%S")
        }
        
        if cv_url:
            log_entry["cv_url"] = cv_url
        
        # Add the log entry to Firestore
        db.collection("cv_view_logs").add(log_entry)
        
        # Also update the candidate document if it exists
        # Try to find by application_id or email
        candidate_ref = db.collection("candidates").where("application_id", "==", candidate_identifier).limit(1).stream()
        for doc in candidate_ref:
            doc.reference.update({
                "last_viewed_by": interviewer_email,
                "last_viewed_at": firestore.SERVER_TIMESTAMP
            })
        
        return True, "CV view logged successfully"
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, f"Error logging CV view: {str(e)}"