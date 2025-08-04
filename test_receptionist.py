import streamlit as st
from receptionist import receptionist_view

# Set page configuration
st.set_page_config(
    page_title="Test Receptionist View - BRV Walk-in Management App",
    page_icon="📝",
    layout="wide"
)

# Run the receptionist view
receptionist_view()

# Instructions for testing
st.sidebar.title("Testing Instructions")
st.sidebar.info("""
1. Upload a dummy resume (PDF, DOC, or DOCX)
2. Fill in the HR section
3. Click the Submit button
4. Verify that the success message appears
5. Check that the resume is saved in data/resumes/
6. Check that the data is saved in data/database.db
""")

# Display a note about the test
st.sidebar.warning("""
This is a test script for the receptionist view.
In the real app, this view would be accessed after login.
""")