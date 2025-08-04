# Testing Instructions for Controlled Editing Features

This document provides instructions for testing the newly implemented features:

1. **Matching CVs with Form Entries via Candidate ID**
2. **Gatekeeper Form Logic (Receptionist Controlled Editing)**

## Prerequisites

Before testing, ensure you have:

1. A running instance of the BRV Applicant Management System
2. Access to the Google Sheet linked to the form
3. Some test CV files in the `data/resumes` directory
4. Receptionist login credentials

## Test Cases for Matching CVs with Form Entries

### Test Case 1: CV Matching with Valid Candidate ID

**Steps:**
1. Create a test CV file named `CAND-001_CV.pdf` and place it in the `data/resumes` directory
2. Log in as a receptionist
3. Navigate to the Gatekeeper Form
4. Enter Candidate ID: `CAND-001`
5. Enter Passcode: `BRV123`
6. Click "Verify and Get Edit Link"

**Expected Result:**
- The system should display "Matching CV Found" section
- The CV file name should be displayed
- A download button for the CV should be available

### Test Case 2: CV Matching with Invalid Candidate ID

**Steps:**
1. Log in as a receptionist
2. Navigate to the Gatekeeper Form
3. Enter Candidate ID: `INVALID-ID`
4. Enter Passcode: `BRV123`
5. Click "Verify and Get Edit Link"

**Expected Result:**
- The system should display an error message
- No CV should be found

## Test Cases for Gatekeeper Form Logic

### Test Case 3: Valid Candidate ID and Passcode

**Steps:**
1. Ensure there's a form response in the Google Sheet with a Candidate ID (e.g., `CAND-001`)
2. Log in as a receptionist
3. Navigate to the Gatekeeper Form
4. Enter Candidate ID: `CAND-001`
5. Enter Passcode: `BRV123`
6. Click "Verify and Get Edit Link"

**Expected Result:**
- The system should display "Access granted for Candidate ID: CAND-001"
- The edit link should be displayed
- Option to send the edit link via email should be available

### Test Case 4: Valid Candidate ID but Invalid Passcode

**Steps:**
1. Log in as a receptionist
2. Navigate to the Gatekeeper Form
3. Enter Candidate ID: `CAND-001`
4. Enter Passcode: `WRONG-PASS`
5. Click "Verify and Get Edit Link"

**Expected Result:**
- The system should display "Invalid passcode. Please try again."
- No edit link should be displayed

### Test Case 5: Invalid Candidate ID with Valid Passcode

**Steps:**
1. Log in as a receptionist
2. Navigate to the Gatekeeper Form
3. Enter Candidate ID: `INVALID-ID`
4. Enter Passcode: `BRV123`
5. Click "Verify and Get Edit Link"

**Expected Result:**
- The system should display "No candidate found with ID INVALID-ID"
- No edit link should be displayed

### Test Case 6: Sending Edit Link via Email

**Steps:**
1. Complete Test Case 3 to get a valid edit link
2. Click "Send Edit Link via Email"

**Expected Result:**
- The system should display "Edit link sent to [email]"
- The candidate should receive an email with the edit link

## Test Cases for Google Sheet Integration

### Test Case 7: Google Sheet with Candidate ID Column

**Steps:**
1. Add a column named "Candidate ID" to the Google Sheet
2. Add some test Candidate IDs (e.g., `CAND-001`, `CAND-002`)
3. Log in as a receptionist
4. Navigate to the Gatekeeper Form
5. Enter Candidate ID: `CAND-001`
6. Enter Passcode: `BRV123`
7. Click "Verify and Get Edit Link"

**Expected Result:**
- The system should find the candidate with ID `CAND-001`
- The edit link should be displayed

### Test Case 8: Google Sheet without Candidate ID Column

**Steps:**
1. Remove the "Candidate ID" column from the Google Sheet
2. Log in as a receptionist
3. Navigate to the Gatekeeper Form
4. Enter a Candidate ID that appears somewhere in the Google Sheet data
5. Enter Passcode: `BRV123`
6. Click "Verify and Get Edit Link"

**Expected Result:**
- The system should generate Candidate IDs
- The system should attempt to match the entered ID with the generated IDs
- If a match is found, the edit link should be displayed

## Troubleshooting

If any test fails, check the following:

1. **CV Matching Issues:**
   - Ensure the CV files are named correctly (e.g., `CAND-001_CV.pdf`)
   - Ensure the CV files are in the `data/resumes` directory
   - Check that the Candidate ID entered matches the one in the filename

2. **Gatekeeper Form Issues:**
   - Ensure the SECRET_PASSCODE in gatekeeper.py is set to `BRV123`
   - Check that the Google Sheet has an "Edit URL" column
   - Verify that the Google Apps Script is running and adding edit URLs to the sheet

3. **Google Sheet Integration Issues:**
   - Check that the Google Sheet is accessible to the application
   - Ensure the Google Sheet has the necessary columns (Email, Edit URL)
   - Verify that the Google Sheet is properly linked to the Google Form

## Reporting Issues

If you encounter any issues during testing, please document:

1. The test case that failed
2. The steps you took
3. The expected result
4. The actual result
5. Any error messages displayed

This information will help in diagnosing and fixing the issues.