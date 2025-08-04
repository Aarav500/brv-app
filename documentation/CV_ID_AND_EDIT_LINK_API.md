# Candidate ID Assignment and Google Form Management API

This document describes three new components added to the BRV Applicant Management System:

1. **CV ID Assigner**: A Python script that assigns unique Candidate IDs to CV files in Google Drive and stores the mapping in a Google Sheet.
2. **Edit Link API**: A Flask application that provides an API endpoint to fetch Google Form edit links by Candidate ID.
3. **Google Form Manager**: A module that allows programmatically creating, editing, and verifying Google Forms.

## Prerequisites

- Python 3.7 or higher
- Google service account credentials (google_key.json)
- Google Drive folder containing CV files
- Google Sheet for storing Candidate ID mappings
- Google Form with responses and edit links

## Installation

1. Install the required dependencies:

```bash
pip install -r requirements.txt
```

2. Create a `.env` file based on the `.env.template` file:

```bash
cp .env.template .env
```

3. Edit the `.env` file and fill in the required values:

```
# Google Drive folder ID containing CV files
DRIVE_FOLDER_ID=your_drive_folder_id_here

# Google Sheet ID for storing Candidate ID mappings
MAPPING_SHEET_ID=your_sheet_id_here

# Google Form ID for the application form
GOOGLE_FORM_ID=your_form_id_here

# Google Form Response Sheet ID (for edit link API)
FORM_SHEET_ID=your_form_response_sheet_id_here

# API Configuration
API_SECRET_KEY=your_secret_key_here
```

## CV ID Assigner

The CV ID Assigner is a Python script that:

1. Scans a Google Drive folder for CV files
2. Assigns unique Candidate IDs in the format CAND-XXXX
3. Stores the mapping between Candidate IDs, file names, and Google Drive file IDs in a Google Sheet
4. Can be rerun without duplicating IDs for already-processed files

### Usage

Run the script:

```bash
python cv_id_assigner.py
```

### Output

The script will create or update a Google Sheet with the following columns:

| Candidate ID | File Name | Google Drive File ID |
|--------------|-----------|----------------------|
| CAND-0001    | resume1.pdf | 1a2b3c4d5e6f7g8h9i |
| CAND-0002    | resume2.pdf | 2b3c4d5e6f7g8h9i0j |

## Google Form Manager

The Google Form Manager is a Python module that:

1. Allows programmatically creating new Google Forms
2. Supports adding, editing, and deleting questions in forms
3. Provides form verification capabilities
4. Retrieves edit links for form responses

### Usage as a Module

```python
from google_form_manager import create_form, add_question, edit_question, delete_question, verify_form

# Create a new form
success, form_id = create_form("Application Form", "Please fill out this application form")

# Add a question
success, question_id = add_question(form_id, "TEXT", "What is your name?", required=True)

# Edit a question
success, message = edit_question(form_id, question_id, title="What is your full name?", required=True)

# Delete a question
success, message = delete_question(form_id, question_id)

# Verify a form
success, message = verify_form(form_id)
```

### Usage as a Command-Line Tool

```bash
# Verify a form
python google_form_manager.py verify

# Get an edit link for a candidate
python google_form_manager.py get-edit-link CAND-0001

# Create a new form
python google_form_manager.py create-form "Application Form" "Please fill out this application form"

# Add a question
python google_form_manager.py add-question your_form_id TEXT "What is your name?" true

# Edit a question
python google_form_manager.py edit-question your_form_id your_question_id "What is your full name?" true

# Delete a question
python google_form_manager.py delete-question your_form_id your_question_id
```

## Google Form Management API

The Google Form Management API is a Flask application that:

1. Provides API endpoints to fetch Google Form edit links by Candidate ID
2. Allows creating, editing, and deleting questions in Google Forms
3. Supports form verification
4. Includes proper error handling (404 for not found, 401 for unauthorized)

### Usage

Start the API server:

```bash
python edit_link_api.py
```

The server will start on the host and port specified in the `.env` file (default: 0.0.0.0:5000).

### Endpoints

#### Get Edit Link

```
GET /get-edit-link?candidate_id=CAND-0001&api_key=your_secret_key_here
```

Parameters:
- `candidate_id`: The Candidate ID (e.g., CAND-0001)
- `api_key`: Optional API key for authentication (if API_SECRET_KEY is set in .env)

Response (success):

```json
{
  "candidate_id": "CAND-0001",
  "edit_link": "https://docs.google.com/forms/d/e/your_form_id/viewform?edit2=2_ABaOnueABCD1234"
}
```

Response (error):

```json
{
  "error": "Not Found",
  "message": "No candidate found with ID CAND-9999"
}
```

#### Create Form

```
POST /create-form
Content-Type: application/json

{
  "title": "Application Form",
  "description": "Please fill out this application form",
  "api_key": "your_secret_key_here"
}
```

Response (success):

```json
{
  "form_id": "1a2b3c4d5e6f7g8h9i",
  "title": "Application Form",
  "description": "Please fill out this application form"
}
```

#### Add Question

```
POST /add-question
Content-Type: application/json

{
  "form_id": "1a2b3c4d5e6f7g8h9i",
  "question_type": "TEXT",
  "title": "What is your name?",
  "required": true,
  "api_key": "your_secret_key_here"
}
```

Response (success):

```json
{
  "question_id": "1a2b3c4d",
  "form_id": "1a2b3c4d5e6f7g8h9i",
  "title": "What is your name?",
  "question_type": "TEXT",
  "required": true,
  "options": null
}
```

For multiple choice questions:

```json
{
  "form_id": "1a2b3c4d5e6f7g8h9i",
  "question_type": "MULTIPLE_CHOICE",
  "title": "What is your favorite color?",
  "required": true,
  "options": ["Red", "Green", "Blue"],
  "api_key": "your_secret_key_here"
}
```

#### Edit Question

```
PUT /edit-question
Content-Type: application/json

{
  "form_id": "1a2b3c4d5e6f7g8h9i",
  "question_id": "1a2b3c4d",
  "title": "What is your full name?",
  "required": true,
  "api_key": "your_secret_key_here"
}
```

Response (success):

```json
{
  "success": true,
  "message": "Question 1a2b3c4d updated successfully",
  "question_id": "1a2b3c4d",
  "form_id": "1a2b3c4d5e6f7g8h9i"
}
```

#### Delete Question

```
DELETE /delete-question?form_id=1a2b3c4d5e6f7g8h9i&question_id=1a2b3c4d&api_key=your_secret_key_here
```

Response (success):

```json
{
  "success": true,
  "message": "Question 1a2b3c4d deleted successfully",
  "question_id": "1a2b3c4d",
  "form_id": "1a2b3c4d5e6f7g8h9i"
}
```

#### Verify Form

```
GET /verify-form?form_id=1a2b3c4d5e6f7g8h9i&api_key=your_secret_key_here
```

Response (success):

```json
{
  "success": true,
  "message": "Form 1a2b3c4d5e6f7g8h9i is accessible and working properly",
  "form_id": "1a2b3c4d5e6f7g8h9i"
}
```

#### Health Check

```
GET /health
```

Response:

```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

## Integration with Google Form

For the Edit Link API to work, your Google Form must have edit links available in the response sheet. You can add edit links to your Google Form responses by:

1. Opening the Google Form in the editor
2. Going to the "Responses" tab
3. Clicking on the Google Sheets icon to link a Google Sheet
4. Adding a Google Apps Script to the linked sheet that adds an "Edit URL" column

Example Google Apps Script:

```javascript
function onFormSubmit(e) {
  var sheet = SpreadsheetApp.getActiveSheet();
  var headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  var editUrlColIndex = headers.indexOf("Edit URL") + 1;
  
  if (editUrlColIndex == 0) {
    // Add "Edit URL" header if it doesn't exist
    sheet.getRange(1, sheet.getLastColumn() + 1).setValue("Edit URL");
    editUrlColIndex = sheet.getLastColumn();
  }
  
  // Get the edit URL from the form response
  var formResponse = e.response;
  var editUrl = formResponse.getEditResponseUrl();
  
  // Add the edit URL to the sheet
  sheet.getRange(sheet.getLastRow(), editUrlColIndex).setValue(editUrl);
}

function installTrigger() {
  var form = FormApp.openById("your_form_id_here");
  ScriptApp.newTrigger("onFormSubmit")
    .forForm(form)
    .onFormSubmit()
    .create();
}
```

## Troubleshooting

### CV ID Assigner

- **Issue**: Script fails with "Error setting up credentials"
  - **Solution**: Ensure that google_key.json is present and has the correct permissions

- **Issue**: Script fails with "DRIVE_FOLDER_ID environment variable is not set"
  - **Solution**: Set the DRIVE_FOLDER_ID in the .env file

### Google Form Manager

- **Issue**: "Error setting up credentials" when using form management functions
  - **Solution**: Ensure that google_key.json is present and has the correct permissions for Forms API

- **Issue**: "No form ID provided or found in environment variables"
  - **Solution**: Set the GOOGLE_FORM_ID in the .env file or provide it as a parameter

### Google Form Management API

- **Issue**: API returns "No Edit URL column found in the Google Sheet"
  - **Solution**: Ensure that the Google Form response sheet has an "Edit URL" column

- **Issue**: API returns "No candidate found with ID CAND-XXXX"
  - **Solution**: Ensure that the Candidate ID exists in the Google Form response sheet

- **Issue**: API returns "Form creation is not available"
  - **Solution**: Ensure that the google_form_manager.py file is in the same directory as edit_link_api.py

## Security Considerations

- The API uses an API key for authentication. Ensure that this key is kept secure.
- The API should be deployed behind HTTPS in production.
- Consider implementing rate limiting to prevent abuse.
- The Google service account should have the minimum necessary permissions.