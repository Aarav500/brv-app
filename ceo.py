# ceo.py
import re
import secrets
import string
from datetime import datetime, timedelta
import streamlit as st

from db_postgres import (
    get_conn, update_user_password,
    get_all_users_with_permissions, set_user_permission,
    get_all_candidates,
    delete_candidate_by_actor, update_candidate_form_data
)

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
    users = []
    for r in rows:
        users.append({
            "id": r[0],
            "email": r[1],
            "role": r[2],
            "last_changed": r[3],
            "created_at": r[4],
        })
    return users


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


def show_ceo_panel():
    st.header("CEO — Administration Panel")

    current_user = st.session_state.get("user")
    if not current_user:
        st.error("No active user session. Please log in.")
        return

    # -------------------------
    # USER PERMISSION MANAGEMENT
    # -------------------------
    st.subheader("User Permissions")
    if current_user["role"] not in ("ceo", "admin"):
        st.warning("You do not have permission to manage users.")
    else:
        users = get_all_users_with_permissions()
        if not users:
            st.warning("No users found.")
        else:
            for u in users:
                with st.expander(f"{u['email']} ({u['role']})", expanded=False):
                    st.write(f"**ID:** {u['id']}")
                    st.write(f"**Created:** {u['created_at']}")

                    col1, col2 = st.columns(2)
                    with col1:
                        can_view = st.checkbox(
                            "Can View CVs", value=u.get("can_view_cvs", False),
                            key=f"view_{u['id']}"
                        )
                    with col2:
                        can_delete = st.checkbox(
                            "Can Delete Candidate Records", value=u.get("can_delete_records", False),
                            key=f"delete_{u['id']}"
                        )

                    if st.button("Update Permissions", key=f"perm_{u['id']}"):
                        if set_user_permission(u["id"], can_view=can_view, can_delete=can_delete):
                            st.success("Permissions updated.")
                            st.rerun()
                        else:
                            st.error("Failed to update permissions.")

    st.markdown("---")

    # -------------------------
    # USER ACCOUNT MANAGEMENT
    # -------------------------
    st.subheader("All Users")
    users = _fetch_users()
    for u in users:
        with st.expander(f"{u['email']}  ({u['role']})", expanded=False):
            st.write(f"**ID:** {u['id']}")
            st.write(f"**Last password change:** {u.get('last_changed', '—')}")

            # Update email
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

            # Reset password
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

            # Remove user
            st.markdown("---")
            if st.button("Remove User", type="secondary", key=f"del_{u['id']}"):
                if _delete_user_by_id(u["id"]):
                    st.success("User removed.")
                    st.rerun()
                else:
                    st.error("Failed to remove user.")

    # 30-day forced reset helper
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

    # -------------------------
    # CANDIDATE RECORD DELETION
    # -------------------------
    st.markdown("---")
    st.subheader("Candidate Records")

    if current_user.get("role") not in ("ceo", "admin"):
        st.info("Only CEO/Admin can delete candidates.")
    else:
        candidates = get_all_candidates()
        if not candidates:
            st.caption("No candidates found.")
        for c in candidates:
            with st.expander(f"{c['name']} — {c['candidate_id']}", expanded=False):
                st.write(f"**Email:** {c.get('email','—')}")
                st.write(f"**Phone:** {c.get('phone','—')}")
                st.write(f"**Created At:** {c.get('created_at','—')}")

                if st.button("🗑️ Delete Candidate", key=f"delcand_{c['candidate_id']}"):
                    if delete_candidate_by_actor(c["candidate_id"], current_user["id"]):
                        st.success("Candidate deleted successfully.")
                        st.rerun()
                    else:
                        st.error("Deletion failed.")

    st.markdown("---")
    st.caption("Emails are validated before updates. Passwords are stored hashed via the existing DB layer.")
