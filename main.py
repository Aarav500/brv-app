# main.py
import streamlit as st
from auth import (
    auth_router,
    is_logged_in,
    logout,
    require_login,
    seed_users_if_needed,
    manage_users_view,
    get_current_user,
)
import ceo
import interviewer
import receptionist
import candidate_view
import admin


# === INIT ===
st.set_page_config(page_title="BRV Recruitment", layout="wide")
seed_users_if_needed()


# === SIDEBAR NAVIGATION ===
def sidebar_navigation():
    st.sidebar.title("📌 Navigation")

    if not is_logged_in():
        return "auth"

    user = get_current_user()
    role = (user.get("role", "") if user else "").lower()

    st.sidebar.write(f"**Logged in as:** {user['email']}")
    # hide explicit role for CEO (or show role for others)
    if role and role.lower() != "ceo":
        st.sidebar.write(f"**Role:** {role.capitalize()}")

    # Add a persistent Logout button in sidebar
    if st.sidebar.button("Logout"):
        logout()

    # Core nav items
    pages = {}

    # Role-based pages
    if role == "ceo":
        pages["CEO Dashboard"] = "ceo"
        pages["Manage Users"] = "manage_users"
    elif role == "hr":
        pages["HR Dashboard"] = "hr"
    elif role == "interviewer":
        pages["Interviewer Dashboard"] = "interviewer"
    elif role == "receptionist":
        pages["Receptionist Dashboard"] = "receptionist"
    elif role == "candidate":
        pages["Candidate Portal"] = "candidate"

    choice = st.sidebar.radio("Go to", list(pages.keys()))
    return pages[choice]


# === ROUTER ===
def router(page: str):
    if page == "auth":
        auth_router()


    elif page == "manage_users":
        require_login()
        admin.show_admin_panel()

    elif page == "ceo":
        require_login()
        ceo.show_ceo_panel()

    elif page == "hr":
        require_login()
        admin.show_admin_panel()

    elif page == "interviewer":
        require_login()
        interviewer.interviewer_view()

    elif page == "receptionist":
        require_login()
        receptionist.receptionist_view()

    elif page == "candidate":
        require_login()
        candidate_view.candidate_view()

    else:
        st.error("Page not found.")


# === ENTRY POINT ===
def main():
    page = sidebar_navigation()
    router(page)


if __name__ == "__main__":
    main()
