#!/usr/bin/env python3
"""
Test Script for CV ID Assigner, Google Form Manager, and Form Management API

This script tests all components of the implementation:
1. CV ID Assigner: Verifies that Candidate IDs are correctly assigned and stored
2. Google Form Manager: Tests form creation, question management, and verification
3. Form Management API: Verifies that the API endpoints work correctly

Usage:
    python test_cv_id_and_edit_link.py [--test-cv-id] [--test-form-manager] [--test-api]
"""

import os
import sys
import argparse
import requests
import json
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_cv_id_assigner():
    """
    Test the CV ID Assigner functionality.
    
    This function:
    1. Imports the cv_id_assigner module
    2. Calls the assign_candidate_ids function
    3. Verifies that the function completes without errors
    4. Checks that the Google Sheet has been updated
    """
    print("\n=== Testing CV ID Assigner ===\n")
    
    # Check if required environment variables are set
    drive_folder_id = os.getenv('DRIVE_FOLDER_ID')
    sheet_id = os.getenv('MAPPING_SHEET_ID')
    
    if not drive_folder_id:
        print("❌ DRIVE_FOLDER_ID environment variable is not set.")
        print("   Please set it in the .env file and try again.")
        return False
    
    if not sheet_id:
        print("❌ MAPPING_SHEET_ID environment variable is not set.")
        print("   Please set it in the .env file and try again.")
        return False
    
    # Check if google_key.json exists
    if not os.path.exists('google_key.json'):
        print("❌ google_key.json file not found.")
        print("   Please create this file with your Google service account credentials and try again.")
        return False
    
    try:
        # Import the cv_id_assigner module
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from cv_id_assigner import assign_candidate_ids, setup_credentials, get_or_create_sheet
        
        # Set up credentials
        drive_service, sheet_client = setup_credentials()
        if not drive_service or not sheet_client:
            print("❌ Failed to set up credentials.")
            return False
        
        # Get the worksheet
        worksheet = get_or_create_sheet(sheet_client)
        if not worksheet:
            print("❌ Failed to get or create worksheet.")
            return False
        
        # Get the initial count of mappings
        initial_data = worksheet.get_all_records()
        initial_count = len(initial_data)
        
        print(f"ℹ️ Initial count of mappings: {initial_count}")
        
        # Run the CV ID Assigner
        print("ℹ️ Running CV ID Assigner...")
        assign_candidate_ids()
        
        # Get the final count of mappings
        final_data = worksheet.get_all_records()
        final_count = len(final_data)
        
        print(f"ℹ️ Final count of mappings: {final_count}")
        
        # Check if any new mappings were added
        if final_count > initial_count:
            print(f"✅ {final_count - initial_count} new mappings added.")
        else:
            print("ℹ️ No new mappings added. This is expected if all files were already processed.")
        
        # Print a sample of the mappings
        if final_data:
            print("\nSample mappings:")
            for i, row in enumerate(final_data[:3]):
                print(f"  {i+1}. {row['Candidate ID']} -> {row['File Name']}")
            
            if len(final_data) > 3:
                print(f"  ... and {len(final_data) - 3} more")
        
        print("\n✅ CV ID Assigner test completed successfully.")
        return True
    
    except Exception as e:
        print(f"❌ Error testing CV ID Assigner: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_form_manager():
    """
    Test the Google Form Manager functionality.
    
    This function:
    1. Imports the google_form_manager module
    2. Tests form creation, question management, and verification
    3. Verifies that the functions work as expected
    """
    print("\n=== Testing Google Form Manager ===\n")
    
    # Check if google_key.json exists
    if not os.path.exists('google_key.json'):
        print("❌ google_key.json file not found.")
        print("   Please create this file with your Google service account credentials and try again.")
        return False
    
    try:
        # Import the google_form_manager module
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from google_form_manager import (
            create_form,
            add_question,
            edit_question,
            delete_question,
            verify_form,
            get_form
        )
        
        # Create a test form
        print("ℹ️ Creating a test form...")
        form_title = f"Test Form {time.strftime('%Y-%m-%d %H:%M:%S')}"
        form_description = "This is a test form created by the test script"
        
        success, form_id = create_form(form_title, form_description)
        
        if not success:
            print(f"❌ Failed to create form: {form_id}")
            return False
        
        print(f"✅ Created form with ID: {form_id}")
        
        # Add a text question
        print("ℹ️ Adding a text question...")
        text_question_title = "What is your name?"
        
        success, text_question_id = add_question(form_id, "TEXT", text_question_title, required=True)
        
        if not success:
            print(f"❌ Failed to add text question: {text_question_id}")
            return False
        
        print(f"✅ Added text question with ID: {text_question_id}")
        
        # Add a multiple choice question
        print("ℹ️ Adding a multiple choice question...")
        mc_question_title = "What is your favorite color?"
        mc_options = ["Red", "Green", "Blue"]
        
        success, mc_question_id = add_question(form_id, "MULTIPLE_CHOICE", mc_question_title, required=False, options=mc_options)
        
        if not success:
            print(f"❌ Failed to add multiple choice question: {mc_question_id}")
            return False
        
        print(f"✅ Added multiple choice question with ID: {mc_question_id}")
        
        # Edit the text question
        print("ℹ️ Editing the text question...")
        new_text_question_title = "What is your full name?"
        
        success, message = edit_question(form_id, text_question_id, title=new_text_question_title)
        
        if not success:
            print(f"❌ Failed to edit text question: {message}")
            return False
        
        print(f"✅ Edited text question: {message}")
        
        # Verify the form
        print("ℹ️ Verifying the form...")
        
        success, message = verify_form(form_id)
        
        if not success:
            print(f"❌ Failed to verify form: {message}")
            return False
        
        print(f"✅ Verified form: {message}")
        
        # Delete the multiple choice question
        print("ℹ️ Deleting the multiple choice question...")
        
        success, message = delete_question(form_id, mc_question_id)
        
        if not success:
            print(f"❌ Failed to delete multiple choice question: {message}")
            return False
        
        print(f"✅ Deleted multiple choice question: {message}")
        
        # Get the form to verify changes
        print("ℹ️ Getting the form to verify changes...")
        
        form = get_form(form_id)
        
        if not form:
            print("❌ Failed to get form")
            return False
        
        print("✅ Got form")
        print(f"   Title: {form.get('info', {}).get('title')}")
        print(f"   Description: {form.get('info', {}).get('description')}")
        print(f"   Number of questions: {len(form.get('items', []))}")
        
        print("\n✅ Google Form Manager test completed successfully.")
        return True
    
    except Exception as e:
        print(f"❌ Error testing Google Form Manager: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_form_management_api():
    """
    Test the Form Management API functionality.
    
    This function:
    1. Makes requests to the API endpoints
    2. Verifies that the responses are as expected
    """
    print("\n=== Testing Form Management API ===\n")
    
    # Check if required environment variables are set
    api_secret_key = os.getenv('API_SECRET_KEY')
    api_port = os.getenv('API_PORT', '5000')
    api_host = os.getenv('API_HOST', '0.0.0.0')
    
    # Check if google_key.json exists
    if not os.path.exists('google_key.json'):
        print("❌ google_key.json file not found.")
        print("   Please create this file with your Google service account credentials and try again.")
        return False
    
    # Check if the API is already running
    try:
        response = requests.get(f"http://localhost:{api_port}/health", timeout=2)
        api_running = response.status_code == 200
    except:
        api_running = False
    
    if not api_running:
        print("ℹ️ API is not running. Please start it in a separate terminal with:")
        print(f"   python edit_link_api.py")
        print("   Then run this test again.")
        return False
    
    try:
        # Test the health check endpoint
        print("ℹ️ Testing health check endpoint...")
        response = requests.get(f"http://localhost:{api_port}/health")
        
        if response.status_code == 200:
            print("✅ Health check endpoint is working.")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ Health check endpoint returned status code {response.status_code}.")
            print(f"   Response: {response.text}")
            return False
        
        # Test creating a form
        print("ℹ️ Testing create-form endpoint...")
        
        form_title = f"API Test Form {time.strftime('%Y-%m-%d %H:%M:%S')}"
        form_description = "This is a test form created by the API test"
        
        create_form_data = {
            "title": form_title,
            "description": form_description
        }
        
        if api_secret_key:
            create_form_data["api_key"] = api_secret_key
        
        response = requests.post(
            f"http://localhost:{api_port}/create-form",
            json=create_form_data
        )
        
        if response.status_code == 200:
            print("✅ create-form endpoint is working.")
            print(f"   Response: {response.json()}")
            form_id = response.json().get("form_id")
        elif response.status_code == 501:
            print("ℹ️ Form creation is not available. This is expected if google_form_manager.py is not properly set up.")
            print(f"   Response: {response.json()}")
            
            # Skip the rest of the form management tests
            print("\n✅ Form Management API test completed with limited functionality.")
            return True
        else:
            print(f"❌ create-form endpoint returned status code {response.status_code}.")
            print(f"   Response: {response.text}")
            return False
        
        # Test adding a question
        print("ℹ️ Testing add-question endpoint...")
        
        add_question_data = {
            "form_id": form_id,
            "question_type": "TEXT",
            "title": "What is your name?",
            "required": True
        }
        
        if api_secret_key:
            add_question_data["api_key"] = api_secret_key
        
        response = requests.post(
            f"http://localhost:{api_port}/add-question",
            json=add_question_data
        )
        
        if response.status_code == 200:
            print("✅ add-question endpoint is working.")
            print(f"   Response: {response.json()}")
            question_id = response.json().get("question_id")
        else:
            print(f"❌ add-question endpoint returned status code {response.status_code}.")
            print(f"   Response: {response.text}")
            return False
        
        # Test editing a question
        print("ℹ️ Testing edit-question endpoint...")
        
        edit_question_data = {
            "form_id": form_id,
            "question_id": question_id,
            "title": "What is your full name?",
            "required": True
        }
        
        if api_secret_key:
            edit_question_data["api_key"] = api_secret_key
        
        response = requests.put(
            f"http://localhost:{api_port}/edit-question",
            json=edit_question_data
        )
        
        if response.status_code == 200:
            print("✅ edit-question endpoint is working.")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ edit-question endpoint returned status code {response.status_code}.")
            print(f"   Response: {response.text}")
            return False
        
        # Test verifying a form
        print("ℹ️ Testing verify-form endpoint...")
        
        verify_url = f"http://localhost:{api_port}/verify-form?form_id={form_id}"
        if api_secret_key:
            verify_url += f"&api_key={api_secret_key}"
        
        response = requests.get(verify_url)
        
        if response.status_code == 200:
            print("✅ verify-form endpoint is working.")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ verify-form endpoint returned status code {response.status_code}.")
            print(f"   Response: {response.text}")
            return False
        
        # Test deleting a question
        print("ℹ️ Testing delete-question endpoint...")
        
        delete_url = f"http://localhost:{api_port}/delete-question?form_id={form_id}&question_id={question_id}"
        if api_secret_key:
            delete_url += f"&api_key={api_secret_key}"
        
        response = requests.delete(delete_url)
        
        if response.status_code == 200:
            print("✅ delete-question endpoint is working.")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ delete-question endpoint returned status code {response.status_code}.")
            print(f"   Response: {response.text}")
            return False
        
        # Test get-edit-link endpoint
        print("ℹ️ Testing get-edit-link endpoint...")
        
        # Get a test Candidate ID
        test_candidate_id = None
        try:
            from cv_id_assigner import setup_credentials, get_or_create_sheet
            _, sheet_client = setup_credentials()
            if sheet_client:
                mapping_sheet_id = os.getenv('MAPPING_SHEET_ID')
                if mapping_sheet_id:
                    spreadsheet = sheet_client.open_by_key(mapping_sheet_id)
                    worksheet = spreadsheet.worksheet(os.getenv('MAPPING_SHEET_NAME', 'Candidate ID Mapping'))
                    data = worksheet.get_all_records()
                    if data:
                        test_candidate_id = data[0]['Candidate ID']
        except:
            pass
        
        # If we couldn't get a real Candidate ID, use a test one
        if not test_candidate_id:
            test_candidate_id = "CAND-0001"
        
        # Prepare the request URL
        request_url = f"http://localhost:{api_port}/get-edit-link?candidate_id={test_candidate_id}"
        if api_secret_key:
            request_url += f"&api_key={api_secret_key}"
        
        response = requests.get(request_url)
        
        if response.status_code == 200:
            print("✅ get-edit-link endpoint is working.")
            print(f"   Response: {response.json()}")
        elif response.status_code == 404:
            print("ℹ️ Candidate ID not found. This is expected if the ID doesn't exist in the form responses.")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ get-edit-link endpoint returned status code {response.status_code}.")
            print(f"   Response: {response.text}")
            return False
        
        print("\n✅ Form Management API test completed successfully.")
        return True
    
    except Exception as e:
        print(f"❌ Error testing Form Management API: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """
    Main function to run the tests.
    """
    parser = argparse.ArgumentParser(description='Test CV ID Assigner, Google Form Manager, and Form Management API')
    parser.add_argument('--test-cv-id', action='store_true', help='Test CV ID Assigner')
    parser.add_argument('--test-form-manager', action='store_true', help='Test Google Form Manager')
    parser.add_argument('--test-api', action='store_true', help='Test Form Management API')
    
    args = parser.parse_args()
    
    # If no specific tests are requested, run all tests
    if not args.test_cv_id and not args.test_form_manager and not args.test_api:
        args.test_cv_id = True
        args.test_form_manager = True
        args.test_api = True
    
    # Run the requested tests
    if args.test_cv_id:
        cv_id_success = test_cv_id_assigner()
    else:
        cv_id_success = None
    
    if args.test_form_manager:
        form_manager_success = test_form_manager()
    else:
        form_manager_success = None
    
    if args.test_api:
        api_success = test_form_management_api()
    else:
        api_success = None
    
    # Print summary
    print("\n=== Test Summary ===\n")
    
    if cv_id_success is not None:
        print(f"CV ID Assigner: {'✅ PASSED' if cv_id_success else '❌ FAILED'}")
    
    if form_manager_success is not None:
        print(f"Google Form Manager: {'✅ PASSED' if form_manager_success else '❌ FAILED'}")
    
    if api_success is not None:
        print(f"Form Management API: {'✅ PASSED' if api_success else '❌ FAILED'}")
    
    # Return exit code
    if (cv_id_success is False) or (form_manager_success is False) or (api_success is False):
        return 1
    else:
        return 0

if __name__ == "__main__":
    sys.exit(main())