import streamlit as st
from auth import login

# Test login with SQLite credentials
def test_login_sqlite():
    print("Testing login with SQLite credentials...")
    
    # SQLite credentials based on the database check
    test_credentials = [
        ("ceo", "345"),  # Using default password from database.py
        ("reception", "123"),  # Using default password from database.py
        ("interview", "234")   # Using default password from database.py
    ]
    
    # Initialize session state for testing
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None
    if 'user_role' not in st.session_state:
        st.session_state.user_role = None
    
    # Test each set of credentials
    for username, password in test_credentials:
        print(f"\nTesting login with: {username} / {password}")
        success, message = login(username, password)
        
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
    test_login_sqlite()