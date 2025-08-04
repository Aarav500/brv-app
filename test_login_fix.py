import streamlit as st
from auth import login

# Test login with default credentials
def test_login():
    print("Testing login with default credentials...")
    
    # Default credentials from database.py
    test_credentials = [
        ("reception@bluematrixit.com", "123"),
        ("interview@bluematrixit.com", "234"),
        ("nikhil.shah@bluematrixit.com", "345")
    ]
    
    # Initialize session state for testing
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None
    if 'user_role' not in st.session_state:
        st.session_state.user_role = None
    
    # Test each set of credentials
    for email, password in test_credentials:
        print(f"\nTesting login with: {email} / {password}")
        success, message = login(email, password)
        
        if success:
            print(f"✅ Login successful: {message}")
            print(f"User role: {st.session_state.user_role}")
            
            # Reset session state for next test
            st.session_state.authenticated = False
            st.session_state.user_id = None
            st.session_state.user_role = None
        else:
            print(f"❌ Login failed: {message}")

if __name__ == "__main__":
    test_login()