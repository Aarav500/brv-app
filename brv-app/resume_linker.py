import os
import shutil
import uuid
from datetime import datetime
import logging
from cloud_storage import upload_cv
from mysql_db import get_candidate_by_id, update_candidate as update_candidate_data

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='resume_linker.log'
)
logger = logging.getLogger('resume_linker')

# Directory for temporary CV storage before upload
TEMP_CV_DIR = "resumes"

def ensure_temp_directory():
    """
    Ensure the temporary directory for CV storage exists
    """
    if not os.path.exists(TEMP_CV_DIR):
        os.makedirs(TEMP_CV_DIR)
        logger.info(f"Created temporary CV directory: {TEMP_CV_DIR}")

def save_temp_cv(file_content, filename):
    """
    Save a CV file temporarily before linking it to a candidate
    
    Args:
        file_content (bytes): The content of the CV file
        filename (str): The original filename
        
    Returns:
        str: The path to the temporarily saved file
    """
    ensure_temp_directory()
    
    # Generate a unique filename to avoid collisions
    unique_filename = f"{uuid.uuid4()}_{filename}"
    temp_path = os.path.join(TEMP_CV_DIR, unique_filename)
    
    # Save the file
    with open(temp_path, 'wb') as f:
        f.write(file_content)
    
    logger.info(f"Saved temporary CV: {temp_path}")
    return temp_path

def link_cv_to_candidate(candidate_id, cv_path=None, cv_content=None, filename=None):
    """
    Link a CV to a candidate by uploading it to cloud storage
    
    Args:
        candidate_id (str): The candidate's unique ID
        cv_path (str, optional): Path to the CV file
        cv_content (bytes, optional): The content of the CV file
        filename (str, optional): The original filename
        
    Returns:
        str: The URL of the uploaded CV
    """
    # Validate that we have either a path or content+filename
    if cv_path is None and (cv_content is None or filename is None):
        raise ValueError("Either cv_path or both cv_content and filename must be provided")
    
    # If we have a path, read the file content
    if cv_path is not None:
        filename = os.path.basename(cv_path)
        with open(cv_path, 'rb') as f:
            cv_content = f.read()
    
    # Upload the CV to cloud storage
    cv_url = upload_cv(candidate_id, cv_content, filename)
    
    # Update the candidate record with the CV URL
    update_candidate_data(candidate_id, {
        "cv_url": cv_url,
        "cv_status": "Uploaded"
    })
    
    logger.info(f"Linked CV to candidate {candidate_id}: {cv_url}")
    
    # Clean up temporary file if it was used
    if cv_path is not None and cv_path.startswith(TEMP_CV_DIR):
        try:
            os.remove(cv_path)
            logger.info(f"Removed temporary CV: {cv_path}")
        except Exception as e:
            logger.warning(f"Failed to remove temporary CV {cv_path}: {str(e)}")
    
    return cv_url

def process_cv_upload(candidate_id, uploaded_file):
    """
    Process a CV upload from a Streamlit file uploader
    
    Args:
        candidate_id (str): The candidate's unique ID
        uploaded_file: A Streamlit UploadedFile object
        
    Returns:
        str: The URL of the uploaded CV
    """
    # Check if the candidate exists
    candidate = get_candidate_by_id(candidate_id)
    if not candidate:
        raise ValueError(f"Candidate with ID {candidate_id} not found")
    
    # Read the file content
    file_content = uploaded_file.read()
    filename = uploaded_file.name
    
    # Link the CV to the candidate
    cv_url = link_cv_to_candidate(
        candidate_id=candidate_id,
        cv_content=file_content,
        filename=filename
    )
    
    return cv_url

def verify_cv_link(candidate_id):
    """
    Verify that a candidate has a CV linked to their profile
    
    Args:
        candidate_id (str): The candidate's unique ID
        
    Returns:
        bool: True if the candidate has a CV, False otherwise
    """
    candidate = get_candidate_by_id(candidate_id)
    if not candidate:
        return False
    
    return candidate.get("cv_url") is not None and candidate.get("cv_status") == "Uploaded"

def cleanup_temp_cvs(max_age_hours=24):
    """
    Clean up temporary CV files that are older than the specified age
    
    Args:
        max_age_hours (int): Maximum age of temporary files in hours
        
    Returns:
        int: Number of files removed
    """
    ensure_temp_directory()
    
    now = datetime.now()
    count = 0
    
    for filename in os.listdir(TEMP_CV_DIR):
        file_path = os.path.join(TEMP_CV_DIR, filename)
        
        # Skip directories
        if os.path.isdir(file_path):
            continue
        
        # Get file modification time
        file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
        age_hours = (now - file_time).total_seconds() / 3600
        
        # Remove old files
        if age_hours > max_age_hours:
            try:
                os.remove(file_path)
                count += 1
                logger.info(f"Removed old temporary CV: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to remove temporary CV {file_path}: {str(e)}")
    
    return count

def update_cv_for_candidate(candidate_id, uploaded_file):
    """
    Update the CV for an existing candidate
    
    Args:
        candidate_id (str): The candidate's unique ID
        uploaded_file: A Streamlit UploadedFile object
        
    Returns:
        str: The URL of the uploaded CV
    """
    return process_cv_upload(candidate_id, uploaded_file)

def get_cv_filename_from_url(cv_url):
    """
    Extract the filename from a CV URL
    
    Args:
        cv_url (str): The URL of the CV
        
    Returns:
        str: The filename
    """
    if not cv_url:
        return None
    
    # Extract the filename from the URL
    # This assumes the URL format is like https://cloud-storage.com/cvs/CAND12345.pdf
    return os.path.basename(cv_url)

# Run cleanup on import to remove old temporary files
cleanup_temp_cvs()