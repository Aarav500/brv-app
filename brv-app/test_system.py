#!/usr/bin/env python3
"""
Test System for BRV Walk-in System

This script tests all components of the BRV Walk-in System:
1. Form generation and edit link creation
2. Candidate ID assignment and matching
3. Google Drive synchronization
4. API functionality

Usage:
    python test_system.py [--test-all] [--test-candidate-id] [--test-edit-links] [--test-drive-sync] [--test-api]
"""

import os
import sys
import argparse
import requests
import time
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_system.log')
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def test_candidate_id_assignment():
    """
    Test the Candidate ID assignment functionality.
    
    This function:
    1. Tests manual Candidate ID assignment
    2. Verifies ID uniqueness validation
    3. Checks if assigned IDs can be retrieved
    """
    logger.info("=== Testing Candidate ID Assignment ===")
    
    try:
        # Import the cv_id_assigner module
        from cv_id_assigner import (
            setup_credentials,
            get_or_create_sheet,
            is_valid_candidate_id,
            is_candidate_id_unique,
            assign_manual_candidate_id,
            list_drive_files
        )
        
        # Test ID validation
        logger.info("Testing ID validation...")
        test_cases = [
            ("CAND-0001", True),
            ("CAND-1234", True),
            ("CAND-0", False),
            ("CAND-00001", False),
            ("cand-0001", False),
            ("BRV-0001", False),
            ("", False),
            (None, False)
        ]
        
        for candidate_id, expected in test_cases:
            result = is_valid_candidate_id(candidate_id)
            if result == expected:
                logger.info(f"✅ Validation for '{candidate_id}' correct: {result}")
            else:
                logger.error(f"❌ Validation for '{candidate_id}' incorrect: got {result}, expected {expected}")
        
        # Set up credentials
        drive_service, sheet_client = setup_credentials()
        if not drive_service or not sheet_client:
            logger.error("❌ Failed to set up credentials.")
            return False
        
        # Check if required environment variables are set
        drive_folder_id = os.getenv('DRIVE_FOLDER_ID')
        if not drive_folder_id:
            logger.error("❌ DRIVE_FOLDER_ID environment variable is not set.")
            return False
        
        sheet_id = os.getenv('MAPPING_SHEET_ID')
        if not sheet_id:
            logger.error("❌ MAPPING_SHEET_ID environment variable is not set.")
            return False
        
        # Get the worksheet
        worksheet = get_or_create_sheet(sheet_client)
        if not worksheet:
            logger.error("❌ Failed to get or create worksheet.")
            return False
        
        # Get existing mappings
        existing_data = worksheet.get_all_records()
        existing_file_ids = {row['Google Drive File ID']: row['Candidate ID'] for row in existing_data}
        existing_candidate_ids = [row['Candidate ID'] for row in existing_data]
        
        logger.info(f"Found {len(existing_data)} existing mappings.")
        
        # List files in the Drive folder
        files = list_drive_files(drive_service, drive_folder_id)
        if not files:
            logger.error("❌ No files found in the specified Google Drive folder.")
            return False
        
        logger.info(f"Found {len(files)} files in the Drive folder.")
        
        # Find an unassigned file for testing
        unassigned_files = [f for f in files if f['id'] not in existing_file_ids]
        if not unassigned_files:
            logger.warning("⚠️ No unassigned files found for testing. All files already have Candidate IDs.")
            return True
        
        test_file = unassigned_files[0]
        logger.info(f"Using file '{test_file['name']}' for testing.")
        
        # Generate a test Candidate ID that doesn't exist
        test_id = "CAND-9999"
        while test_id in existing_candidate_ids:
            test_id = f"CAND-{int(test_id.split('-')[1]) + 1:04d}"
        
        logger.info(f"Using test Candidate ID: {test_id}")
        
        # Test uniqueness check
        is_unique = is_candidate_id_unique(test_id, existing_candidate_ids)
        if is_unique:
            logger.info(f"✅ Uniqueness check for '{test_id}' correct: {is_unique}")
        else:
            logger.error(f"❌ Uniqueness check for '{test_id}' incorrect: {is_unique}")
        
        # Test manual assignment
        logger.info(f"Testing manual assignment of {test_id} to {test_file['name']}...")
        success, message = assign_manual_candidate_id(test_file['id'], test_file['name'], test_id)
        
        if success:
            logger.info(f"✅ Manual assignment successful: {message}")
        else:
            logger.error(f"❌ Manual assignment failed: {message}")
            return False
        
        # Verify the assignment
        updated_data = worksheet.get_all_records()
        assigned_id = None
        for row in updated_data:
            if row['Google Drive File ID'] == test_file['id']:
                assigned_id = row['Candidate ID']
                break
        
        if assigned_id == test_id:
            logger.info(f"✅ Verification successful: {test_id} assigned to {test_file['name']}")
        else:
            logger.error(f"❌ Verification failed: Expected {test_id}, got {assigned_id}")
            return False
        
        logger.info("✅ Candidate ID assignment test completed successfully.")
        return True
    
    except Exception as e:
        logger.error(f"❌ Error testing Candidate ID assignment: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_edit_links():
    """
    Test the edit link functionality.
    
    This function:
    1. Tests retrieving edit links by Candidate ID
    2. Verifies error handling for invalid IDs
    """
    logger.info("=== Testing Edit Links ===")
    
    try:
        # Import the edit_link_api module
        from edit_link_api import get_edit_link_by_candidate_id
        
        # Test getting edit link for a valid Candidate ID
        # First, get an existing Candidate ID from the mapping sheet
        from cv_id_assigner import setup_credentials, get_or_create_sheet
        
        drive_service, sheet_client = setup_credentials()
        if not drive_service or not sheet_client:
            logger.error("❌ Failed to set up credentials.")
            return False
        
        sheet_id = os.getenv('MAPPING_SHEET_ID')
        if not sheet_id:
            logger.error("❌ MAPPING_SHEET_ID environment variable is not set.")
            return False
        
        worksheet = get_or_create_sheet(sheet_client)
        if not worksheet:
            logger.error("❌ Failed to get or create worksheet.")
            return False
        
        existing_data = worksheet.get_all_records()
        if not existing_data:
            logger.warning("⚠️ No existing mappings found for testing.")
            return True
        
        test_id = existing_data[0]['Candidate ID']
        logger.info(f"Using test Candidate ID: {test_id}")
        
        # Test getting edit link
        success, result = get_edit_link_by_candidate_id(test_id)
        
        if success:
            logger.info(f"✅ Got edit link for {test_id}: {result[:50]}...")
        else:
            logger.warning(f"⚠️ Could not get edit link for {test_id}: {result}")
            # This might be expected if the ID doesn't have a form submission
        
        # Test with invalid ID
        invalid_id = "INVALID-ID"
        success, result = get_edit_link_by_candidate_id(invalid_id)
        
        if not success:
            logger.info(f"✅ Correctly handled invalid ID: {result}")
        else:
            logger.error(f"❌ Unexpectedly got success for invalid ID: {result}")
            return False
        
        # Test with empty ID
        success, result = get_edit_link_by_candidate_id("")
        
        if not success:
            logger.info(f"✅ Correctly handled empty ID: {result}")
        else:
            logger.error(f"❌ Unexpectedly got success for empty ID: {result}")
            return False
        
        logger.info("✅ Edit links test completed successfully.")
        return True
    
    except Exception as e:
        logger.error(f"❌ Error testing edit links: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_drive_sync():
    """
    Test the Google Drive synchronization.
    
    This function:
    1. Tests retrieving CVs from Google Drive by Candidate ID
    2. Verifies the mapping between Candidate IDs and Google Drive files
    """
    logger.info("=== Testing Google Drive Synchronization ===")
    
    try:
        # Import the utils module
        from utils import get_cv_from_drive_by_candidate_id
        
        # Get an existing Candidate ID from the mapping sheet
        from cv_id_assigner import setup_credentials, get_or_create_sheet
        
        drive_service, sheet_client = setup_credentials()
        if not drive_service or not sheet_client:
            logger.error("❌ Failed to set up credentials.")
            return False
        
        sheet_id = os.getenv('MAPPING_SHEET_ID')
        if not sheet_id:
            logger.error("❌ MAPPING_SHEET_ID environment variable is not set.")
            return False
        
        worksheet = get_or_create_sheet(sheet_client)
        if not worksheet:
            logger.error("❌ Failed to get or create worksheet.")
            return False
        
        existing_data = worksheet.get_all_records()
        if not existing_data:
            logger.warning("⚠️ No existing mappings found for testing.")
            return True
        
        test_id = existing_data[0]['Candidate ID']
        logger.info(f"Using test Candidate ID: {test_id}")
        
        # Test getting CV from Drive
        cv_file = get_cv_from_drive_by_candidate_id(test_id)
        
        if cv_file:
            logger.info(f"✅ Got CV for {test_id}: {cv_file['name']}")
        else:
            logger.warning(f"⚠️ Could not get CV for {test_id}")
            # This might be expected if the ID doesn't have a CV in Drive
        
        # Test with invalid ID
        invalid_id = "INVALID-ID"
        cv_file = get_cv_from_drive_by_candidate_id(invalid_id)
        
        if not cv_file:
            logger.info(f"✅ Correctly handled invalid ID")
        else:
            logger.error(f"❌ Unexpectedly got CV for invalid ID: {cv_file['name']}")
            return False
        
        # Test with empty ID
        cv_file = get_cv_from_drive_by_candidate_id("")
        
        if not cv_file:
            logger.info(f"✅ Correctly handled empty ID")
        else:
            logger.error(f"❌ Unexpectedly got CV for empty ID: {cv_file['name']}")
            return False
        
        logger.info("✅ Google Drive synchronization test completed successfully.")
        return True
    
    except Exception as e:
        logger.error(f"❌ Error testing Google Drive synchronization: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_api():
    """
    Test the API functionality.
    
    This function:
    1. Tests the edit link API endpoint
    2. Verifies error handling for invalid requests
    """
    logger.info("=== Testing API Functionality ===")
    
    try:
        # Check if the API is running
        api_port = os.getenv('API_PORT', '5000')
        api_host = os.getenv('API_HOST', '0.0.0.0')
        api_url = f"http://{api_host}:{api_port}"
        
        try:
            response = requests.get(f"{api_url}/health", timeout=2)
            api_running = response.status_code == 200
        except:
            api_running = False
        
        if not api_running:
            logger.warning("⚠️ API is not running. Please start it in a separate terminal with:")
            logger.warning(f"   python edit_link_api.py")
            logger.warning("   Then run this test again.")
            return True
        
        # Get an existing Candidate ID from the mapping sheet
        from cv_id_assigner import setup_credentials, get_or_create_sheet
        
        drive_service, sheet_client = setup_credentials()
        if not drive_service or not sheet_client:
            logger.error("❌ Failed to set up credentials.")
            return False
        
        sheet_id = os.getenv('MAPPING_SHEET_ID')
        if not sheet_id:
            logger.error("❌ MAPPING_SHEET_ID environment variable is not set.")
            return False
        
        worksheet = get_or_create_sheet(sheet_client)
        if not worksheet:
            logger.error("❌ Failed to get or create worksheet.")
            return False
        
        existing_data = worksheet.get_all_records()
        if not existing_data:
            logger.warning("⚠️ No existing mappings found for testing.")
            return True
        
        test_id = existing_data[0]['Candidate ID']
        logger.info(f"Using test Candidate ID: {test_id}")
        
        # Test the get-edit-link endpoint
        api_key = os.getenv('API_SECRET_KEY')
        url = f"{api_url}/get-edit-link?candidate_id={test_id}"
        if api_key:
            url += f"&api_key={api_key}"
        
        response = requests.get(url)
        
        if response.status_code == 200:
            logger.info(f"✅ Got edit link for {test_id} from API")
            logger.info(f"   Response: {response.json()}")
        elif response.status_code == 404:
            logger.warning(f"⚠️ Could not get edit link for {test_id} from API: {response.json()}")
            # This might be expected if the ID doesn't have a form submission
        else:
            logger.error(f"❌ Unexpected status code {response.status_code} from API")
            logger.error(f"   Response: {response.text}")
            return False
        
        # Test with invalid ID
        invalid_id = "INVALID-ID"
        url = f"{api_url}/get-edit-link?candidate_id={invalid_id}"
        if api_key:
            url += f"&api_key={api_key}"
        
        response = requests.get(url)
        
        if response.status_code == 404:
            logger.info(f"✅ Correctly handled invalid ID from API")
            logger.info(f"   Response: {response.json()}")
        else:
            logger.error(f"❌ Unexpected status code {response.status_code} from API for invalid ID")
            logger.error(f"   Response: {response.text}")
            return False
        
        # Test with missing ID
        url = f"{api_url}/get-edit-link"
        if api_key:
            url += f"?api_key={api_key}"
        
        response = requests.get(url)
        
        if response.status_code == 400:
            logger.info(f"✅ Correctly handled missing ID from API")
            logger.info(f"   Response: {response.json()}")
        else:
            logger.error(f"❌ Unexpected status code {response.status_code} from API for missing ID")
            logger.error(f"   Response: {response.text}")
            return False
        
        # Test with invalid API key (if API key is required)
        if api_key:
            url = f"{api_url}/get-edit-link?candidate_id={test_id}&api_key=invalid_key"
            
            response = requests.get(url)
            
            if response.status_code == 401:
                logger.info(f"✅ Correctly handled invalid API key from API")
                logger.info(f"   Response: {response.json()}")
            else:
                logger.error(f"❌ Unexpected status code {response.status_code} from API for invalid API key")
                logger.error(f"   Response: {response.text}")
                return False
        
        logger.info("✅ API functionality test completed successfully.")
        return True
    
    except Exception as e:
        logger.error(f"❌ Error testing API functionality: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """
    Main function to run the tests.
    """
    parser = argparse.ArgumentParser(description='Test BRV Walk-in System')
    parser.add_argument('--test-all', action='store_true', help='Run all tests')
    parser.add_argument('--test-candidate-id', action='store_true', help='Test Candidate ID assignment')
    parser.add_argument('--test-edit-links', action='store_true', help='Test edit links')
    parser.add_argument('--test-drive-sync', action='store_true', help='Test Google Drive synchronization')
    parser.add_argument('--test-api', action='store_true', help='Test API functionality')
    
    args = parser.parse_args()
    
    # If no specific tests are requested, run all tests
    if not args.test_candidate_id and not args.test_edit_links and not args.test_drive_sync and not args.test_api:
        args.test_all = True
    
    # Run the requested tests
    if args.test_all or args.test_candidate_id:
        candidate_id_success = test_candidate_id_assignment()
    else:
        candidate_id_success = None
    
    if args.test_all or args.test_edit_links:
        edit_links_success = test_edit_links()
    else:
        edit_links_success = None
    
    if args.test_all or args.test_drive_sync:
        drive_sync_success = test_drive_sync()
    else:
        drive_sync_success = None
    
    if args.test_all or args.test_api:
        api_success = test_api()
    else:
        api_success = None
    
    # Print summary
    logger.info("\n=== Test Summary ===\n")
    
    if candidate_id_success is not None:
        logger.info(f"Candidate ID Assignment: {'✅ PASSED' if candidate_id_success else '❌ FAILED'}")
    
    if edit_links_success is not None:
        logger.info(f"Edit Links: {'✅ PASSED' if edit_links_success else '❌ FAILED'}")
    
    if drive_sync_success is not None:
        logger.info(f"Google Drive Synchronization: {'✅ PASSED' if drive_sync_success else '❌ FAILED'}")
    
    if api_success is not None:
        logger.info(f"API Functionality: {'✅ PASSED' if api_success else '❌ FAILED'}")
    
    # Return exit code
    if (candidate_id_success is False) or (edit_links_success is False) or (drive_sync_success is False) or (api_success is False):
        return 1
    else:
        return 0

if __name__ == "__main__":
    sys.exit(main())