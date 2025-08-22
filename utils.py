# utils.py
import streamlit as st
from auth import get_current_user
from db_postgres import get_user_permissions
VALID_ROLES = {"ceo","admin","hr","receptionist","interviewer","candidate"}

def require_login():
    user = get_current_user()
    if not user:
        st.warning("Please login first.")
        st.stop()

def get_user():
    return get_current_user()

def can_view_cvs(user_id: int) -> bool:
    p = get_user_permissions(user_id) or {}
    role = (p.get("role") or "").lower()
    return role in ("admin", "ceo") or bool(p.get("can_view_cvs"))

def can_delete_records(user_id: int) -> bool:
    p = get_user_permissions(user_id) or {}
    role = (p.get("role") or "").lower()
    return role in ("admin", "ceo") or bool(p.get("can_delete_records")) or bool(p.get("can_grant_delete"))