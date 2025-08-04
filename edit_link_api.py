#!/usr/bin/env python3
"""
Google Form Management API

This Flask application provides API endpoints to:
1. Fetch Google Form edit links by Candidate ID
2. Create, edit, and delete questions in Google Forms
3. Verify forms and report if they fail to update or respond properly

Endpoints:
    GET /get-edit-link?candidate_id=CAND-0002
    POST /create-form
    POST /add-question
    PUT /edit-question
    DELETE /delete-question
    GET /verify-form

Returns:
    JSON responses with appropriate status codes
"""

import os
import sys
import logging
from flask import Flask, request, jsonify
import pandas as pd

# Try to import dotenv, install if not available
try:
    from dotenv import load_dotenv
except ImportError:
    import subprocess
    print("Installing python-dotenv...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "python-dotenv"])
    from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('edit_link_api.log')
    ]
)
logger = logging.getLogger(__name__)

# Import Google Form Manager functions
try:
    from google_form_manager import (
        get_edit_link_by_candidate_id as gfm_get_edit_link,
        create_form,
        add_question,
        edit_question,
        delete_question,
        verify_form
    )
    logger.info("Successfully imported Google Form Manager functions")
except ImportError:
    logger.error("Failed to import Google Form Manager functions")
    # We'll fall back to the gatekeeper function for edit links

# Define the function to get edit link by candidate ID
def get_edit_link_by_candidate_id(candidate_id):
    """
    Get the edit link for a candidate by their ID.
    
    Args:
        candidate_id (str): The Candidate ID to get the edit link for
        
    Returns:
        tuple: (success, result) where success is a boolean and result is either the edit link or an error message
    """
    logger.info(f"Getting edit link for candidate ID: {candidate_id}")
    
    if not candidate_id:
        return False, "No candidate ID provided"
    
    # Get the Google Sheet ID from environment variables
    sheet_id = os.getenv('FORM_SHEET_ID')
    if not sheet_id:
        return False, "FORM_SHEET_ID environment variable is not set"
    
    try:
        # Set up Google Sheets API
        import gspread
        from google.oauth2 import service_account
        
        # Set up credentials
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
        SERVICE_ACCOUNT_FILE = 'google_key.json'
        
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        
        # Connect to the Google Sheet
        gc = gspread.authorize(creds)
        sheet = gc.open_by_key(sheet_id).sheet1
        
        # Get all records
        records = sheet.get_all_records()
        
        # Find the Candidate ID column
        candidate_id_col = None
        for record in records:
            for key in record.keys():
                if 'candidate id' in key.lower() or 'application id' in key.lower():
                    candidate_id_col = key
                    break
            if candidate_id_col:
                break
        
        if not candidate_id_col:
            return False, "No Candidate ID column found in the Google Sheet"
        
        # Find the Edit URL column
        edit_url_col = None
        for record in records:
            for key in record.keys():
                if key == "Edit URL":
                    edit_url_col = key
                    break
            if edit_url_col:
                break
        
        if not edit_url_col:
            return False, "No Edit URL column found in the Google Sheet"
        
        # Find the matching record
        for record in records:
            if record[candidate_id_col] == candidate_id:
                edit_url = record[edit_url_col]
                if edit_url:
                    return True, edit_url
                else:
                    return False, f"No edit URL found for candidate with ID {candidate_id}"
        
        return False, f"No candidate found with ID {candidate_id}"
        
    except Exception as e:
        logger.error(f"Error in get_edit_link_by_candidate_id: {e}")
        return False, f"Error retrieving edit URL: {str(e)}"

# Import the function from gatekeeper.py
try:
    from gatekeeper import get_edit_url_by_candidate_id
except ImportError:
    logger.error("Failed to import get_edit_url_by_candidate_id from gatekeeper.py")

# Create Flask app
app = Flask(__name__)

# Get API configuration from environment variables
API_SECRET_KEY = os.getenv('API_SECRET_KEY')
API_PORT = int(os.getenv('API_PORT', 5000))
API_HOST = os.getenv('API_HOST', '0.0.0.0')
GOOGLE_FORM_ID = os.getenv('GOOGLE_FORM_ID')

def check_auth(api_key):
    """
    Check if the API key is valid.
    
    Args:
        api_key: The API key to check
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not API_SECRET_KEY:
        return True
    
    return api_key == API_SECRET_KEY

@app.route('/get-edit-link', methods=['GET'])
def get_edit_link():
    """
    Endpoint to get the edit link for a candidate by their ID.
    
    Query parameters:
        candidate_id: The Candidate ID (e.g., CAND-0001)
        api_key: Optional API key for authentication
        
    Returns:
        JSON response with the edit link or an error message
    """
    # Get query parameters
    candidate_id = request.args.get('candidate_id')
    api_key = request.args.get('api_key')
    
    # Log the request
    logger.info(f"Received request for candidate_id: {candidate_id}")
    
    # Check if API key is required and valid
    if not check_auth(api_key):
        logger.warning(f"Invalid or missing API key: {api_key}")
        return jsonify({
            "error": "Unauthorized",
            "message": "Invalid or missing API key"
        }), 401
    
    # Check if candidate_id is provided
    if not candidate_id:
        logger.warning("No candidate_id provided")
        return jsonify({
            "error": "Bad Request",
            "message": "candidate_id is required"
        }), 400
    
    # Try to use the Google Form Manager function first
    try:
        if 'gfm_get_edit_link' in globals():
            success, result = gfm_get_edit_link(candidate_id)
        else:
            # Use our defined function
            success, result = get_edit_link_by_candidate_id(candidate_id)
    except Exception as e:
        logger.error(f"Error getting edit link: {e}")
        success = False
        result = f"Error: {str(e)}"
    
    if success:
        logger.info(f"Found edit link for candidate_id: {candidate_id}")
        return jsonify({
            "candidate_id": candidate_id,
            "edit_link": result
        })
    else:
        logger.warning(f"Failed to find edit link: {result}")
        return jsonify({
            "error": "Not Found",
            "message": result
        }), 404

@app.route('/create-form', methods=['POST'])
def create_form_endpoint():
    """
    Endpoint to create a new Google Form.
    
    JSON body:
        title: The title of the form
        description: (optional) The description of the form
        api_key: (optional) API key for authentication
        
    Returns:
        JSON response with the form ID or an error message
    """
    # Get JSON data
    data = request.get_json()
    if not data:
        return jsonify({
            "error": "Bad Request",
            "message": "JSON body is required"
        }), 400
    
    # Get parameters
    title = data.get('title')
    description = data.get('description', '')
    api_key = data.get('api_key')
    
    # Log the request
    logger.info(f"Received request to create form: {title}")
    
    # Check if API key is required and valid
    if not check_auth(api_key):
        logger.warning(f"Invalid or missing API key: {api_key}")
        return jsonify({
            "error": "Unauthorized",
            "message": "Invalid or missing API key"
        }), 401
    
    # Check if title is provided
    if not title:
        logger.warning("No title provided")
        return jsonify({
            "error": "Bad Request",
            "message": "title is required"
        }), 400
    
    # Check if create_form function is available
    if 'create_form' not in globals():
        logger.error("create_form function not available")
        return jsonify({
            "error": "Not Implemented",
            "message": "Form creation is not available"
        }), 501
    
    # Create the form
    try:
        success, result = create_form(title, description)
    except Exception as e:
        logger.error(f"Error creating form: {e}")
        success = False
        result = f"Error: {str(e)}"
    
    if success:
        logger.info(f"Created form with ID: {result}")
        return jsonify({
            "form_id": result,
            "title": title,
            "description": description
        })
    else:
        logger.warning(f"Failed to create form: {result}")
        return jsonify({
            "error": "Internal Server Error",
            "message": result
        }), 500

@app.route('/add-question', methods=['POST'])
def add_question_endpoint():
    """
    Endpoint to add a question to a Google Form.
    
    JSON body:
        form_id: (optional) The ID of the form (defaults to GOOGLE_FORM_ID)
        question_type: The type of question (TEXT, PARAGRAPH, MULTIPLE_CHOICE, CHECKBOX)
        title: The title of the question
        required: (optional) Whether the question is required (default: false)
        options: (optional) Options for multiple choice questions
        api_key: (optional) API key for authentication
        
    Returns:
        JSON response with the question ID or an error message
    """
    # Get JSON data
    data = request.get_json()
    if not data:
        return jsonify({
            "error": "Bad Request",
            "message": "JSON body is required"
        }), 400
    
    # Get parameters
    form_id = data.get('form_id', GOOGLE_FORM_ID)
    question_type = data.get('question_type')
    title = data.get('title')
    required = data.get('required', False)
    options = data.get('options')
    api_key = data.get('api_key')
    
    # Log the request
    logger.info(f"Received request to add question to form {form_id}: {title}")
    
    # Check if API key is required and valid
    if not check_auth(api_key):
        logger.warning(f"Invalid or missing API key: {api_key}")
        return jsonify({
            "error": "Unauthorized",
            "message": "Invalid or missing API key"
        }), 401
    
    # Check if required parameters are provided
    if not form_id:
        logger.warning("No form_id provided")
        return jsonify({
            "error": "Bad Request",
            "message": "form_id is required"
        }), 400
    
    if not question_type:
        logger.warning("No question_type provided")
        return jsonify({
            "error": "Bad Request",
            "message": "question_type is required"
        }), 400
    
    if not title:
        logger.warning("No title provided")
        return jsonify({
            "error": "Bad Request",
            "message": "title is required"
        }), 400
    
    # Check if add_question function is available
    if 'add_question' not in globals():
        logger.error("add_question function not available")
        return jsonify({
            "error": "Not Implemented",
            "message": "Question addition is not available"
        }), 501
    
    # Add the question
    try:
        success, result = add_question(form_id, question_type, title, required, options)
    except Exception as e:
        logger.error(f"Error adding question: {e}")
        success = False
        result = f"Error: {str(e)}"
    
    if success:
        logger.info(f"Added question with ID: {result}")
        return jsonify({
            "question_id": result,
            "form_id": form_id,
            "title": title,
            "question_type": question_type,
            "required": required,
            "options": options
        })
    else:
        logger.warning(f"Failed to add question: {result}")
        return jsonify({
            "error": "Internal Server Error",
            "message": result
        }), 500

@app.route('/edit-question', methods=['PUT'])
def edit_question_endpoint():
    """
    Endpoint to edit a question in a Google Form.
    
    JSON body:
        form_id: (optional) The ID of the form (defaults to GOOGLE_FORM_ID)
        question_id: The ID of the question
        title: (optional) The new title of the question
        required: (optional) Whether the question is required
        options: (optional) New options for multiple choice questions
        api_key: (optional) API key for authentication
        
    Returns:
        JSON response with success message or an error message
    """
    # Get JSON data
    data = request.get_json()
    if not data:
        return jsonify({
            "error": "Bad Request",
            "message": "JSON body is required"
        }), 400
    
    # Get parameters
    form_id = data.get('form_id', GOOGLE_FORM_ID)
    question_id = data.get('question_id')
    title = data.get('title')
    required = data.get('required')
    options = data.get('options')
    api_key = data.get('api_key')
    
    # Log the request
    logger.info(f"Received request to edit question {question_id} in form {form_id}")
    
    # Check if API key is required and valid
    if not check_auth(api_key):
        logger.warning(f"Invalid or missing API key: {api_key}")
        return jsonify({
            "error": "Unauthorized",
            "message": "Invalid or missing API key"
        }), 401
    
    # Check if required parameters are provided
    if not form_id:
        logger.warning("No form_id provided")
        return jsonify({
            "error": "Bad Request",
            "message": "form_id is required"
        }), 400
    
    if not question_id:
        logger.warning("No question_id provided")
        return jsonify({
            "error": "Bad Request",
            "message": "question_id is required"
        }), 400
    
    # Check if at least one update parameter is provided
    if not title and required is None and not options:
        logger.warning("No update parameters provided")
        return jsonify({
            "error": "Bad Request",
            "message": "At least one of title, required, or options must be provided"
        }), 400
    
    # Check if edit_question function is available
    if 'edit_question' not in globals():
        logger.error("edit_question function not available")
        return jsonify({
            "error": "Not Implemented",
            "message": "Question editing is not available"
        }), 501
    
    # Edit the question
    try:
        success, result = edit_question(form_id, question_id, title, required, options)
    except Exception as e:
        logger.error(f"Error editing question: {e}")
        success = False
        result = f"Error: {str(e)}"
    
    if success:
        logger.info(f"Edited question {question_id}: {result}")
        return jsonify({
            "success": True,
            "message": result,
            "question_id": question_id,
            "form_id": form_id
        })
    else:
        logger.warning(f"Failed to edit question: {result}")
        return jsonify({
            "error": "Internal Server Error",
            "message": result
        }), 500

@app.route('/delete-question', methods=['DELETE'])
def delete_question_endpoint():
    """
    Endpoint to delete a question from a Google Form.
    
    Query parameters:
        form_id: (optional) The ID of the form (defaults to GOOGLE_FORM_ID)
        question_id: The ID of the question
        api_key: (optional) API key for authentication
        
    Returns:
        JSON response with success message or an error message
    """
    # Get query parameters
    form_id = request.args.get('form_id', GOOGLE_FORM_ID)
    question_id = request.args.get('question_id')
    api_key = request.args.get('api_key')
    
    # Log the request
    logger.info(f"Received request to delete question {question_id} from form {form_id}")
    
    # Check if API key is required and valid
    if not check_auth(api_key):
        logger.warning(f"Invalid or missing API key: {api_key}")
        return jsonify({
            "error": "Unauthorized",
            "message": "Invalid or missing API key"
        }), 401
    
    # Check if required parameters are provided
    if not form_id:
        logger.warning("No form_id provided")
        return jsonify({
            "error": "Bad Request",
            "message": "form_id is required"
        }), 400
    
    if not question_id:
        logger.warning("No question_id provided")
        return jsonify({
            "error": "Bad Request",
            "message": "question_id is required"
        }), 400
    
    # Check if delete_question function is available
    if 'delete_question' not in globals():
        logger.error("delete_question function not available")
        return jsonify({
            "error": "Not Implemented",
            "message": "Question deletion is not available"
        }), 501
    
    # Delete the question
    try:
        success, result = delete_question(form_id, question_id)
    except Exception as e:
        logger.error(f"Error deleting question: {e}")
        success = False
        result = f"Error: {str(e)}"
    
    if success:
        logger.info(f"Deleted question {question_id}: {result}")
        return jsonify({
            "success": True,
            "message": result,
            "question_id": question_id,
            "form_id": form_id
        })
    else:
        logger.warning(f"Failed to delete question: {result}")
        return jsonify({
            "error": "Internal Server Error",
            "message": result
        }), 500

@app.route('/verify-form', methods=['GET'])
def verify_form_endpoint():
    """
    Endpoint to verify that a Google Form is accessible and working properly.
    
    Query parameters:
        form_id: (optional) The ID of the form (defaults to GOOGLE_FORM_ID)
        api_key: (optional) API key for authentication
        
    Returns:
        JSON response with verification result or an error message
    """
    # Get query parameters
    form_id = request.args.get('form_id', GOOGLE_FORM_ID)
    api_key = request.args.get('api_key')
    
    # Log the request
    logger.info(f"Received request to verify form {form_id}")
    
    # Check if API key is required and valid
    if not check_auth(api_key):
        logger.warning(f"Invalid or missing API key: {api_key}")
        return jsonify({
            "error": "Unauthorized",
            "message": "Invalid or missing API key"
        }), 401
    
    # Check if form_id is provided
    if not form_id:
        logger.warning("No form_id provided")
        return jsonify({
            "error": "Bad Request",
            "message": "form_id is required"
        }), 400
    
    # Check if verify_form function is available
    if 'verify_form' not in globals():
        logger.error("verify_form function not available")
        return jsonify({
            "error": "Not Implemented",
            "message": "Form verification is not available"
        }), 501
    
    # Verify the form
    try:
        success, result = verify_form(form_id)
    except Exception as e:
        logger.error(f"Error verifying form: {e}")
        success = False
        result = f"Error: {str(e)}"
    
    if success:
        logger.info(f"Verified form {form_id}: {result}")
        return jsonify({
            "success": True,
            "message": result,
            "form_id": form_id
        })
    else:
        logger.warning(f"Failed to verify form: {result}")
        return jsonify({
            "error": "Internal Server Error",
            "message": result
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint.
    
    Returns:
        JSON response with status
    """
    return jsonify({
        "status": "ok",
        "version": "1.0.0"
    })

if __name__ == '__main__':
    logger.info(f"Starting Edit Link API on {API_HOST}:{API_PORT}")
    app.run(host=API_HOST, port=API_PORT)