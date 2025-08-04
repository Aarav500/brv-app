import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Union

# Import from oracle_db.py
from oracle_db import execute_query, execute_across_all_dbs

def create_candidate(
    full_name: str,
    email: str,
    phone: str = None,
    additional_phone: str = None,
    dob: str = None,
    caste: str = None,
    sub_caste: str = None,
    marital_status: str = None,
    qualification: str = None,
    work_experience: str = None,
    referral: str = None,
    resume_link: str = None,
    interview_status: str = "pending"
) -> Tuple[bool, Optional[str], str]:
    """
    Create a new candidate in the database.
    
    Args:
        full_name (str): The candidate's full name
        email (str): The candidate's email
        phone (str, optional): The candidate's phone number
        additional_phone (str, optional): The candidate's additional phone number
        dob (str, optional): The candidate's date of birth (YYYY-MM-DD)
        caste (str, optional): The candidate's caste
        sub_caste (str, optional): The candidate's sub-caste
        marital_status (str, optional): The candidate's marital status
        qualification (str, optional): The candidate's qualification
        work_experience (str, optional): The candidate's work experience
        referral (str, optional): How the candidate was referred
        resume_link (str, optional): Link to the candidate's resume in Google Drive
        interview_status (str, optional): The candidate's interview status
        
    Returns:
        Tuple[bool, Optional[str], str]: (success, candidate_id, message)
    """
    # Check if candidate with this email already exists
    existing_candidate = get_candidate_by_email(email)
    if existing_candidate:
        return False, None, f"Candidate with email {email} already exists"
    
    # Generate a UUID for the candidate
    candidate_id = str(uuid.uuid4())
    
    # Current timestamp
    now = datetime.now()
    
    query = """
    INSERT INTO candidates (
        candidate_id,
        full_name,
        email,
        phone,
        additional_phone,
        dob,
        caste,
        sub_caste,
        marital_status,
        qualification,
        work_experience,
        referral,
        resume_link,
        timestamp,
        interview_status
    ) VALUES (
        :candidate_id,
        :full_name,
        :email,
        :phone,
        :additional_phone,
        TO_DATE(:dob, 'YYYY-MM-DD'),
        :caste,
        :sub_caste,
        :marital_status,
        :qualification,
        :work_experience,
        :referral,
        :resume_link,
        :timestamp,
        :interview_status
    )
    """
    
    params = {
        "candidate_id": candidate_id,
        "full_name": full_name,
        "email": email,
        "phone": phone,
        "additional_phone": additional_phone,
        "dob": dob,
        "caste": caste,
        "sub_caste": sub_caste,
        "marital_status": marital_status,
        "qualification": qualification,
        "work_experience": work_experience,
        "referral": referral,
        "resume_link": resume_link,
        "timestamp": now,
        "interview_status": interview_status
    }
    
    result = execute_query(query, params, commit=True)
    
    if result is not None:
        return True, candidate_id, "Candidate created successfully"
    else:
        return False, None, "Failed to create candidate"

def get_candidate_by_id(candidate_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a candidate by ID.
    
    Args:
        candidate_id (str): The candidate's ID
        
    Returns:
        Optional[Dict[str, Any]]: Candidate data or None if not found
    """
    query = """
    SELECT 
        candidate_id,
        full_name,
        email,
        phone,
        additional_phone,
        TO_CHAR(dob, 'YYYY-MM-DD') as dob,
        caste,
        sub_caste,
        marital_status,
        qualification,
        work_experience,
        referral,
        resume_link,
        TO_CHAR(timestamp, 'YYYY-MM-DD HH24:MI:SS') as timestamp,
        interview_status
    FROM candidates 
    WHERE candidate_id = :candidate_id
    """
    
    return execute_across_all_dbs(query, {"candidate_id": candidate_id}, fetchone=True)

def get_candidate_by_email(email: str) -> Optional[Dict[str, Any]]:
    """
    Get a candidate by email.
    
    Args:
        email (str): The candidate's email
        
    Returns:
        Optional[Dict[str, Any]]: Candidate data or None if not found
    """
    query = """
    SELECT 
        candidate_id,
        full_name,
        email,
        phone,
        additional_phone,
        TO_CHAR(dob, 'YYYY-MM-DD') as dob,
        caste,
        sub_caste,
        marital_status,
        qualification,
        work_experience,
        referral,
        resume_link,
        TO_CHAR(timestamp, 'YYYY-MM-DD HH24:MI:SS') as timestamp,
        interview_status
    FROM candidates 
    WHERE email = :email
    """
    
    return execute_across_all_dbs(query, {"email": email}, fetchone=True)

def search_candidates_by_name(name: str) -> List[Dict[str, Any]]:
    """
    Search for candidates by name.
    
    Args:
        name (str): The name to search for
        
    Returns:
        List[Dict[str, Any]]: List of matching candidates
    """
    query = """
    SELECT 
        candidate_id,
        full_name,
        email,
        phone,
        additional_phone,
        TO_CHAR(dob, 'YYYY-MM-DD') as dob,
        caste,
        sub_caste,
        marital_status,
        qualification,
        work_experience,
        referral,
        resume_link,
        TO_CHAR(timestamp, 'YYYY-MM-DD HH24:MI:SS') as timestamp,
        interview_status
    FROM candidates 
    WHERE UPPER(full_name) LIKE UPPER('%' || :name || '%')
    ORDER BY timestamp DESC
    """
    
    return execute_across_all_dbs(query, {"name": name}) or []

def get_all_candidates(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """
    Get all candidates with pagination.
    
    Args:
        limit (int, optional): Maximum number of candidates to return. Defaults to 100.
        offset (int, optional): Number of candidates to skip. Defaults to 0.
        
    Returns:
        List[Dict[str, Any]]: List of candidates
    """
    query = """
    SELECT 
        candidate_id,
        full_name,
        email,
        phone,
        additional_phone,
        TO_CHAR(dob, 'YYYY-MM-DD') as dob,
        caste,
        sub_caste,
        marital_status,
        qualification,
        work_experience,
        referral,
        resume_link,
        TO_CHAR(timestamp, 'YYYY-MM-DD HH24:MI:SS') as timestamp,
        interview_status
    FROM candidates 
    ORDER BY timestamp DESC
    """
    
    # Note: Oracle doesn't support LIMIT/OFFSET directly in the query
    # We'll need to handle pagination in the application code
    all_candidates = execute_across_all_dbs(query) or []
    
    # Apply pagination
    paginated_candidates = all_candidates[offset:offset+limit] if all_candidates else []
    
    return paginated_candidates

def update_candidate(
    candidate_id: str,
    full_name: str = None,
    email: str = None,
    phone: str = None,
    additional_phone: str = None,
    dob: str = None,
    caste: str = None,
    sub_caste: str = None,
    marital_status: str = None,
    qualification: str = None,
    work_experience: str = None,
    referral: str = None,
    resume_link: str = None,
    interview_status: str = None
) -> Tuple[bool, str]:
    """
    Update a candidate's information.
    
    Args:
        candidate_id (str): The candidate's ID
        full_name (str, optional): The candidate's full name
        email (str, optional): The candidate's email
        phone (str, optional): The candidate's phone number
        additional_phone (str, optional): The candidate's additional phone number
        dob (str, optional): The candidate's date of birth (YYYY-MM-DD)
        caste (str, optional): The candidate's caste
        sub_caste (str, optional): The candidate's sub-caste
        marital_status (str, optional): The candidate's marital status
        qualification (str, optional): The candidate's qualification
        work_experience (str, optional): The candidate's work experience
        referral (str, optional): How the candidate was referred
        resume_link (str, optional): Link to the candidate's resume in Google Drive
        interview_status (str, optional): The candidate's interview status
        
    Returns:
        Tuple[bool, str]: (success, message)
    """
    # Get the current candidate data
    current_candidate = get_candidate_by_id(candidate_id)
    if not current_candidate:
        return False, f"Candidate with ID {candidate_id} not found"
    
    # Check if email is being changed and if it's already in use
    if email and email != current_candidate["email"]:
        existing_candidate = get_candidate_by_email(email)
        if existing_candidate and existing_candidate["candidate_id"] != candidate_id:
            return False, f"Email {email} is already in use by another candidate"
    
    # Build the SET clause and parameters dynamically
    set_clauses = []
    params = {"candidate_id": candidate_id}
    
    if full_name is not None:
        set_clauses.append("full_name = :full_name")
        params["full_name"] = full_name
    
    if email is not None:
        set_clauses.append("email = :email")
        params["email"] = email
    
    if phone is not None:
        set_clauses.append("phone = :phone")
        params["phone"] = phone
    
    if additional_phone is not None:
        set_clauses.append("additional_phone = :additional_phone")
        params["additional_phone"] = additional_phone
    
    if dob is not None:
        set_clauses.append("dob = TO_DATE(:dob, 'YYYY-MM-DD')")
        params["dob"] = dob
    
    if caste is not None:
        set_clauses.append("caste = :caste")
        params["caste"] = caste
    
    if sub_caste is not None:
        set_clauses.append("sub_caste = :sub_caste")
        params["sub_caste"] = sub_caste
    
    if marital_status is not None:
        set_clauses.append("marital_status = :marital_status")
        params["marital_status"] = marital_status
    
    if qualification is not None:
        set_clauses.append("qualification = :qualification")
        params["qualification"] = qualification
    
    if work_experience is not None:
        set_clauses.append("work_experience = :work_experience")
        params["work_experience"] = work_experience
    
    if referral is not None:
        set_clauses.append("referral = :referral")
        params["referral"] = referral
    
    if resume_link is not None:
        set_clauses.append("resume_link = :resume_link")
        params["resume_link"] = resume_link
    
    if interview_status is not None:
        set_clauses.append("interview_status = :interview_status")
        params["interview_status"] = interview_status
    
    # If no fields to update, return success
    if not set_clauses:
        return True, "No fields to update"
    
    # Build the query
    query = f"""
    UPDATE candidates 
    SET {', '.join(set_clauses)}
    WHERE candidate_id = :candidate_id
    """
    
    result = execute_query(query, params, commit=True)
    
    if result is not None:
        return True, "Candidate updated successfully"
    else:
        return False, "Failed to update candidate"

def delete_candidate(candidate_id: str) -> Tuple[bool, str]:
    """
    Delete a candidate.
    
    Args:
        candidate_id (str): The ID of the candidate
        
    Returns:
        Tuple[bool, str]: (success, message)
    """
    # Check if candidate exists
    candidate = get_candidate_by_id(candidate_id)
    if not candidate:
        return False, f"Candidate with ID {candidate_id} not found"
    
    # Delete the candidate
    query = """
    DELETE FROM candidates 
    WHERE candidate_id = :candidate_id
    """
    
    result = execute_query(query, {"candidate_id": candidate_id}, commit=True)
    
    if result is not None:
        return True, "Candidate deleted successfully"
    else:
        return False, "Failed to delete candidate"

def update_interview_status(candidate_id: str, status: str) -> Tuple[bool, str]:
    """
    Update a candidate's interview status.
    
    Args:
        candidate_id (str): The ID of the candidate
        status (str): The new interview status
        
    Returns:
        Tuple[bool, str]: (success, message)
    """
    # Check if candidate exists
    candidate = get_candidate_by_id(candidate_id)
    if not candidate:
        return False, f"Candidate with ID {candidate_id} not found"
    
    # Update the interview status
    query = """
    UPDATE candidates 
    SET interview_status = :status
    WHERE candidate_id = :candidate_id
    """
    
    params = {
        "status": status,
        "candidate_id": candidate_id
    }
    
    result = execute_query(query, params, commit=True)
    
    if result is not None:
        return True, f"Interview status updated to {status}"
    else:
        return False, "Failed to update interview status"

def update_resume_link(candidate_id: str, resume_link: str) -> Tuple[bool, str]:
    """
    Update a candidate's resume link.
    
    Args:
        candidate_id (str): The ID of the candidate
        resume_link (str): The new resume link
        
    Returns:
        Tuple[bool, str]: (success, message)
    """
    # Check if candidate exists
    candidate = get_candidate_by_id(candidate_id)
    if not candidate:
        return False, f"Candidate with ID {candidate_id} not found"
    
    # Update the resume link
    query = """
    UPDATE candidates 
    SET resume_link = :resume_link
    WHERE candidate_id = :candidate_id
    """
    
    params = {
        "resume_link": resume_link,
        "candidate_id": candidate_id
    }
    
    result = execute_query(query, params, commit=True)
    
    if result is not None:
        return True, "Resume link updated successfully"
    else:
        return False, "Failed to update resume link"

def search_candidates(
    name: str = None,
    email: str = None,
    phone: str = None,
    interview_status: str = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    Search for candidates with multiple criteria.
    
    Args:
        name (str, optional): Name to search for
        email (str, optional): Email to search for
        phone (str, optional): Phone number to search for
        interview_status (str, optional): Interview status to filter by
        limit (int, optional): Maximum number of candidates to return. Defaults to 100.
        offset (int, optional): Number of candidates to skip. Defaults to 0.
        
    Returns:
        List[Dict[str, Any]]: List of matching candidates
    """
    # Build the WHERE clause and parameters dynamically
    where_clauses = []
    params = {}
    
    if name:
        where_clauses.append("UPPER(full_name) LIKE UPPER('%' || :name || '%')")
        params["name"] = name
    
    if email:
        where_clauses.append("UPPER(email) LIKE UPPER('%' || :email || '%')")
        params["email"] = email
    
    if phone:
        where_clauses.append("phone LIKE '%' || :phone || '%'")
        params["phone"] = phone
    
    if interview_status:
        where_clauses.append("interview_status = :interview_status")
        params["interview_status"] = interview_status
    
    # Build the query
    query = """
    SELECT 
        candidate_id,
        full_name,
        email,
        phone,
        additional_phone,
        TO_CHAR(dob, 'YYYY-MM-DD') as dob,
        caste,
        sub_caste,
        marital_status,
        qualification,
        work_experience,
        referral,
        resume_link,
        TO_CHAR(timestamp, 'YYYY-MM-DD HH24:MI:SS') as timestamp,
        interview_status
    FROM candidates 
    """
    
    if where_clauses:
        query += f"WHERE {' AND '.join(where_clauses)} "
    
    query += "ORDER BY timestamp DESC"
    
    # Execute the query
    all_candidates = execute_across_all_dbs(query, params) or []
    
    # Apply pagination
    paginated_candidates = all_candidates[offset:offset+limit] if all_candidates else []
    
    return paginated_candidates

def get_candidates_by_status(status: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """
    Get candidates by interview status.
    
    Args:
        status (str): The interview status to filter by
        limit (int, optional): Maximum number of candidates to return. Defaults to 100.
        offset (int, optional): Number of candidates to skip. Defaults to 0.
        
    Returns:
        List[Dict[str, Any]]: List of matching candidates
    """
    return search_candidates(interview_status=status, limit=limit, offset=offset)

def count_candidates_by_status() -> Dict[str, int]:
    """
    Count candidates by interview status.
    
    Returns:
        Dict[str, int]: Dictionary with status as key and count as value
    """
    query = """
    SELECT 
        interview_status, 
        COUNT(*) as count
    FROM candidates 
    GROUP BY interview_status
    """
    
    results = execute_across_all_dbs(query) or []
    
    # Convert to dictionary
    counts = {}
    for result in results:
        counts[result["interview_status"] or "unknown"] = result["count"]
    
    return counts