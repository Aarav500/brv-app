# ceo.py
# -----------------------------------------------------------------------------
# CEO — Administration Panel
# Full file (copy-paste). Integrates with db_postgres.py (permission-aware delete).
# -----------------------------------------------------------------------------

import re
import secrets
import string
from datetime import datetime, timedelta

import streamlit as st
import matplotlib.pyplot as plt

from db_postgres import (
    get_conn,
    update_user_password,
    set_user_permission,
    get_all_users_with_permissions,
    get_all_candidates,
    get_total_cv_storage_usage,
    get_candidate_statistics,
    get_candidate_cv,
    get_interviews_for_candidate,
    get_receptionist_assessment,
    delete_candidate_by_actor,
    get_user_permissions,
)

from drive_and_cv_views import preview_cv_ui, download_cv_ui

EMAIL_RE = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.I)


def _valid_email(addr: str) -> bool:
    return bool(EMAIL_RE.match(addr or ""))


def _random_password(n: int = 12) -> str:
    chars = string.ascii_letters + string.digits + "!@#$%?"
    return "".join(secrets.choice(chars) for _ in range(n))


def _fetch_users():
    """
    Fetch all users along with the latest permissions and timestamps.
    (Used for the admin list + password audit.)
    """
    conn = get_conn()
    with conn, conn.cursor() as cur:
        cur.execute("""
            SELECT id, email, role,
                   can_view_cv, can_upload_cv, can_edit_cv, can_delete_candidate,
                   can_grant_delete, can_manage_users, can_add_candidates,
                   can_edit_candidates, can_view_all_candidates,
                   can_schedule_interviews, can_view_interview_feedback,
                   can_edit_interview_feedback, can_delete_interview_feedback,
                   can_view_reports, can_export_reports,
                   COALESCE(updated_at, created_at) AS last_changed,
                   created_at,
                   force_password_reset
            FROM users
            ORDER BY id
        """)
        rows = cur.fetchall()
    conn.close()

    return [
        {
            "id": r[0],
            "email": r[1],
            "role": r[2],
            "can_view_cv": r[3],
            "can_upload_cv": r[4],
            "can_edit_cv": r[5],
            "can_delete_candidate": r[6],
            "can_grant_delete": r[7],
            "can_manage_users": r[8],
            "can_add_candidates": r[9],
            "can_edit_candidates": r[10],
            "can_view_all_candidates": r[11],
            "can_schedule_interviews": r[12],
            "can_view_interview_feedback": r[13],
            "can_edit_interview_feedback": r[14],
            "can_delete_interview_feedback": r[15],
            "can_view_reports": r[16],
            "can_export_reports": r[17],
            "last_changed": r[18],
            "created_at": r[19],
            "force_password_reset": r[20],
        }
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


def _plot_candidate_charts(stats: dict):
    """Generate pie and bar charts for candidate stats."""
    if not stats:
        st.info("No statistics available to visualize.")
        return

    # Pie chart: resumes
    fig1, ax1 = plt.subplots()
    labels = ["With Resume", "Without Resume"]
    with_resume = stats.get("candidates_with_resume", 0)
    total = stats.get("total_candidates", 0)
    values = [with_resume, max(total - with_resume, 0)]
    ax1.pie(values, labels=labels, autopct="%1.1f%%", startangle=90)
    ax1.set_title("Resume Uploads")
    st.pyplot(fig1)

    # Bar chart: interview breakdown
    interview_breakdown = stats.get("interview_results", {})
    if interview_breakdown:
        fig2, ax2 = plt.subplots()
        colors = []
        for outcome in interview_breakdown.keys():
            o = (outcome or "").lower()
            if "pass" in o:
                colors.append("green")
            elif "fail" in o:
                colors.append("red")
            elif "hold" in o:
                colors.append("orange")
            elif "sched" in o:
                colors.append("blue")
            elif "complete" in o:
                colors.append("purple")
            else:
                colors.append("gray")
        ax2.bar(list(interview_breakdown.keys()), list(interview_breakdown.values()), color=colors)
        ax2.set_title("Interview Outcomes")
        ax2.set_ylabel("Count")
        ax2.tick_params(axis="x", rotation=20)
        st.pyplot(fig2)


def show_ceo_panel():
    st.header("CEO — Administration Panel")

    current_user = st.session_state.get("user")
    if not current_user:
        st.error("No active user session. Please log in.")
        return

    # -------------------------
    # STORAGE + STATS
    # -------------------------
    st.subheader("System Overview")
    colA, colB = st.columns(2)
    with colA:
        try:
            total_bytes = get_total_cv_storage_usage()
        except Exception as e:
            total_bytes = 0
            st.error(f"Error reading storage usage: {e}")

        st.metric("Total CV Storage Used", _human_bytes(total_bytes))
        if total_bytes:
            limit_mb = 500
            used_mb = total_bytes / (1024 * 1024)
            pct = min(100, int((used_mb / limit_mb) * 100)) if limit_mb else 0
            st.progress(pct)
            st.caption(f"Using ~{used_mb:.1f} MB of {limit_mb} MB soft limit")

    with colB:
        try:
            stats = get_candidate_statistics() or {}
        except Exception as e:
            stats = {}
            st.error(f"Error loading statistics: {e}")

        st.metric("Total Candidates", stats.get("total_candidates", 0))
        st.metric("With Resume", stats.get("candidates_with_resume", 0))
        st.metric("Interviews", stats.get("total_interviews", 0))

    st.markdown("---")
    st.subheader("📊 Advanced Candidate Statistics")
    if stats:
        _plot_candidate_charts(stats)
        with st.expander("Raw statistics (JSON)", expanded=False):
            st.json(stats)
    else:
        st.caption("No stats available.")

    # -------------------------
    # USER PERMISSIONS
    # -------------------------
    st.markdown("---")
    st.subheader("User Permissions Management")

    PERMISSION_FIELDS = [
        "can_view_cv",
        "can_upload_cv",
        "can_edit_cv",
        "can_delete_candidate",
        "can_grant_delete",
        "can_manage_users",
        "can_add_candidates",
        "can_edit_candidates",
        "can_view_all_candidates",
        "can_schedule_interviews",
        "can_view_interview_feedback",
        "can_edit_interview_feedback",
        "can_delete_interview_feedback",
        "can_view_reports",
        "can_export_reports",
    ]

    users = get_all_users_with_permissions()
    if not users:
        st.warning("No users found.")
    else:
        for user in users:
            with st.expander(f"🔹 {user['email']} ({user['role']})", expanded=False):
                st.write(f"**User ID:** {user['id']} | **Role:** {user['role']}")

                updated_perms = {}
                for field in PERMISSION_FIELDS:
                    updated_perms[field] = st.checkbox(
                        field.replace("_", " ").title(),
                        value=user.get(field, False),
                        key=f"{user['id']}_{field}"
                    )

                if st.button(f"💾 Save Permissions for {user['email']}", key=f"save_{user['id']}"):
                    try:
                        success = set_user_permission(user["id"], **updated_perms)
                    except Exception as e:
                        st.error(f"Failed to update permissions: {e}")
                        success = False
                    if success:
                        st.success("✅ Permissions updated successfully!")
                        st.rerun()
                    else:
                        st.error("❌ Failed to update permissions.")

    # -------------------------
    # ALL USERS (ADMIN)
    # -------------------------
    st.markdown("---")
    st.subheader("All Users")
    users = _fetch_users()
    for u in users:
        with st.expander(f"{u['email']}  ({u['role']})", expanded=False):
            st.write(f"**ID:** {u['id']}")
            st.write(f"**Last password change:** {u.get('last_changed', '—')}")
            st.write(f"**Force Password Reset:** {u.get('force_password_reset', False)}")

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
                try:
                    if _reset_password(u["id"], _random_password()):
                        ok += 1
                    else:
                        fail += 1
                except Exception:
                    fail += 1
            st.success(f"Done. Reset: {ok}, Failed: {fail}.")

    # Single-user forced password reset button (per-user control shown above)

    # -------------------------
    # CANDIDATE RECORDS + CV + INTERVIEWS
    # -------------------------
    st.markdown("---")
    st.subheader("Candidate Records")
    candidates = get_all_candidates()
    if not candidates:
        st.caption("No candidates found.")
    else:
        for c in candidates:
            with st.expander(f"{c.get('name','(unnamed)')} — {c.get('candidate_id','?')}", expanded=False):
                st.write(f"**Email:** {c.get('email','—')}")
                st.write(f"**Phone:** {c.get('phone','—')}")
                st.write(f"**Created At:** {c.get('created_at','—')}")
                if c.get("form_data"):
                    st.json(c["form_data"])

                # CV section
                st.markdown("#### Candidate CV")
                if current_user.get("can_view_cv", False):
                    try:
                        preview_cv_ui(c["candidate_id"])
                        download_cv_ui(c["candidate_id"])
                    except Exception as e:
                        st.error(f"Error fetching CV: {e}")
                else:
                    st.warning("🚫 You don't have permission to view CVs.")

                # Interview history section
                st.markdown("#### Interview History")
                try:
                    interviews = get_interviews_for_candidate(c["candidate_id"])
                    if not interviews:
                        st.caption("No interviews found for this candidate.")
                    else:
                        for iv in interviews:
                            st.write(f"**Scheduled At:** {iv.get('scheduled_at','—')}")
                            st.write(f"**Interviewer:** {iv.get('interviewer','—')}")
                            st.write(f"**Result:** {iv.get('result','—')}")
                            st.write(f"**Notes:** {iv.get('notes','—')}")
                            st.markdown("---")
                except Exception as e:
                    st.error(f"Error fetching interview history: {e}")

                # Receptionist Assessment
                st.markdown("#### Receptionist Assessment")
                try:
                    assessment = get_receptionist_assessment(c["candidate_id"])
                    if not assessment:
                        st.caption("No receptionist assessment found for this candidate.")
                    else:
                        st.write(f"**Speed Test (WPM):** {assessment.get('speed_test','—')}")
                        st.write(f"**Accuracy Test (%):** {assessment.get('accuracy_test','—')}")
                        st.write(f"**Work Commitment:** {assessment.get('work_commitment','—')}")
                        st.write(f"**English Understanding:** {assessment.get('english_understanding','—')}")
                        st.write(f"**Comments:** {assessment.get('comments','—')}")
                except Exception as e:
                    st.error(f"Error fetching receptionist assessment: {e}")

                # === Candidate Delete Action ===
                user_id = current_user.get("id")
                try:
                    user_perms = get_user_permissions(user_id) if user_id else {}
                except Exception:
                    user_perms = {}

                can_delete = bool(user_perms.get("can_delete_candidate")) or (user_perms.get("role") or "").lower() in ("ceo", "admin")

                st.markdown("#### Danger Zone")
                if can_delete:
                    confirm_key = f"confirm_delete_{c['candidate_id']}"
                    delete_key = f"delete_{c['candidate_id']}"

                    confirm_delete = st.checkbox(f"⚠️ Confirm Delete Candidate {c['candidate_id']}", key=confirm_key)
                    if confirm_delete:
                        if st.button(f"🗑️ Delete Candidate {c['candidate_id']}", key=delete_key):
                            try:
                                if delete_candidate_by_actor(c["candidate_id"], user_id):
                                    st.success(f"✅ Candidate {c['candidate_id']} deleted successfully.")
                                    st.rerun()
                                else:
                                    st.error("❌ You don't have permission or deletion failed.")
                            except Exception as e:
                                st.error(f"❌ Error deleting candidate: {e}")
                else:
                    st.info("🚫 You do not have permission to delete candidates.")

    st.markdown("---")
    st.caption("CEO can now view CVs, manage all permissions, audit passwords, and delete candidates (permission-aware).")
