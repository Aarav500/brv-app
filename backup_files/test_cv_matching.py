#!/usr/bin/env python3
"""
Test Script for CV Time-Based Matching

This script tests the time-based matching functionality for CV uploads:
1. Tests the matching algorithm with various scenarios
2. Tests CV renaming functionality
3. Tests edge cases like similar names and close timestamps

Usage:
    python test_cv_matching.py
"""

import os
import sys
import pandas as pd
import datetime
from dateutil import parser
import unittest
from unittest.mock import patch, MagicMock

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the functions to test
from utils import match_cvs_with_form_submissions
from cv_id_assigner import rename_file_in_drive, assign_manual_candidate_id

class TestCVMatching(unittest.TestCase):
    """Test cases for CV time-based matching functionality."""

    def setUp(self):
        """Set up test data."""
        # Create sample form data
        self.form_data = pd.DataFrame({
            'Timestamp': [
                '2025-07-19 10:00:00',
                '2025-07-19 11:30:00',
                '2025-07-19 14:15:00',
                '2025-07-19 16:45:00'
            ],
            'Full Name': [
                'John Smith',
                'Jane Doe',
                'Alex Johnson',
                'Maria Garcia'
            ],
            'Email Address': [
                'john.smith@example.com',
                'jane.doe@example.com',
                'alex.johnson@example.com',
                'maria.garcia@example.com'
            ]
        })
        
        # Create sample CV files
        self.cv_files = [
            {
                'id': 'file1',
                'name': 'John_Smith_Resume.pdf',
                'mimeType': 'application/pdf',
                'createdTime': '2025-07-19T10:05:00.000Z',
                'modifiedTime': '2025-07-19T10:05:00.000Z',
                'webViewLink': 'https://drive.google.com/file/d/file1/view'
            },
            {
                'id': 'file2',
                'name': 'Jane_Doe_CV.pdf',
                'mimeType': 'application/pdf',
                'createdTime': '2025-07-19T11:40:00.000Z',
                'modifiedTime': '2025-07-19T11:40:00.000Z',
                'webViewLink': 'https://drive.google.com/file/d/file2/view'
            },
            {
                'id': 'file3',
                'name': 'Resume_Alex_J.pdf',
                'mimeType': 'application/pdf',
                'createdTime': '2025-07-19T14:30:00.000Z',
                'modifiedTime': '2025-07-19T14:30:00.000Z',
                'webViewLink': 'https://drive.google.com/file/d/file3/view'
            },
            {
                'id': 'file4',
                'name': 'maria.garcia@example.com_CV.pdf',
                'mimeType': 'application/pdf',
                'createdTime': '2025-07-19T17:00:00.000Z',
                'modifiedTime': '2025-07-19T17:00:00.000Z',
                'webViewLink': 'https://drive.google.com/file/d/file4/view'
            },
            {
                'id': 'file5',
                'name': 'Another_Resume.pdf',
                'mimeType': 'application/pdf',
                'createdTime': '2025-07-19T12:00:00.000Z',
                'modifiedTime': '2025-07-19T12:00:00.000Z',
                'webViewLink': 'https://drive.google.com/file/d/file5/view'
            }
        ]

    def test_basic_matching(self):
        """Test basic matching functionality."""
        matches = match_cvs_with_form_submissions(self.form_data, self.cv_files)
        
        # Check that we have matches
        self.assertTrue(len(matches) > 0, "Should have found matches")
        
        # Check that John Smith's form submission matches his CV
        john_match = next((m for m in matches if m['form_data']['Full Name'] == 'John Smith'), None)
        self.assertIsNotNone(john_match, "Should have found a match for John Smith")
        
        if john_match:
            # Check that the top match is the correct file
            top_match = john_match['potential_matches'][0]['cv_file']
            self.assertEqual(top_match['id'], 'file1', "Top match for John Smith should be file1")
            
            # Check confidence score
            confidence = john_match['potential_matches'][0]['confidence']
            self.assertGreaterEqual(confidence, 0.7, "Confidence score should be high for exact name match with close timestamp")

    def test_email_matching(self):
        """Test matching based on email in filename."""
        matches = match_cvs_with_form_submissions(self.form_data, self.cv_files)
        
        # Check that Maria Garcia's form submission matches her CV (which has email in filename)
        maria_match = next((m for m in matches if m['form_data']['Full Name'] == 'Maria Garcia'), None)
        self.assertIsNotNone(maria_match, "Should have found a match for Maria Garcia")
        
        if maria_match:
            # Check that the top match is the correct file
            top_match = maria_match['potential_matches'][0]['cv_file']
            self.assertEqual(top_match['id'], 'file4', "Top match for Maria Garcia should be file4")
            
            # Check that email match is detected
            self.assertTrue(maria_match['potential_matches'][0]['email_match'], "Email match should be detected")

    def test_partial_name_matching(self):
        """Test matching based on partial name."""
        matches = match_cvs_with_form_submissions(self.form_data, self.cv_files)
        
        # Check that Alex Johnson's form submission matches his CV (which has partial name)
        alex_match = next((m for m in matches if m['form_data']['Full Name'] == 'Alex Johnson'), None)
        self.assertIsNotNone(alex_match, "Should have found a match for Alex Johnson")
        
        if alex_match:
            # Check that the correct file is in the potential matches
            alex_file = next((m for m in alex_match['potential_matches'] if m['cv_file']['id'] == 'file3'), None)
            self.assertIsNotNone(alex_file, "file3 should be in potential matches for Alex Johnson")

    def test_time_difference_scoring(self):
        """Test that time difference affects confidence scores."""
        # Create a new CV file with same name but different time
        late_cv = {
            'id': 'file6',
            'name': 'John_Smith_Resume.pdf',
            'mimeType': 'application/pdf',
            'createdTime': '2025-07-19T15:05:00.000Z',  # 5 hours after form submission
            'modifiedTime': '2025-07-19T15:05:00.000Z',
            'webViewLink': 'https://drive.google.com/file/d/file6/view'
        }
        
        # Add to CV files
        test_cv_files = self.cv_files + [late_cv]
        
        matches = match_cvs_with_form_submissions(self.form_data, test_cv_files)
        
        # Find John Smith's matches
        john_match = next((m for m in matches if m['form_data']['Full Name'] == 'John Smith'), None)
        self.assertIsNotNone(john_match, "Should have found a match for John Smith")
        
        if john_match and len(john_match['potential_matches']) >= 2:
            # Get the two John Smith files
            john_files = [m for m in john_match['potential_matches'] if 'John_Smith' in m['cv_file']['name']]
            self.assertEqual(len(john_files), 2, "Should have found two files for John Smith")
            
            # Sort by confidence
            john_files.sort(key=lambda x: x['confidence'], reverse=True)
            
            # Check that the file with closer timestamp has higher confidence
            self.assertEqual(john_files[0]['cv_file']['id'], 'file1', "file1 should have higher confidence")
            self.assertGreater(john_files[0]['confidence'], john_files[1]['confidence'], 
                              "File with closer timestamp should have higher confidence")

    @patch('cv_id_assigner.setup_credentials')
    def test_rename_file(self, mock_setup_credentials):
        """Test file renaming functionality."""
        # Mock the drive service
        mock_drive_service = MagicMock()
        mock_sheet_client = MagicMock()
        mock_setup_credentials.return_value = (mock_drive_service, mock_sheet_client)
        
        # Mock the file update response
        mock_file = {
            'id': 'file1',
            'name': 'BRV-CID-CAND-0001.pdf',
            'mimeType': 'application/pdf',
            'webViewLink': 'https://drive.google.com/file/d/file1/view'
        }
        mock_drive_service.files().update().execute.return_value = mock_file
        
        # Call the rename function
        success, message, updated_file = rename_file_in_drive(
            mock_drive_service, 'file1', 'BRV-CID-CAND-0001.pdf'
        )
        
        # Check results
        self.assertTrue(success, "Rename should succeed")
        self.assertEqual(updated_file['name'], 'BRV-CID-CAND-0001.pdf', "File should be renamed")
        
        # Verify the API was called correctly
        mock_drive_service.files().update.assert_called_with(
            fileId='file1',
            body={'name': 'BRV-CID-CAND-0001.pdf'},
            fields='id, name, mimeType, webViewLink'
        )

    @patch('cv_id_assigner.setup_credentials')
    @patch('cv_id_assigner.get_or_create_sheet')
    def test_assign_candidate_id(self, mock_get_sheet, mock_setup_credentials):
        """Test assigning a Candidate ID with renaming."""
        # Mock the drive service and sheet client
        mock_drive_service = MagicMock()
        mock_sheet_client = MagicMock()
        mock_setup_credentials.return_value = (mock_drive_service, mock_sheet_client)
        
        # Mock the worksheet
        mock_worksheet = MagicMock()
        mock_get_sheet.return_value = mock_worksheet
        mock_worksheet.get_all_records.return_value = []
        
        # Mock the file update response
        mock_file = {
            'id': 'file1',
            'name': 'BRV-CID-CAND-0001.pdf',
            'mimeType': 'application/pdf',
            'webViewLink': 'https://drive.google.com/file/d/file1/view'
        }
        mock_drive_service.files().update().execute.return_value = mock_file
        
        # Mock environment variables
        with patch.dict(os.environ, {'MAPPING_SHEET_ID': 'sheet1'}):
            # Call the assign function
            success, message = assign_manual_candidate_id(
                'file1', 'John_Smith_Resume.pdf', 'CAND-0001', rename_file=True
            )
            
            # Check results
            self.assertTrue(success, "Assignment should succeed")
            self.assertIn("Successfully assigned", message)
            
            # Verify the rename API was called
            mock_drive_service.files().update.assert_called()
            
            # Verify the worksheet was updated
            mock_worksheet.append_row.assert_called_with(['CAND-0001', 'BRV-CID-CAND-0001.pdf', 'file1'])

def main():
    """Run the tests."""
    unittest.main()

if __name__ == "__main__":
    main()