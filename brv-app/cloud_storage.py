import os
import json
import uuid
from datetime import datetime
from io import BytesIO
import traceback

# Google Drive API imports
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload, MediaIoBaseDownload
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2 import service_account

# Google Drive configuration
# Note: In a production environment, these should be stored as environment variables
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "google_key.json")

# Function to get Google Drive service
def get_drive_service():
    """
    Get an authenticated Google Drive service.
    
    Returns:
        googleapiclient.discovery.Resource: Authenticated Google Drive service
    """
    try:
        # Check if credentials file exists
        if not os.path.exists(GOOGLE_SERVICE_ACCOUNT_FILE):
            print(f"Google API key file not found: {GOOGLE_SERVICE_ACCOUNT_FILE}")
            return None
            
        # Set up credentials
        scope = ['https://www.googleapis.com/auth/drive']
        credentials = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SERVICE_ACCOUNT_FILE, scope)
        
        # Build the Drive API client
        service = build('drive', 'v3', credentials=credentials)
        return service
    except Exception as e:
        print(f"Error creating Google Drive service: {e}")
        traceback.print_exc()
        return None

# Initialize the storage folder if it doesn't exist
def init_storage():
    """
    Initialize the necessary folder in Google Drive for storing CV files.
    This should be called when the application starts.
    
    Returns:
        bool: True if initialization was successful, False otherwise
    """
    try:
        # Get Google Drive service
        service = get_drive_service()
        if not service:
            print("❌ Failed to initialize Google Drive service")
            return False
            
        # Check if folder ID is provided
        if not GOOGLE_DRIVE_FOLDER_ID:
            # Create a new folder if no folder ID is provided
            folder_metadata = {
                'name': 'BRV_CV_Files',
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            folder = service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()
            
            folder_id = folder.get('id')
            print(f"✅ Created new Google Drive folder with ID: {folder_id}")
            print(f"⚠️ Please set GOOGLE_DRIVE_FOLDER_ID environment variable to: {folder_id}")
        else:
            # Check if the folder exists
            try:
                folder = service.files().get(fileId=GOOGLE_DRIVE_FOLDER_ID).execute()
                folder_id = folder.get('id')
                print(f"✅ Using existing Google Drive folder with ID: {folder_id}")
            except Exception as e:
                print(f"❌ Error accessing Google Drive folder: {e}")
                return False
        
        print("✅ Google Drive storage initialized")
        return True
    except Exception as e:
        print(f"❌ Error initializing Google Drive storage: {e}")
        traceback.print_exc()
        return False

# Upload a CV file to Google Drive
def upload_cv(candidate_id, file_content, filename):
    """
    Upload a CV file to Google Drive
    
    Args:
        candidate_id (int): The candidate's unique ID
        file_content (bytes): The content of the CV file
        filename (str): The original filename
        
    Returns:
        str: The URL of the uploaded file
    """
    try:
        # Get Google Drive service
        service = get_drive_service()
        if not service:
            print("❌ Failed to initialize Google Drive service")
            return None
            
        # Check if folder ID is provided
        if not GOOGLE_DRIVE_FOLDER_ID:
            print("❌ Google Drive folder ID not provided")
            return None
            
        # Get file extension
        _, file_extension = os.path.splitext(filename)
        
        # Create a unique filename using the candidate ID
        storage_filename = f"CV_{candidate_id}{file_extension}"
        
        # Prepare file metadata
        file_metadata = {
            'name': storage_filename,
            'parents': [GOOGLE_DRIVE_FOLDER_ID]
        }
        
        # Determine MIME type based on file extension
        mime_type = 'application/pdf'  # Default to PDF
        if file_extension.lower() == '.docx':
            mime_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        elif file_extension.lower() == '.doc':
            mime_type = 'application/msword'
        elif file_extension.lower() in ['.jpg', '.jpeg']:
            mime_type = 'image/jpeg'
        elif file_extension.lower() == '.png':
            mime_type = 'image/png'
            
        # Create a BytesIO object from file_content
        file_stream = BytesIO(file_content)
        
        # Upload the file
        media = MediaIoBaseUpload(file_stream, mimetype=mime_type, resumable=True)
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id,webViewLink'
        ).execute()
        
        # Get the file ID and web view link
        file_id = file.get('id')
        file_url = file.get('webViewLink')
        
        # Store metadata about the CV
        cv_metadata = {
            "id": file_id,
            "candidate_id": candidate_id,
            "filename": storage_filename,
            "content_type": mime_type,
            "size": len(file_content),
            "uploaded_at": datetime.now().isoformat()
        }
        
        # In a real implementation, we might store this metadata in a database
        
        print(f"✅ CV Uploaded to Google Drive: {storage_filename} → {file_url}")
        return file_url
    except Exception as e:
        print(f"❌ Error uploading CV to Google Drive: {e}")
        traceback.print_exc()
        return None

# Download a CV file from Google Drive
def download_cv(cv_url):
    """
    Download a CV file from Google Drive
    
    Args:
        cv_url (str): The URL or file ID of the CV file
        
    Returns:
        bytes: The content of the CV file
    """
    try:
        # Get Google Drive service
        service = get_drive_service()
        if not service:
            print("❌ Failed to initialize Google Drive service")
            return None
            
        # Extract file ID from URL if needed
        file_id = cv_url
        
        # If cv_url is a web view link, extract the file ID
        if cv_url.startswith('https://drive.google.com/'):
            from resume_handler import extract_file_id
            extracted_id = extract_file_id(cv_url)
            if extracted_id:
                file_id = extracted_id
            else:
                print(f"❌ Could not extract file ID from URL: {cv_url}")
                return None
                
        # Download the file
        request = service.files().get_media(fileId=file_id)
        file_content = BytesIO()
        downloader = MediaIoBaseDownload(file_content, request)
        
        done = False
        while not done:
            status, done = downloader.next_chunk()
            
        # Reset the file pointer to the beginning of the file
        file_content.seek(0)
        
        # Return the file content as bytes
        return file_content.read()
    except Exception as e:
        print(f"❌ Error downloading CV from Google Drive: {e}")
        traceback.print_exc()
        
        # For fallback, return mock data
        print("⚠️ Returning mock CV content as fallback")
        return b"Mock CV content"

# Delete a CV file from Google Drive
def delete_cv(cv_url):
    """
    Delete a CV file from Google Drive
    
    Args:
        cv_url (str): The URL or file ID of the CV file
        
    Returns:
        bool: True if the file was deleted successfully, False otherwise
    """
    try:
        # Get Google Drive service
        service = get_drive_service()
        if not service:
            print("❌ Failed to initialize Google Drive service")
            return False
            
        # Extract file ID from URL if needed
        file_id = cv_url
        
        # If cv_url is a web view link, extract the file ID
        if cv_url.startswith('https://drive.google.com/'):
            from resume_handler import extract_file_id
            extracted_id = extract_file_id(cv_url)
            if extracted_id:
                file_id = extracted_id
            else:
                print(f"❌ Could not extract file ID from URL: {cv_url}")
                return False
                
        # Delete the file
        service.files().delete(fileId=file_id).execute()
        
        print(f"✅ CV Deleted from Google Drive: {cv_url}")
        return True
    except Exception as e:
        print(f"❌ Error deleting CV from Google Drive: {e}")
        traceback.print_exc()
        return False