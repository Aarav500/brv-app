# main.py
import streamlit as st
from auth import (
    auth_router,
    is_logged_in,
    logout,
    require_login,
    seed_users_if_needed,
    manage_users_view,
)
import ceo
import hr
import interviewer
import receptionist
import candidate


# === INIT ===
st.set_page_config(page_title="BRV Recruitment", layout="wide")
seed_users_if_needed()


# === SIDEBAR NAVIGATION ===
def sidebar_navigation():
    st.sidebar.title("📌 Navigation")

    if not is_logged_in():
        return "auth"

    user = st.session_state.user
    role = user.get("role", "").lower()

    st.sidebar.write(f"**Logged in as:** {user['email']}")
    # hide explicit role for CEO (or show role for others)
    if role and role.lower() != "ceo":
        st.sidebar.write(f"**Role:** {role.capitalize()}")

    # Core nav items
    pages = {"Profile": "profile"}

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

    elif page == "profile":
        require_login()
        st.title("👤 My Profile")
        st.write("See your details under the profile tab in auth.py.")

        if st.button("Logout"):
            logout()

    elif page == "manage_users":
        manage_users_view()

    elif page == "ceo":
        require_login()
        ceo.ceo_dashboard()

    elif page == "hr":
        require_login()
        hr.hr_dashboard()

    elif page == "interviewer":
        require_login()
        interviewer.interviewer_dashboard()

    elif page == "receptionist":
        require_login()
        receptionist.receptionist_dashboard()

    elif page == "candidate":
        require_login()
        candidate.candidate_portal()

    else:
        st.error("Page not found.")


# === ENTRY POINT ===
def main():
    page = sidebar_navigation()
    router(page)


if __name__ == "__main__":
    main()
