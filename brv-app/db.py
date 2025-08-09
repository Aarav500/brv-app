"""
Centralized Database Module for BRV Applicant Management System

This module serves as the main entry point for all database operations,
using Oracle Autonomous Database for storage. It imports and re-exports
functions from oracle_db.py, user_auth.py, and oracle_candidates.py.

All database operations should go through this module to ensure consistency
and to make future database migrations easier.
"""

import uuid
from datetime import datetime

# Import from oracle_db.py
from oracle_db import (
    init_oracle_client,
    get_connection_pool,
    get_db_connection,
    close_connection,
    execute_query,
    execute_across_all_dbs,
    get_db_config,
    update_db_config,
    test_connection
)

# Import from user_auth.py
from user_auth import (
    authenticate_user
)

# Import from oracle_candidates.py
from oracle_candidates import (
    update_interview_status
)

# Import from db_auto_scaling.py

# Re-export all imported functions to provide a unified interface

# Initialize the database connection
def init_db():
    """
    Initialize the database connection.
    
    Returns:
        bool: True if successful, False otherwise
    """
    return init_oracle_client()

# Authentication wrapper functions
def authenticate(username_or_email, password):
    """
    Authenticate a user.
    
    Args:
        username_or_email (str): The username or email
        password (str): The password
        
    Returns:
        tuple: (success, user_data, message)
    """
    return authenticate_user(username_or_email, password)

# Log activity to the activity_log table
def log_activity(user_id, action, details=None):
    """
    Log an activity to the activity_log table.
    
    Args:
        user_id (str): The ID of the user performing the action
        action (str): The action being performed
        details (str, optional): Additional details about the action
        
    Returns:
        bool: True if successful, False otherwise
    """
    query = """
    INSERT INTO activity_log (
        log_id,
        user_id,
        action,
        details,
        timestamp
    ) VALUES (
        :log_id,
        :user_id,
        :action,
        :details,
        :timestamp
    )
    """
    
    params = {
        "log_id": str(uuid.uuid4()),
        "user_id": user_id,
        "action": action,
        "details": details,
        "timestamp": datetime.now()
    }
    
    result = execute_query(query, params, commit=True)
    return result is not None

# Get activity logs
def get_activity_logs(limit=100, offset=0, user_id=None, action=None, start_date=None, end_date=None):
    """
    Get activity logs with optional filtering.
    
    Args:
        limit (int, optional): Maximum number of logs to return. Defaults to 100.
        offset (int, optional): Number of logs to skip. Defaults to 0.
        user_id (str, optional): Filter by user ID. Defaults to None.
        action (str, optional): Filter by action. Defaults to None.
        start_date (str, optional): Filter by start date (YYYY-MM-DD). Defaults to None.
        end_date (str, optional): Filter by end date (YYYY-MM-DD). Defaults to None.
        
    Returns:
        list: List of activity logs
    """
    # Build the WHERE clause and parameters dynamically
    where_clauses = []
    params = {}
    
    if user_id:
        where_clauses.append("user_id = :user_id")
        params["user_id"] = user_id
    
    if action:
        where_clauses.append("action = :action")
        params["action"] = action
    
    if start_date:
        where_clauses.append("timestamp >= TO_TIMESTAMP(:start_date, 'YYYY-MM-DD')")
        params["start_date"] = start_date
    
    if end_date:
        where_clauses.append("timestamp <= TO_TIMESTAMP(:end_date, 'YYYY-MM-DD') + INTERVAL '1' DAY")
        params["end_date"] = end_date
    
    # Build the query
    query = """
    SELECT 
        log_id,
        user_id,
        action,
        details,
        TO_CHAR(timestamp, 'YYYY-MM-DD HH24:MI:SS') as timestamp
    FROM activity_log 
    """
    
    if where_clauses:
        query += f"WHERE {' AND '.join(where_clauses)} "
    
    query += "ORDER BY timestamp DESC"
    
    # Execute the query
    all_logs = execute_across_all_dbs(query, params) or []
    
    # Apply pagination
    paginated_logs = all_logs[offset:offset+limit] if all_logs else []
    
    return paginated_logs

# Resume metadata functions
def add_resume_metadata(resume_id, candidate_id, filename, file_size, mime_type, upload_date, resume_link):
    """
    Add metadata for a resume.
    
    Args:
        resume_id (str): The ID of the resume
        candidate_id (str): The ID of the candidate
        filename (str): The original filename
        file_size (int): The file size in bytes
        mime_type (str): The MIME type of the file
        upload_date (datetime): The upload date
        resume_link (str): The link to the resume in Google Drive
        
    Returns:
        bool: True if successful, False otherwise
    """
    query = """
    INSERT INTO resumes_metadata (
        resume_id,
        candidate_id,
        filename,
        file_size,
        mime_type,
        upload_date,
        resume_link
    ) VALUES (
        :resume_id,
        :candidate_id,
        :filename,
        :file_size,
        :mime_type,
        :upload_date,
        :resume_link
    )
    """
    
    params = {
        "resume_id": resume_id,
        "candidate_id": candidate_id,
        "filename": filename,
        "file_size": file_size,
        "mime_type": mime_type,
        "upload_date": upload_date,
        "resume_link": resume_link
    }
    
    result = execute_query(query, params, commit=True)
    return result is not None

def get_resume_metadata(resume_id=None, candidate_id=None):
    """
    Get metadata for a resume.
    
    Args:
        resume_id (str, optional): The ID of the resume. Defaults to None.
        candidate_id (str, optional): The ID of the candidate. Defaults to None.
        
    Returns:
        dict or list: Resume metadata
    """
    if resume_id:
        # Get a specific resume
        query = """
        SELECT 
            resume_id,
            candidate_id,
            filename,
            file_size,
            mime_type,
            TO_CHAR(upload_date, 'YYYY-MM-DD HH24:MI:SS') as upload_date,
            resume_link
        FROM resumes_metadata 
        WHERE resume_id = :resume_id
        """
        
        return execute_across_all_dbs(query, {"resume_id": resume_id}, fetchone=True)
    
    elif candidate_id:
        # Get all resumes for a candidate
        query = """
        SELECT 
            resume_id,
            candidate_id,
            filename,
            file_size,
            mime_type,
            TO_CHAR(upload_date, 'YYYY-MM-DD HH24:MI:SS') as upload_date,
            resume_link
        FROM resumes_metadata 
        WHERE candidate_id = :candidate_id
        ORDER BY upload_date DESC
        """
        
        return execute_across_all_dbs(query, {"candidate_id": candidate_id}) or []
    
    else:
        # Get all resumes
        query = """
        SELECT 
            resume_id,
            candidate_id,
            filename,
            file_size,
            mime_type,
            TO_CHAR(upload_date, 'YYYY-MM-DD HH24:MI:SS') as upload_date,
            resume_link
        FROM resumes_metadata 
        ORDER BY upload_date DESC
        """
        
        return execute_across_all_dbs(query) or []

def delete_resume_metadata(resume_id):
    """
    Delete metadata for a resume.
    
    Args:
        resume_id (str): The ID of the resume
        
    Returns:
        bool: True if successful, False otherwise
    """
    query = """
    DELETE FROM resumes_metadata 
    WHERE resume_id = :resume_id
    """
    
    result = execute_query(query, {"resume_id": resume_id}, commit=True)
    return result is not None

# Interview management functions
def create_interview(candidate_id, interviewer_id, scheduled_time, notes=None):
    """
    Create a new interview.
    
    Args:
        candidate_id (str): The ID of the candidate
        interviewer_id (str): The ID of the interviewer
        scheduled_time (str): The scheduled time (YYYY-MM-DD HH:MM:SS)
        notes (str, optional): Additional notes. Defaults to None.
        
    Returns:
        tuple: (success, interview_id, message)
    """
    # Generate a UUID for the interview
    interview_id = str(uuid.uuid4())
    
    query = """
    INSERT INTO interviews (
        interview_id,
        candidate_id,
        interviewer_id,
        scheduled_time,
        feedback,
        status,
        created_at,
        updated_at
    ) VALUES (
        :interview_id,
        :candidate_id,
        :interviewer_id,
        TO_TIMESTAMP(:scheduled_time, 'YYYY-MM-DD HH24:MI:SS'),
        :feedback,
        :status,
        CURRENT_TIMESTAMP,
        CURRENT_TIMESTAMP
    )
    """
    
    params = {
        "interview_id": interview_id,
        "candidate_id": candidate_id,
        "interviewer_id": interviewer_id,
        "scheduled_time": scheduled_time,
        "feedback": notes,
        "status": "scheduled"
    }
    
    result = execute_query(query, params, commit=True)
    
    if result is not None:
        # Update candidate status
        update_interview_status(candidate_id, "Interview Scheduled")
        return True, interview_id, "Interview scheduled successfully"
    else:
        return False, None, "Failed to schedule interview"

def get_interviews_by_candidate(candidate_id):
    """
    Get all interviews for a candidate.
    
    Args:
        candidate_id (str): The ID of the candidate
        
    Returns:
        list: List of interviews
    """
    query = """
    SELECT 
        i.interview_id,
        i.candidate_id,
        i.interviewer_id,
        u.username as interviewer_name,
        TO_CHAR(i.scheduled_time, 'YYYY-MM-DD HH24:MI:SS') as scheduled_time,
        i.feedback,
        i.status,
        i.result,
        TO_CHAR(i.created_at, 'YYYY-MM-DD HH24:MI:SS') as created_at,
        TO_CHAR(i.updated_at, 'YYYY-MM-DD HH24:MI:SS') as updated_at
    FROM interviews i
    LEFT JOIN users u ON i.interviewer_id = u.user_id
    WHERE i.candidate_id = :candidate_id
    ORDER BY i.scheduled_time DESC
    """
    
    return execute_across_all_dbs(query, {"candidate_id": candidate_id}) or []

def get_interviews_by_interviewer(interviewer_id):
    """
    Get all interviews for an interviewer.
    
    Args:
        interviewer_id (str): The ID of the interviewer
        
    Returns:
        list: List of interviews
    """
    query = """
    SELECT 
        i.interview_id,
        i.candidate_id,
        c.full_name as candidate_name,
        i.interviewer_id,
        TO_CHAR(i.scheduled_time, 'YYYY-MM-DD HH24:MI:SS') as scheduled_time,
        i.feedback,
        i.status,
        i.result,
        TO_CHAR(i.created_at, 'YYYY-MM-DD HH24:MI:SS') as created_at,
        TO_CHAR(i.updated_at, 'YYYY-MM-DD HH24:MI:SS') as updated_at
    FROM interviews i
    LEFT JOIN candidates c ON i.candidate_id = c.candidate_id
    WHERE i.interviewer_id = :interviewer_id
    ORDER BY i.scheduled_time DESC
    """
    
    return execute_across_all_dbs(query, {"interviewer_id": interviewer_id}) or []

def update_interview_feedback(interview_id, feedback, result):
    """
    Update interview feedback and result.
    
    Args:
        interview_id (str): The ID of the interview
        feedback (str): The feedback
        result (str): The result (e.g., "pass", "fail")
        
    Returns:
        tuple: (success, message)
    """
    query = """
    UPDATE interviews 
    SET 
        feedback = :feedback,
        result = :result,
        status = :status,
        updated_at = CURRENT_TIMESTAMP
    WHERE interview_id = :interview_id
    """
    
    params = {
        "feedback": feedback,
        "result": result,
        "status": result,  # Use result as status
        "interview_id": interview_id
    }
    
    result_update = execute_query(query, params, commit=True)
    
    if result_update is not None:
        # Get the candidate ID
        query = "SELECT candidate_id FROM interviews WHERE interview_id = :interview_id"
        interview = execute_across_all_dbs(query, {"interview_id": interview_id}, fetchone=True)
        
        if interview:
            # Update candidate status
            update_interview_status(interview["candidate_id"], result)
            return True, "Interview feedback updated successfully"
        else:
            return False, "Interview found but failed to update candidate status"
    else:
        return False, "Failed to update interview feedback"

# Test the database connection
if __name__ == "__main__":
    print("Testing database connection...")
    if test_connection():
        print("Database connection successful!")
    else:
        print("Database connection failed!")