import streamlit as st
import pandas as pd
import base64
import os
import io
import json
from datetime import datetime
from database import (
    get_all_candidates,
    get_candidate_details,
    delete_candidate,
    update_candidate,
    get_all_users,
    update_user_role,
    get_interview_notes
)

# =========================
# Utility Functions
# =========================

def load_css():
    st.markdown(
        """
        <style>
        .cv-frame {
            width: 100%;
            height: 600px;
            border: none;
            border-radius: 8px;
        }
        .interview-card {
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 10px;
            background: #fafafa;
        }
        .interview-title {
            font-weight: bold;
            font-size: 16px;
            margin-bottom: 6px;
        }
        .interview-field {
            font-size: 14px;
            margin-left: 6px;
        }
        </style>
        """,
        unsafe_allow_html=True
    )


def get_file_download_link(file_path, label="Download"):
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            data = f.read()
        b64 = base64.b64encode(data).decode()
        href = f'<a href="data:application/octet-stream;base64,{b64}" download="{os.path.basename(file_path)}">{label}</a>'
        return href
    return None


def preview_cv(file_path):
    if not os.path.exists(file_path):
        st.warning("No CV uploaded.")
        return
    ext = os.path.splitext(file_path)[1].lower()

    try:
        if ext == ".pdf":
            with open(file_path, "rb") as f:
                base64_pdf = base64.b64encode(f.read()).decode("utf-8")
            pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" class="cv-frame"></iframe>'
            st.markdown(pdf_display, unsafe_allow_html=True)

        elif ext in [".txt"]:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            st.text_area("CV Preview", content, height=400)

        elif ext in [".jpg", ".jpeg", ".png"]:
            st.image(file_path, caption="CV Preview", use_container_width=True)

        else:
            st.info("Preview not supported. Please download instead.")
            link = get_file_download_link(file_path, "Download CV")
            if link:
                st.markdown(link, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Error rendering CV: {e}")
        link = get_file_download_link(file_path, "Download CV")
        if link:
            st.markdown(link, unsafe_allow_html=True)


def render_interview_notes(candidate_id):
    notes = get_interview_notes(candidate_id)
    if not notes or len(notes) == 0:
        st.info("No interview notes available.")
        return
    for note in notes:
        # Skip system or creation events
        if "system" in note.get("type", "").lower() or "creation" in note.get("type", "").lower():
            continue
        st.markdown('<div class="interview-card">', unsafe_allow_html=True)
        st.markdown(
            f"<div class='interview-title'>{note.get('title','Interview Note')}</div>",
            unsafe_allow_html=True
        )
        for k, v in note.items():
            if k in ["title", "id", "candidate_id"]:
                continue
            st.markdown(
                f"<div class='interview-field'><b>{k.capitalize()}</b>: {v}</div>",
                unsafe_allow_html=True
            )
        st.markdown("</div>", unsafe_allow_html=True)


# =========================
# Candidate Management
# =========================

def candidate_management():
    st.subheader("Candidate Management")
    candidates = get_all_candidates()
    if not candidates or len(candidates) == 0:
        st.info("No candidates available.")
        return

    df = pd.DataFrame(candidates)
    search = st.text_input("Search candidates")
    if search:
        df = df[df.apply(lambda row: row.astype(str).str.contains(search, case=False).any(), axis=1)]

    # Multi-select for batch deletion
    selected = st.multiselect("Select candidates to delete", df["id"].tolist())
    if st.button("Delete Selected", type="primary") and selected:
        for cid in selected:
            delete_candidate(cid)
        st.success(f"Deleted {len(selected)} candidate(s).")
        st.experimental_rerun()

    st.dataframe(df)

    # Candidate details
    selected_id = st.selectbox("View candidate details", df["id"].tolist())
    if selected_id:
        details = get_candidate_details(selected_id)
        if details:
            st.write("### Candidate Details")
            st.json(details)

            # CV Preview
            if "cv_path" in details and details["cv_path"]:
                st.write("### CV Preview")
                preview_cv(details["cv_path"])

            # Interview Notes
            st.write("### Interview Notes")
            render_interview_notes(selected_id)

            # Update candidate
            with st.expander("Edit Candidate"):
                new_name = st.text_input("Name", details.get("name", ""))
                new_email = st.text_input("Email", details.get("email", ""))
                if st.button("Save Changes"):
                    update_candidate(selected_id, {"name": new_name, "email": new_email})
                    st.success("Candidate updated successfully.")
                    st.experimental_rerun()


# =========================
# User Management (NO CANDIDATE LOGIC)
# =========================

def user_management():
    st.subheader("User Management")
    users = get_all_users()
    if not users or len(users) == 0:
        st.info("No users available.")
        return
    df = pd.DataFrame(users)
    st.dataframe(df)

    selected_user = st.selectbox("Select user to update role", df["id"].tolist())
    if selected_user:
        user_details = df[df["id"] == selected_user].iloc[0]
        st.write(f"### {user_details['username']} ({user_details['role']})")
        new_role = st.selectbox("New Role", ["Admin", "Manager", "Interviewer", "Viewer"])
        if st.button("Update Role"):
            update_user_role(selected_user, new_role)
            st.success("User role updated successfully.")
            st.experimental_rerun()


# =========================
# Main CEO Dashboard
# =========================

def ceo_dashboard():
    load_css()
    st.title("CEO Dashboard")

    menu = ["Candidate Management", "User Management"]
    choice = st.sidebar.radio("Navigation", menu)

    if choice == "Candidate Management":
        candidate_management()
    elif choice == "User Management":
        user_management()


if __name__ == "__main__":
    ceo_dashboard()
