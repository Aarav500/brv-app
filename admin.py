# admin.py

import re
import secrets
import string
from datetime import datetime, timedelta

import streamlit as st

from db_postgres import (
    get_conn, update_user_password,
    get_all_users_with_permissions, set_user_permission,
    get_all_candidates, get_total_cv_storage_usage, get_candidate_statistics,
    delete_candidate, get_user_permissions, create_user_in_db
)

# -------------------------
# Helpers
# -------------------------
EMAIL_RE = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.I)

def _valid_email(addr: str) -> bool:
    return bool(EMAIL_RE.match(addr or ""))

def _random_password(n: int = 12) -> str:
    chars = string.ascii_letters + string.digits + "!@#$%?"
    return "".join(secrets.choice(chars) for _ in range(n))

def _fetch_users():
    conn = get_conn()
    with conn, conn.cursor() as cur:
        cur.execute("""
            SELECT id, email, role,
                   COALESCE(updated_at, created_at) AS last_changed,
                   created_at
            FROM users
            ORDER BY id
        """)
        rows = cur.fetchall()
    conn.close()
    return [
        {"id": r[0], "email": r[1], "role": r[2], "last_changed": r[3], "created_at": r[4]}
        for r in rows
    ]

def _delete_user_by_id(uid: int) -> bool:
    conn = get_conn()
    with conn, conn.cursor() as cur:
        cur.execute("DELETE FROM users WHERE id=%s", (uid,))
        ok = cur.rowcount > 0
    conn.close()
    return ok

def _update_email(uid: int, new_email: str) -> bool:
    conn = get_conn()
    with conn, conn.cursor() as cur:
        cur.execute("UPDATE users SET email=%s WHERE id=%s", (new_email, uid))
        ok = cur.rowcount > 0
    conn.close()
    return ok

def _reset_password(uid: int, new_password: str) -> bool:
    conn = get_conn()
    with conn, conn.cursor() as cur:
        cur.execute("SELECT email FROM users WHERE id=%s", (uid,))
        row = cur.fetchone()
        if not row:
            return False
        email = row[0]
    return update_user_password(email, new_password)

def _users_older_than_30_days(users):
    cutoff = datetime.utcnow() - timedelta(days=30)
    res = []
    for u in users:
        last = u.get("last_changed") or u.get("created_at")
        try:
            if isinstance(last, str):
                last = datetime.fromisoformat(last.replace("Z", ""))
        except Exception:
            pass
        if last and last < cutoff:
            res.append(u)
    return res

def _human_bytes(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    i, v = 0, float(n)
    while v >= 1024 and i < len(units) - 1:
        v /= 1024.0
        i += 1
    return f"{v:.2f} {units[i]}"


# -------------------------
# Admin Panel (with access control)
# -------------------------
def show_admin_panel():
    st.header("⚙️ Admin — Administration Panel")

    current_user = st.session_state.get("user")
    if not current_user:
        st.error("No active user session. Please log in.")
        return

    # Load permissions
    perms = get_user_permissions(current_user["id"]) or {}
    role = current_user.get("role", "").lower()
    is_ceo = (role == "ceo")

    # -------------------------
    # OVERVIEW: Storage + Stats
    # -------------------------
    with st.container():
        colA, colB = st.columns(2)
        with colA:
            total_bytes = get_total_cv_storage_usage()
            st.metric("Total CV Storage Used", _human_bytes(total_bytes))
            if total_bytes:
                limit_mb = 500
                used_mb = total_bytes / (1024 * 1024)
                pct = min(100, int((used_mb / limit_mb) * 100))
                st.progress(pct)
        with colB:
            stats = get_candidate_statistics() or {}
            st.metric("Total Candidates", stats.get("total_candidates", 0))
            st.metric("With Resume", stats.get("candidates_with_resume", 0))
            st.metric("Interviews", stats.get("total_interviews", 0))

    st.markdown("---")

    # -------------------------
    # USER PERMISSION MANAGEMENT
    # -------------------------
    if is_ceo:
        st.subheader("User Permissions")
        users = get_all_users_with_permissions()
        if not users:
            st.warning("No users found.")
        else:
            for u in users:
                with st.expander(f"{u['email']} ({u['role']})", expanded=False):
                    st.write(f"**ID:** {u['id']} | **Created:** {u['created_at']}")

                    col1, col2 = st.columns(2)
                    with col1:
                        can_view = st.checkbox("Can View CVs", value=u.get("can_view_cvs", False), key=f"view_{u['id']}")
                    with col2:
                        can_delete = st.checkbox("Can Delete Candidate Records", value=u.get("can_delete_records", False), key=f"delete_{u['id']}")

                    can_grant_delete = u.get("can_grant_delete", False)
                    can_grant_delete = st.checkbox("Can Grant Delete Rights", value=can_grant_delete, key=f"grant_{u['id']}")

                    if st.button("Update Permissions", key=f"perm_{u['id']}"):
                        if set_user_permission(
                            u["id"],
                            can_view=can_view,
                            can_delete=can_delete,
                            can_grant_delete=can_grant_delete
                        ):
                            st.success("Permissions updated.")
                            st.rerun()
                        else:
                            st.error("Failed to update permissions.")

        st.markdown("---")
    else:
        st.info("🔒 Only CEO can manage user permissions.")

    # -------------------------
    # USER ACCOUNT MANAGEMENT
    # -------------------------
    if is_ceo:
        st.subheader("Create New User")
        with st.form("create_user_form"):
            new_email = st.text_input("Email", key="create_user_email")
            new_role = st.selectbox("Role", ["candidate", "receptionist", "interviewer", "hr", "admin", "ceo"], index=0)
            colp1, colp2 = st.columns(2)
            with colp1:
                new_pw1 = st.text_input("Password", type="password", key="create_user_pw1")
            with colp2:
                new_pw2 = st.text_input("Confirm Password", type="password", key="create_user_pw2")
            create_submitted = st.form_submit_button("Create User")
        if create_submitted:
            if not _valid_email(new_email):
                st.error("Invalid email format.")
            elif not new_pw1:
                st.error("Password is required.")
            elif new_pw1 != new_pw2:
                st.error("Passwords do not match.")
            else:
                try:
                    ok = create_user_in_db(new_email.strip(), new_pw1, new_role)
                    if ok:
                        st.success("User created successfully.")
                        st.rerun()
                    else:
                        st.error("User already exists or creation failed.")
                except Exception as e:
                    st.error(f"Failed to create user: {e}")

        st.markdown("---")
        st.subheader("All Users")
        users = _fetch_users()
        for u in users:
            with st.expander(f"{u['email']}  ({u['role']})", expanded=False):
                st.write(f"**ID:** {u['id']}")
                st.write(f"**Last password change:** {u.get('last_changed', '—')}")

                new_email = st.text_input("New email", value=u["email"], key=f"email_{u['id']}")
                if st.button("Change Email", key=f"change_email_{u['id']}"):
                    if not _valid_email(new_email):
                        st.error("Invalid email format.")
                    else:
                        if _update_email(u["id"], new_email):
                            st.success("Email updated.")
                            st.rerun()
                        else:
                            st.error("Failed to update email.")

                col1, col2 = st.columns(2)
                with col1:
                    new_pw = st.text_input("New password", type="password", key=f"pw_{u['id']}")
                with col2:
                    if st.button("Generate Strong Password", key=f"gen_{u['id']}"):
                        st.session_state[f"pw_{u['id']}"] = _random_password()
                        st.rerun()
                if st.button("Reset Password", key=f"reset_{u['id']}"):
                    pw = st.session_state.get(f"pw_{u['id']}", new_pw)
                    if not pw:
                        st.error("Please provide a new password.")
                    else:
                        if _reset_password(u["id"], pw):
                            st.success("Password reset.")
                        else:
                            st.error("Failed to reset password.")

                st.markdown("---")
                if st.button("Remove User", type="secondary", key=f"del_{u['id']}"):
                    if _delete_user_by_id(u["id"]):
                        st.success("User removed.")
                        st.rerun()
                    else:
                        st.error("Failed to remove user.")

        st.markdown("---")
        st.subheader("Force Reset Passwords (older than 30 days)")
        stale = _users_older_than_30_days(users)
        if not stale:
            st.caption("No accounts older than 30 days found.")
        else:
            st.write(f"{len(stale)} user(s) have passwords older than 30 days.")
            if st.button("Reset All (generate random passwords)"):
                ok, fail = 0, 0
                for u in stale:
                    if _reset_password(u["id"], _random_password()):
                        ok += 1
                    else:
                        fail += 1
                st.success(f"Done. Reset: {ok}, Failed: {fail}.")
    else:
        st.info("🔒 Only CEO can manage user accounts and passwords.")

    st.markdown("---")

    # -------------------------
    # Candidate Records
    # -------------------------
    st.subheader("Candidate Records")

    # Candidate delete access (Admin/CEO or configured delete rights)
    can_delete_records = bool(perms.get("can_delete_records")) or bool(perms.get("can_grant_delete")) or role in ("admin", "ceo")
    if can_delete_records:
        candidates = get_all_candidates()
        if not candidates:
            st.caption("No candidates found.")
        for c in candidates:
            with st.expander(f"{c['name']} — {c['candidate_id']}", expanded=False):
                st.write(f"**Email:** {c.get('email','—')}")
                st.write(f"**Phone:** {c.get('phone','—')}")
                st.write(f"**Created At:** {c.get('created_at','—')}")

                if st.button("🗑️ Delete Candidate", key=f"delcand_{c['candidate_id']}"):
                    try:
                        ok = delete_candidate(c["candidate_id"], current_user["id"])
                        if ok:
                            st.success("Candidate deleted successfully.")
                            st.rerun()
                        else:
                            st.error("You don’t have permission to delete this record.")
                    except Exception as e:
                        st.error(f"Deletion failed: {e}")
    else:
        st.info("🔒 You don’t have permission to delete this record.")

    st.markdown("---")
    st.caption("Admin panel actions depend on CEO-granted rights. CEO always has full access.")
