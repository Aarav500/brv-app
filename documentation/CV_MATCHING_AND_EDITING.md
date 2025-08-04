# CV Matching and Editing Implementation

## Overview

This document outlines the implementation of enhanced CV matching and editing functionality in the BRV Applicant Management System. The goal is to ensure that:

1. Receptionists can edit candidate data using Candidate ID as the unique key
2. Interviewers can view CVs by Candidate ID
3. CV view access is logged in Firestore for tracking purposes

## Changes Made

### 1. Utility Functions for Google Sheet Operations

New utility functions were added in `utils_update.py`:

- `update_google_sheet_by_candidate_id(candidate_id, updates)`: Updates a row in the Google Sheet based on Candidate ID
- `get_google_sheet_row_by_candidate_id(candidate_id)`: Retrieves a row from the Google Sheet based on Candidate ID
- `log_cv_view_in_firestore(candidate_id, interviewer_email, cv_url)`: Logs CV view access in Firestore

### 2. Enhanced CV Display Logic

The CV display logic was updated in `cv_display.py` to use Candidate ID for matching:

- Added `display_cv_from_sheet_by_candidate_id(candidate_id, interviewer_email, candidate_name)`: Displays a CV based on Candidate ID by looking it up in the Google Sheet

### 3. Receptionist View for Editing Candidate Data

A new receptionist view was added in `receptionist_edit.py`:

- `receptionist_edit_view()`: Allows the receptionist to enter a Candidate ID, view and edit the candidate's information, and update the Google Sheet
- The main `receptionist.py` file was updated to include this new view in the navigation

### 4. Interviewer View for Displaying CVs by Candidate ID

A new interviewer view was added in `interviewer_cv_view.py`:

- `interviewer_cv_view()`: Allows the interviewer to enter a Candidate ID and view the corresponding CV
- The main `interviewer.py` file was updated to include this new view in the navigation

### 5. Firestore Logging for CV View Access

CV view access is now logged in Firestore for tracking purposes:

- When an interviewer views a CV, the access is logged in the `cv_view_logs` collection in Firestore
- The log includes the Candidate ID, interviewer email, timestamp, and CV URL

## How to Use

### Receptionist: Editing Candidate Data

1. Log in as a receptionist
2. Click on "Edit Candidate" in the navigation sidebar
3. Enter the Candidate ID of the candidate you want to edit
4. Edit the candidate's information, including the 'Upload your Resume' field
5. Click "Update Candidate Information" to save the changes

### Interviewer: Viewing CVs by Candidate ID

1. Log in as an interviewer
2. Click on "View CV by ID" in the navigation sidebar
3. Enter your email (for logging purposes)
4. Enter the Candidate ID of the candidate whose CV you want to view
5. Click "View CV" to display the candidate's information and CV

## Implementation Details

### 1. Google Sheet Integration

The system now uses the Google Sheet URL specified in the requirements:

```
https://docs.google.com/spreadsheets/d/1V0Sf65ZVrebpopBfg2vwk-_PjRxgqlbytIX-L2GImAE/edit#gid=1400567486
```

The system looks for the following columns in the Google Sheet:

- `Candidate ID`: Used as the unique key for matching
- `Upload your Resume`: Contains the CV link
- Other columns like `Full Name( First-middle-last)`, `Email Address`, etc.

### 2. CV Display Logic

The CV display logic now follows these steps:

1. Fetch the row from the Google Sheet using the Candidate ID
2. Extract the 'Upload your Resume' link from the row
3. Check if it's a valid Google Drive link
4. Display the CV using the appropriate method (Google Drive iframe or fallback)
5. Log the CV view access in Firestore

### 3. Firestore Logging

CV view access is logged in Firestore with the following information:

- `candidate_id`: The Candidate ID of the CV being viewed
- `interviewer_email`: The email of the interviewer viewing the CV
- `timestamp`: The timestamp of the view
- `date`: The date of the view
- `time`: The time of the view
- `cv_url`: The URL of the CV being viewed

## Affected Files

1. `utils_update.py`: New file with utility functions for Google Sheet operations and Firestore logging
2. `cv_display.py`: Updated to use Candidate ID for matching and to integrate Firestore logging
3. `receptionist_edit.py`: New file with receptionist view for editing candidate data
4. `receptionist.py`: Updated to include the new edit view in the navigation
5. `interviewer_cv_view.py`: New file with interviewer view for displaying CVs by Candidate ID
6. `interviewer.py`: Updated to include the new CV view in the navigation

## Testing

To test the implementation:

1. Log in as a receptionist and try editing a candidate's information
2. Log in as an interviewer and try viewing a CV by Candidate ID
3. Check the Firestore database to verify that CV view access is being logged

## Notes

- The system now relies on the Candidate ID as the unique key for matching, rather than name or timestamp
- The system handles both Google Drive links and other types of links, with a fallback display for non-Google Drive links
- Error handling is implemented for various scenarios, such as missing Candidate ID, missing CV, etc.
- The system logs CV view access in Firestore for tracking purposes