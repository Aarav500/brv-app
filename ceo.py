# ceo.py
import re
import secrets
import string
from datetime import datetime, timedelta
import streamlit as st
import matplotlib.pyplot as plt

from db_postgres import (
    get_conn, update_user_password,
    get_all_users_with_permissions, set_user_permission,
    get_all_candidates, get_total_cv_storage_usage, get_candidate_statistics,
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


def _human_bytes(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    v = float(n)
    while v >= 1024 and i < len(units) - 1:
        v /= 1024.0
        i += 1
    return f"{v:.2f} {units[i]}"


def _plot_candidate_charts(stats: dict):
    """Generate simple pie/bar charts for CEO overview"""
    if not stats:
        st.info("No statistics available to visualize.")
        return

    # Pie: Resume vs No Resume
    fig1, ax1 = plt.subplots()
    labels = ["With Resume", "Without Resume"]
    values = [stats.get("candidates_with_resume", 0),
              stats.get("total_candidates", 0) - stats.get("candidates_with_resume", 0)]
    ax1.pie(values, labels=labels, autopct="%1.1f%%", startangle=90)
    ax1.set_title("Resume Uploads")
    st.pyplot(fig1)

    # Bar: Interview Results (if breakdown available)
    interview_breakdown = stats.get("interview_results", {})
    if interview_breakdown:
        fig2, ax2 = plt.subplots()
        ax2.bar(interview_breakdown.keys(), interview_breakdown.values())
        ax2.set_title("Interview Outcomes")
        ax2.set_ylabel("Count")
        st.pyplot(fig2)


def show_ceo_panel():
    st.header("CEO — Administration Panel")

    current_user = st.session_state.get("user")
    if not current_user:
        st.error("No active user session. Please log in.")
        return

    # -------------------------
    # STORAGE + STATISTICS
    # -------------------------
    st.subheader("System Overview")
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
    st.subheader("📊 Advanced Candidate Statistics")
    if stats:
        _plot_candidate_charts(stats)
        st.json(stats)  # Pretty print everything for transparency
    else:
        st.caption("No stats available.")

    # -------------------------
    # USER PERMISSIONS
    # -------------------------
    st.markdown("---")
    st.subheader("User Permissions")
    users = get_all_users_with_permissions()
    if not users:
        st.warning("No users found.")
    else:
        for u in users:
            with st.expander(f"{u['email']} ({u['role']})", expanded=False):
                st.write(f"**ID:** {u['id']} | **Created:** {u['created_at']}")

                can_view = st.checkbox(
                    "Can View CVs", value=u.get("can_view_cvs", False), key=f"view_{u['id']}"
                )
                can_delete = st.checkbox(
                    "Can Delete Candidate Records", value=u.get("can_delete_records", False), key=f"delete_{u['id']}"
                )
                can_grant_delete = st.checkbox(
                    "Can Grant Delete Rights", value=u.get("can_grant_delete", False), key=f"grant_{u['id']}"
                )

                if st.button("Update Permissions", key=f"perm_{u['id']}"):
                    if set_user_permission(
                        u["id"], can_view=can_view, can_delete=can_delete, can_grant_delete=can_grant_delete
                    ):
                        st.success("Permissions updated.")
                        st.rerun()
                    else:
                        st.error("Failed to update permissions.")

    # -------------------------
    # USER MANAGEMENT
    # -------------------------
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

    # -------------------------
    # PASSWORD AUDIT
    # -------------------------
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
    # CANDIDATE RECORDS (Read-Only)
    # -------------------------
    st.markdown("---")
    st.subheader("Candidate Records (Read-Only)")
    candidates = get_all_candidates()
    if not candidates:
        st.caption("No candidates found.")
    else:
        for c in candidates:
            with st.expander(f"{c['name']} — {c['candidate_id']}", expanded=False):
                st.write(f"**Email:** {c.get('email','—')}")
                st.write(f"**Phone:** {c.get('phone','—')}")
                st.write(f"**Created At:** {c.get('created_at','—')}")
                if c.get("form_data"):
                    st.json(c["form_data"])

    st.markdown("---")
    st.caption("CEO can now manage all permissions including delete rights.")
