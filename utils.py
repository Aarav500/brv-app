# utils.py
import streamlit as st
from auth import get_current_user

VALID_ROLES = {"ceo","admin","hr","receptionist","interviewer","candidate"}

def require_login():
    user = get_current_user()
    if not user:
        st.warning("Please login first.")
        st.stop()

def get_user():
    return get_current_user()
