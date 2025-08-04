# Receptionist Guide: Managing Candidates and Form Edits

This guide explains how to use the BRV Applicant Management System, including the Candidate ID Panel for tracking candidates and the "Allow Edit" functionality for granting candidates permission to edit their Google Form responses.

## Candidate ID Panel

The Candidate ID Panel provides a centralized view of all candidates with their Candidate IDs, contact information, CV status, and edit links. This panel makes it easy to track and manage candidates throughout the application process.

### Accessing the Candidate ID Panel

1. Log in to the BRV Applicant Management System with your receptionist credentials
2. In the navigation sidebar, click on "Candidate ID Panel"
3. The panel will load, displaying all candidates from the Google Form responses

### Understanding the Panel Layout

The Candidate ID Panel displays the following information for each candidate:

- **Candidate Name**: The full name of the candidate
- **Email ID**: The candidate's email address
- **Phone Number**: The candidate's contact number
- **Candidate ID**: The unique identifier assigned to the candidate (e.g., BRV-1024)
- **CV Status**: Indicates whether a CV has been uploaded (✅) or not (❌)
- **Edit Link**: A button to access the Google Form edit link
- **Remarks**: A section to add notes about the candidate

### Using Filtering and Sorting

To find specific candidates quickly:

1. **Filter by Candidate ID**: Enter a partial or complete Candidate ID in the "Filter by Candidate ID" field
2. **Filter by Name**: Enter a partial or complete name in the "Filter by Name" field
3. **Sorting**: The list is automatically sorted by Candidate ID for easy reference

### Checking CV Status

The CV status indicator shows whether a CV has been uploaded for each candidate:

- ✅ indicates that a CV has been found for this Candidate ID
- ❌ indicates that no CV has been found for this Candidate ID

### Using Edit Links

To access a candidate's form edit link:

1. Locate the candidate in the list
2. Click the "Edit Form" button in their row
3. The edit link will open in a new tab, allowing you to make changes to their form submission

### Adding and Managing Remarks

To add notes about a candidate:

1. Click on the candidate's entry to expand their details
2. Scroll down to the "Remarks" section
3. Enter your notes in the text area
4. The remarks will be saved automatically when you click outside the text area

### Auto-Refresh and Manual Refresh

The panel can be configured to automatically refresh:

1. Check the "Auto-refresh every 5 minutes" option at the top of the panel
2. Alternatively, click the "🔄 Refresh Data" button to manually refresh the data

### Troubleshooting the Candidate ID Panel

#### No Candidates Displayed

If no candidates are displayed in the panel:

1. Check that the Google Sheet is properly connected and contains form responses
2. Click the "🔄 Refresh Data" button to fetch the latest data
3. Verify that you have the correct permissions to access the Google Sheet

#### Missing Candidate IDs

If candidates are displayed but Candidate IDs are missing:

1. Check that the Google Sheet has a column for Candidate IDs (often labeled "Candidate ID" or "Application ID")
2. If no such column exists, the system will attempt to use Column Z or create temporary IDs
3. Contact the administrator to set up proper Candidate ID assignment

#### CV Status Shows ❌ Despite CV Being Uploaded

If the CV status shows ❌ even though you know a CV has been uploaded:

1. Verify that the CV file is named correctly with the Candidate ID (e.g., CV_BRV-1024.pdf)
2. Check that the CV is stored in the correct location (cvs folder or Google Drive)
3. Click the "🔄 Refresh Data" button to update the status

#### Edit Link Not Working

If the "Edit Form" button doesn't work or shows "Not available":

1. Verify that the Google Form is set up to collect email addresses
2. Check that the Google Sheet has an "Edit URL" column
3. Ensure the Google Apps Script for capturing edit URLs is properly installed
4. Try using the Gatekeeper Form as an alternative method to get the edit link

## Form Edit Management

As a receptionist, you can allow candidates to edit their previously submitted Google Form responses. This is useful when:

- A candidate needs to update their contact information
- A candidate wants to upload a new resume
- A candidate needs to correct errors in their application
- Additional information is required from the candidate

The system sends an email with a unique edit link directly to the candidate, allowing them to make changes to their original submission.

## Step-by-Step Guide

### 1. Accessing Candidate Profiles

1. Log in to the BRV Applicant Management System with your receptionist credentials
2. Click on "View Profiles" in the navigation sidebar
3. You'll see a list of all candidates in the system

### 2. Selecting a Candidate

1. From the candidate list, select the candidate who needs to edit their form
2. The candidate's profile will be displayed, showing their personal information, resume, and assessment data

### 3. Granting Edit Permission

In the candidate's profile, you'll find a section titled "Form Edit Permission":

1. **Check for Edit URL**
   - The system automatically checks if an edit URL is available for this candidate
   - If no edit URL is found, you'll see a warning message

2. **Refresh Edit URLs (if needed)**
   - If you've just set up the Google Apps Script or if the candidate recently submitted the form, click the "Refresh Edit URLs" button
   - This will fetch the latest edit URLs from the Google Sheet

3. **Send Edit Link**
   - If an edit URL is available, click the "Send Edit Link to Candidate" button
   - The system will send an email to the candidate with their unique edit link
   - You'll see a success message if the email was sent successfully

### 4. Following Up

After sending the edit link:

1. Inform the candidate that they should check their email for the edit link
2. Advise them to make the necessary changes and resubmit the form
3. Let them know that they must be signed in with the same Google account they used for the initial submission

### 5. Verifying Updates

To verify that the candidate has updated their information:

1. After the candidate has made changes, go back to the "View Profiles" section
2. Click the "Reload Data" button to refresh the candidate information
3. Select the candidate again to view their updated profile

## Troubleshooting

### No Edit URL Available

If no edit URL is found for a candidate:

1. Verify that the Google Form is set up correctly:
   - "Collect email addresses" is enabled
   - "Limit to 1 response" is enabled
   - "Allow response editing" is enabled

2. Check that the Google Apps Script is properly set up:
   - The script has been added to the Google Sheet
   - The script has been run at least once
   - The "Edit URL" column exists in the Google Sheet

3. Ensure the candidate has actually submitted the form:
   - The candidate must have submitted the form through the Google Form, not just been added manually to the system

### Email Not Sending

If the email with the edit link fails to send:

1. Check that the email configuration in the system is correct
2. Verify that the candidate's email address is valid
3. Try sending the edit link again after a few minutes

### Candidate Cannot Edit Form

If the candidate reports they cannot edit the form:

1. Ensure they are signed in with the same Google account they used for the initial submission
2. Verify that the edit link hasn't expired (Google Form edit links can expire after a certain period)
3. If needed, send a new edit link to the candidate

## Best Practices

1. **Communicate Clearly**: Always inform candidates about what information they need to update and why.

2. **Verify Email Addresses**: Double-check that you have the correct email address for the candidate before sending the edit link.

3. **Follow Up**: After sending an edit link, follow up with the candidate to ensure they received it and were able to make the necessary changes.

4. **Document Changes**: Make a note in the candidate's profile about what changes were requested and when the edit link was sent.

5. **Refresh Data**: Always refresh the data after a candidate has made changes to ensure you're viewing the most up-to-date information.

## Additional Resources

For more detailed information about the Google Forms setup and the controlled editing workflow, refer to the [Google Forms Setup Guide](GOOGLE_FORMS_SETUP.md).

If you encounter any issues that aren't covered in this guide, please contact the system administrator for assistance.