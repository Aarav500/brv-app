# Test Plan: Controlled Editing System for Google Forms

This document outlines the test procedures for verifying the functionality of the controlled editing system for Google Forms in the BRV Applicant Management System.

## 1. Prerequisites Testing

### 1.1 Google Form Configuration

**Test Objective:** Verify that the Google Form is properly configured for controlled editing.

**Test Steps:**
1. Open the Google Form used for candidate applications
2. Go to Settings > Responses
3. Verify that "Collect email addresses" is enabled
4. Verify that "Limit to 1 response" is enabled
5. Verify that "Allow response editing" is enabled

**Expected Result:** All required settings are enabled in the Google Form.

### 1.2 Google Apps Script Deployment

**Test Objective:** Verify that the Google Apps Script is properly deployed and functioning.

**Test Steps:**
1. Open the Google Sheet linked to the Google Form
2. Verify that an "Edit URL" column exists
3. Submit a test form response using a test Google account
4. Verify that an edit URL appears in the "Edit URL" column for the new response
5. Open the Apps Script editor and run the `generateEditUrls` function manually
6. Verify that edit URLs are generated for all responses

**Expected Result:** The Google Apps Script is properly deployed and generating edit URLs for form responses.

## 2. Functionality Testing

### 2.1 Edit URLs Extraction

**Test Objective:** Verify that the system can fetch edit URLs from the Google Sheet.

**Test Steps:**
1. Log in to the BRV system as a receptionist
2. Navigate to the "View Profiles" section
3. Select a candidate profile
4. In the "Form Edit Permission" section, click the "Refresh Edit URLs" button
5. Check the application logs or debug output to verify that edit URLs are being fetched

**Expected Result:** The system successfully fetches edit URLs from the Google Sheet and displays appropriate messages based on whether edit URLs are found.

### 2.2 Email Sending

**Test Objective:** Verify that the system can send emails with edit links to candidates.

**Test Steps:**
1. Configure the email settings in the application (EMAIL_HOST, EMAIL_PORT, EMAIL_USER, EMAIL_PASS)
2. Log in to the BRV system as a receptionist
3. Navigate to the "View Profiles" section
4. Select a candidate profile with an available edit URL
5. Click the "Send Edit Link to Candidate" button
6. Verify that a success message is displayed
7. Check the recipient's email inbox for the edit link email

**Expected Result:** The system successfully sends an email with the edit link to the candidate and displays a success message.

### 2.3 Form Editing

**Test Objective:** Verify that candidates can use the edit link to modify their form responses.

**Test Steps:**
1. Receive an edit link email (from test 2.2)
2. Click on the edit link in the email
3. Verify that the Google Form opens with the previous responses pre-filled
4. Make changes to the form responses
5. Submit the form again
6. Verify that the changes are reflected in the Google Sheet

**Expected Result:** Candidates can successfully edit their form responses using the edit link.

## 3. End-to-End Workflow Testing

### 3.1 Complete Workflow

**Test Objective:** Verify the entire controlled editing workflow from form submission to data update.

**Test Steps:**
1. Submit a new test form response using a test Google account
2. Verify that the response appears in the Google Sheet with an edit URL
3. Log in to the BRV system as a receptionist
4. Navigate to the "View Profiles" section and select the test candidate
5. Click the "Send Edit Link to Candidate" button
6. Verify that the edit link email is received
7. Use the edit link to modify the form responses
8. Submit the form again
9. In the BRV system, refresh the candidate data
10. Verify that the updated information is displayed in the candidate profile

**Expected Result:** The entire workflow functions correctly, from form submission to data update.

### 3.2 Edge Cases

**Test Objective:** Verify system behavior in edge cases and error conditions.

**Test Cases:**

1. **No Edit URL Available:**
   - Select a candidate that was added manually (not through the Google Form)
   - Verify that an appropriate warning message is displayed
   - Verify that the setup instructions are available in an expander

2. **Invalid Email Address:**
   - Modify a candidate's email address to be invalid
   - Attempt to send an edit link
   - Verify that an appropriate error message is displayed

3. **Google Sheet Access Issues:**
   - Temporarily revoke the service account's access to the Google Sheet
   - Attempt to refresh edit URLs
   - Verify that an appropriate error message is displayed
   - Restore access and verify functionality returns

4. **Multiple Form Submissions:**
   - Submit a form response
   - Use the edit link to modify and resubmit
   - Verify that only one row exists in the Google Sheet (updated, not duplicated)
   - Verify that the edit URL still works for further edits

**Expected Result:** The system handles edge cases gracefully with appropriate error messages and recovery mechanisms.

## 4. Performance Testing

### 4.1 Large Dataset Handling

**Test Objective:** Verify system performance with a large number of form responses.

**Test Steps:**
1. Populate the Google Sheet with a large number of test responses (50+)
2. Run the Google Apps Script to generate edit URLs for all responses
3. Log in to the BRV system as a receptionist
4. Navigate to the "View Profiles" section
5. Measure the time taken to load the candidate list
6. Select a candidate and measure the time taken to fetch edit URLs
7. Click the "Refresh Edit URLs" button and measure the time taken to refresh

**Expected Result:** The system maintains acceptable performance even with a large number of form responses.

## 5. Security Testing

### 5.1 Access Control

**Test Objective:** Verify that only authorized users can send edit links.

**Test Steps:**
1. Log in to the BRV system as different user roles (interviewer, CEO, admin)
2. Attempt to access the "Form Edit Permission" functionality
3. Verify that only receptionists can send edit links

**Expected Result:** Only users with the receptionist role can send edit links to candidates.

### 5.2 Edit Link Security

**Test Objective:** Verify that edit links are secure and can only be used by the intended recipient.

**Test Steps:**
1. Send an edit link to a candidate
2. Attempt to use the edit link without being signed in to Google
3. Attempt to use the edit link while signed in with a different Google account
4. Attempt to use the edit link while signed in with the correct Google account

**Expected Result:** The edit link can only be used by the intended recipient who is signed in with the correct Google account.

## 6. Documentation Testing

### 6.1 User Guide Accuracy

**Test Objective:** Verify that the user documentation accurately reflects the system functionality.

**Test Steps:**
1. Review the RECEPTIONIST_GUIDE.md document
2. Follow each step in the guide while using the system
3. Verify that the actual system behavior matches the documented behavior
4. Check that all UI elements mentioned in the guide exist in the actual system
5. Verify that the troubleshooting tips are accurate and helpful

**Expected Result:** The user documentation accurately reflects the system functionality and provides helpful guidance.

## Test Reporting

For each test, record the following information:

1. Test ID and name
2. Test date and time
3. Tester name
4. Test environment (browser, OS, etc.)
5. Test result (Pass/Fail)
6. Observations and issues encountered
7. Screenshots or logs (if applicable)

Report any issues found during testing with the following details:

1. Issue description
2. Steps to reproduce
3. Expected vs. actual behavior
4. Severity (Critical, High, Medium, Low)
5. Screenshots or logs (if applicable)