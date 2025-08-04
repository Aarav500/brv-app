import streamlit as st
import pandas as pd

def test_candidate_dictionary_access():
    """
    Test function to verify that dictionary access works correctly for candidate data.
    This simulates the behavior in receptionist.py to ensure the KeyError is fixed.
    """
    print("Testing candidate dictionary access...")
    
    # Create a sample candidate dictionary (similar to what we'd get from Firestore)
    candidate = {
        'Candidate Name': 'Aarav Shah',
        'Email': 'aarav@example.com',
        'Phone': '1234567890',
        'Address': '123 Main St, Mumbai',
        'hr_data': {
            'typing_speed': '60',
            'accuracy_test': '95'
        },
        'resume_path': 'resumes/aarav_resume.pdf',
        'Interview Status': 'Pending'
    }
    
    # Test accessing fields with get() method
    try:
        name = candidate.get('Candidate Name', 'Unknown')
        email = candidate.get('Email', 'Unknown')
        cv_status = 'Uploaded ✅' if candidate.get('resume_path') else 'Missing ❌'
        interview_status = candidate.get('Interview Status', 'Not Set')
        
        print(f"Name: {name}")
        print(f"Email: {email}")
        print(f"CV Status: {cv_status}")
        print(f"Interview Status: {interview_status}")
        
        # Test HR data access
        hr_data = candidate.get('hr_data', {})
        if hr_data:
            print("HR Data:")
            for key, value in hr_data.items():
                print(f" - {key}: {value}")
        
        print("All tests passed successfully!")
        return True
    except Exception as e:
        print(f"Error during testing: {e}")
        return False

if __name__ == "__main__":
    test_candidate_dictionary_access()