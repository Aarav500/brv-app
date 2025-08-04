import os
import uuid
from datetime import datetime
from io import BytesIO
import traceback
from typing import Optional, Tuple, Dict, Any

# Google Drive API imports
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload, MediaIoBaseDownload
from oauth2client.service_account import ServiceAccountCredentials

# Import from env_config.py
from env_config import (
    GOOGLE_DRIVE_FOLDER_ID,
    GOOGLE_SERVICE_ACCOUNT_FILE
)

# Import from oracle_candidates.py
from oracle_candidates import update_resume_link

def get_drive_service():
    """
    Get an authenticated Google Drive service.
    
    Returns:
        googleapiclient.discovery.Resource: Authenticated Google Drive service
    """
    try:
        # Check if credentials file exists
        if not os.path.exists(GOOGLE_SERVICE_ACCOUNT_FILE):
            print(f"❌ Google API key file not found: {GOOGLE_SERVICE_ACCOUNT_FILE}")
            return None
            
        # Set up credentials
        scope = ['https://www.googleapis.com/auth/drive']
        credentials = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SERVICE_ACCOUNT_FILE, scope)
        
        # Build the Drive API client
        service = build('drive', 'v3', credentials=credentials)
        return service
    except Exception as e:
        print(f"❌ Error creating Google Drive service: {e}")
        traceback.print_exc()
        return None

def init_drive_folder():
    """
    Initialize the Google Drive folder for storing resumes.
    If the folder doesn't exist, create it.
    
    Returns:
        str: The folder ID
    """
    try:
        # Get Google Drive service
        service = get_drive_service()
        if not service:
            print("❌ Failed to initialize Google Drive service")
            return None
            
        # Check if folder ID is provided in environment variables
        if GOOGLE_DRIVE_FOLDER_ID:
            # Verify the folder exists
            try:
                folder = service.files().get(fileId=GOOGLE_DRIVE_FOLDER_ID).execute()
                print(f"✅ Using existing Google Drive folder: {folder.get('name')} ({GOOGLE_DRIVE_FOLDER_ID})")
                return GOOGLE_DRIVE_FOLDER_ID
            except Exception as e:
                print(f"❌ Error accessing Google Drive folder: {e}")
                # Continue to create a new folder
        
        # Create a new folder
        folder_metadata = {
            'name': 'BRV_Resumes',
            'mimeType': 'application/vnd.google-apps.folder'
        }
        
        folder = service.files().create(
            body=folder_metadata,
            fields='id,name'
        ).execute()
        
        folder_id = folder.get('id')
        folder_name = folder.get('name')
        
        print(f"✅ Created new Google Drive folder: {folder_name} ({folder_id})")
        print(f"⚠️ Please set GOOGLE_DRIVE_FOLDER_ID environment variable to: {folder_id}")
        
        return folder_id
    except Exception as e:
        print(f"❌ Error initializing Google Drive folder: {e}")
        traceback.print_exc()
        return None

def upload_resume(candidate_id: str, file_content: bytes, filename: str) -> Tuple[bool, Optional[str], str]:
    """
    Upload a resume to Google Drive and update the candidate's resume_link in the database.
    
    Args:
        candidate_id (str): The candidate's ID
        file_content (bytes): The content of the resume file
        filename (str): The original filename
        
    Returns:
        Tuple[bool, Optional[str], str]: (success, file_url, message)
    """
    try:
        # Get Google Drive service
        service = get_drive_service()
        if not service:
            return False, None, "Failed to initialize Google Drive service"
            
        # Initialize or get the folder ID
        folder_id = init_drive_folder()
        if not folder_id:
            return False, None, "Failed to initialize Google Drive folder"
            
        # Get file extension
        _, file_extension = os.path.splitext(filename)
        
        # Create a unique filename using the candidate ID
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        storage_filename = f"Resume_{candidate_id}_{timestamp}{file_extension}"
        
        # Prepare file metadata
        file_metadata = {
            'name': storage_filename,
            'parents': [folder_id]
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
        
        # Update the candidate's resume_link in the database
        success, message = update_resume_link(candidate_id, file_url)
        if not success:
            print(f"⚠️ Warning: Resume uploaded to Google Drive but failed to update candidate record: {message}")
            return True, file_url, f"Resume uploaded but failed to update candidate record: {message}"
        
        print(f"✅ Resume uploaded for candidate {candidate_id}: {storage_filename} → {file_url}")
        return True, file_url, "Resume uploaded successfully"
    except Exception as e:
        print(f"❌ Error uploading resume: {e}")
        traceback.print_exc()
        return False, None, f"Error uploading resume: {str(e)}"

def download_resume(resume_link: str) -> Tuple[bool, Optional[bytes], str]:
    """
    Download a resume from Google Drive.
    
    Args:
        resume_link (str): The Google Drive link to the resume
        
    Returns:
        Tuple[bool, Optional[bytes], str]: (success, file_content, message)
    """
    try:
        # Get Google Drive service
        service = get_drive_service()
        if not service:
            return False, None, "Failed to initialize Google Drive service"
            
        # Extract file ID from the link
        file_id = extract_file_id_from_link(resume_link)
        if not file_id:
            return False, None, f"Invalid Google Drive link: {resume_link}"
            
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
        return True, file_content.read(), "Resume downloaded successfully"
    except Exception as e:
        print(f"❌ Error downloading resume: {e}")
        traceback.print_exc()
        return False, None, f"Error downloading resume: {str(e)}"

def delete_resume(resume_link: str) -> Tuple[bool, str]:
    """
    Delete a resume from Google Drive.
    
    Args:
        resume_link (str): The Google Drive link to the resume
        
    Returns:
        Tuple[bool, str]: (success, message)
    """
    try:
        # Get Google Drive service
        service = get_drive_service()
        if not service:
            return False, "Failed to initialize Google Drive service"
            
        # Extract file ID from the link
        file_id = extract_file_id_from_link(resume_link)
        if not file_id:
            return False, f"Invalid Google Drive link: {resume_link}"
            
        # Delete the file
        service.files().delete(fileId=file_id).execute()
        
        print(f"✅ Resume deleted: {resume_link}")
        return True, "Resume deleted successfully"
    except Exception as e:
        print(f"❌ Error deleting resume: {e}")
        traceback.print_exc()
        return False, f"Error deleting resume: {str(e)}"

def extract_file_id_from_link(link: str) -> Optional[str]:
    """
    Extract the file ID from a Google Drive link.
    
    Args:
        link (str): The Google Drive link
        
    Returns:
        Optional[str]: The file ID or None if not found
    """
    try:
        # Handle different types of Google Drive links
        if '/file/d/' in link:
            # Format: https://drive.google.com/file/d/FILE_ID/view
            file_id = link.split('/file/d/')[1].split('/')[0]
        elif 'id=' in link:
            # Format: https://drive.google.com/open?id=FILE_ID
            file_id = link.split('id=')[1].split('&')[0]
        elif '/view' in link:
            # Format: https://drive.google.com/file/d/FILE_ID/view
            file_id = link.split('/view')[0].split('/')[-1]
        elif 'drive.google.com' in link and len(link.split('/')) <= 5:
            # Format: https://drive.google.com/FILE_ID
            file_id = link.split('/')[-1]
        else:
            # Assume the link is already a file ID
            file_id = link
        
        return file_id
    except Exception as e:
        print(f"❌ Error extracting file ID from link: {e}")
        return None

def get_resume_info(resume_link: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """
    Get information about a resume file in Google Drive.
    
    Args:
        resume_link (str): The Google Drive link to the resume
        
    Returns:
        Tuple[bool, Optional[Dict[str, Any]], str]: (success, file_info, message)
    """
    try:
        # Get Google Drive service
        service = get_drive_service()
        if not service:
            return False, None, "Failed to initialize Google Drive service"
            
        # Extract file ID from the link
        file_id = extract_file_id_from_link(resume_link)
        if not file_id:
            return False, None, f"Invalid Google Drive link: {resume_link}"
            
        # Get file metadata
        file = service.files().get(
            fileId=file_id,
            fields='id,name,mimeType,size,createdTime,modifiedTime,webViewLink,webContentLink'
        ).execute()
        
        # Return the file information
        return True, file, "Resume information retrieved successfully"
    except Exception as e:
        print(f"❌ Error getting resume information: {e}")
        traceback.print_exc()
        return False, None, f"Error getting resume information: {str(e)}"

def list_resumes(limit: int = 100) -> Tuple[bool, Optional[list], str]:
    """
    List all resumes in the Google Drive folder.
    
    Args:
        limit (int, optional): Maximum number of resumes to return. Defaults to 100.
        
    Returns:
        Tuple[bool, Optional[list], str]: (success, files, message)
    """
    try:
        # Get Google Drive service
        service = get_drive_service()
        if not service:
            return False, None, "Failed to initialize Google Drive service"
            
        # Initialize or get the folder ID
        folder_id = init_drive_folder()
        if not folder_id:
            return False, None, "Failed to initialize Google Drive folder"
            
        # List files in the folder
        query = f"'{folder_id}' in parents and trashed = false"
        results = service.files().list(
            q=query,
            pageSize=limit,
            fields="files(id, name, mimeType, size, createdTime, modifiedTime, webViewLink, webContentLink)"
        ).execute()
        
        files = results.get('files', [])
        
        return True, files, f"Found {len(files)} resumes"
    except Exception as e:
        print(f"❌ Error listing resumes: {e}")
        traceback.print_exc()
        return False, None, f"Error listing resumes: {str(e)}"

def init_storage():
    """
    Initialize the Google Drive storage.
    This is a wrapper around init_drive_folder for compatibility with the old API.
    
    Returns:
        bool: True if successful, False otherwise
    """
    folder_id = init_drive_folder()
    return folder_id is not None

def upload_cv(candidate_id, file_content, filename):
    """
    Upload a CV file to Google Drive.
    This is a wrapper around upload_resume for compatibility with the old API.
    
    Args:
        candidate_id (str): The candidate's ID
        file_content (bytes): The content of the CV file
        filename (str): The original filename
        
    Returns:
        str: The URL of the uploaded file or None if upload failed
    """
    success, file_url, _ = upload_resume(candidate_id, file_content, filename)
    return file_url if success else None

def download_cv(cv_url):
    """
    Download a CV file from Google Drive.
    This is a wrapper around download_resume for compatibility with the old API.
    
    Args:
        cv_url (str): The URL of the CV file
        
    Returns:
        bytes: The content of the CV file or None if download failed
    """
    success, file_content, _ = download_resume(cv_url)
    return file_content if success else None

def delete_cv(cv_url):
    """
    Delete a CV file from Google Drive.
    This is a wrapper around delete_resume for compatibility with the old API.
    
    Args:
        cv_url (str): The URL of the CV file
        
    Returns:
        bool: True if the file was deleted successfully, False otherwise
    """
    success, _ = delete_resume(cv_url)
    return success