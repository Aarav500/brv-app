# utils.py
import streamlit as st

VALID_ROLES = {"ceo","admin","hr","receptionist","interviewer","candidate"}

def require_login():
    if "user" not in st.session_state:
        st.warning("Please login first.")
        st.stop()

def get_user():
    return st.session_state.get("user")
