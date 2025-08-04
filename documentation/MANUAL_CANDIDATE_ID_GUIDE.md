# BRV Walk-in System: Manual Candidate ID Assignment Guide

## Overview

The BRV Walk-in System has been updated to support manual Candidate ID assignment for walk-in candidates. This guide explains the new workflow and features.

## Key Changes

1. **Manual Candidate ID Assignment**: Receptionists can now manually assign Candidate IDs to CV files in Google Drive.
2. **Candidate ID as Primary Key**: The Candidate ID is used as the primary key to link all candidate data across systems.
3. **Removal of Gatekeeper**: The gatekeeper functionality has been removed, simplifying the system.
4. **Streamlit Receptionist Panel**: The receptionist panel has been updated to support manual ID assignment and CV display.

## Workflow

### 1. Manual Candidate ID Assignment

1. Open the Receptionist Panel by selecting "Candidate ID Panel" from the navigation menu.
2. Click on the "Manual Candidate ID Assignment" expander to open the assignment interface.
3. Select a CV file from the dropdown list of unassigned files in Google Drive.
4. Enter a Candidate ID in the format CAND-XXXX (e.g., CAND-0001).
5. Click "Assign Candidate ID" to assign the ID to the selected file.
6. The system will validate the ID format and uniqueness before assigning it.

### 2. Viewing Candidate Information

1. Use the "Filter by Candidate ID" or "Filter by Name" fields to find specific candidates.
2. Click on a candidate's expander to view their details, including:
   - Email and phone number
   - Candidate ID
   - CV status (available or not)
   - Edit link for their form
   - Remarks section for notes

### 3. Editing Form Responses

1. Click the "Edit Form" button in a candidate's details to open their form for editing.
2. The system will retrieve the edit link based on the Candidate ID.

## Technical Details

### Candidate ID Format

- All Candidate IDs must follow the format CAND-XXXX (e.g., CAND-0001, CAND-0002).
- IDs are manually assigned by the receptionist, not auto-generated.
- The system ensures that each ID is unique.

### CV Storage and Retrieval

- CVs are uploaded to Google Drive and manually tagged with Candidate IDs.
- The system maintains a mapping between Candidate IDs and Google Drive file IDs in a Google Sheet.
- The CV status is displayed in the receptionist panel based on this mapping.

### Form Edit Links

- Form edit links are retrieved from a Google Sheet based on the Candidate ID.
- The system uses a direct API call to retrieve the edit link, without going through the gatekeeper.

## Testing

A comprehensive testing module (`test_system.py`) is available to verify the functionality of the system:

```bash
# Run all tests
python test_system.py

# Run specific tests
python test_system.py --test-candidate-id
python test_system.py --test-edit-links
python test_system.py --test-drive-sync
python test_system.py --test-api
```

## Troubleshooting

### Common Issues

1. **Invalid Candidate ID Format**: Ensure that the Candidate ID follows the format CAND-XXXX.
2. **Duplicate Candidate ID**: Each Candidate ID must be unique. The system will prevent assigning the same ID twice.
3. **CV Not Found**: If a CV is not found for a Candidate ID, check that the file exists in Google Drive and is correctly mapped in the Google Sheet.
4. **Edit Link Not Available**: If an edit link is not available, check that the candidate has submitted a form and that the form response sheet contains the edit link.

### Environment Variables

The system requires the following environment variables to be set in a `.env` file:

```
# Google Drive folder ID containing CV files
DRIVE_FOLDER_ID=your_drive_folder_id_here

# Google Sheet ID for storing Candidate ID mappings
MAPPING_SHEET_ID=your_sheet_id_here

# Google Form Response Sheet ID (for edit link API)
FORM_SHEET_ID=your_form_response_sheet_id_here

# API Configuration
API_PORT=5000
API_HOST=0.0.0.0
API_SECRET_KEY=your_secret_key_here
```

## Conclusion

The updated BRV Walk-in System provides a streamlined workflow for managing walk-in candidates, with manual Candidate ID assignment as the primary method of linking candidate data across systems. The removal of the gatekeeper functionality simplifies the system and makes it more user-friendly for receptionists.