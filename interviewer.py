# interviewer.py
import streamlit as st
from database import SessionLocal
from models import Candidate, Interview, User
from datetime import datetime

def interviewer_view():
    st.header("Interviewer Dashboard")
    db = SessionLocal()
    try:
        st.subheader("Upcoming / All Candidates")
        q = st.text_input("Search by name/email")
        query = db.query(Candidate)
        if q:
            query = query.filter((Candidate.name.ilike(f"%{q}%")) | (Candidate.email.ilike(f"%{q}%")))
        results = query.order_by(Candidate.updated_at.desc()).limit(50).all()
        for c in results:
            with st.expander(f"{c.id} — {c.name}"):
                st.write("Email:", c.email)
                st.write("Phone:", c.phone)
                st.write("Skills:", (c.form_data or {}).get("skills", ""))
                st.write("Resume:", c.resume_url or "No resume")
                st.markdown("**Interview**")
                scheduled = st.date_input("Schedule date", key=f"date_{c.id}")
                notes = st.text_area("Notes", key=f"notes_{c.id}")
                result = st.selectbox("Result", ["", "pass", "fail", "on_hold"], key=f"result_{c.id}")
                if st.button("Save interview", key=f"save_int_{c.id}"):
                    interview = Interview(
                        candidate_id=c.id,
                        scheduled_at=datetime.combine(scheduled, datetime.min.time()),
                        interviewer=None,
                        result=result or None,
                        notes=notes
                    )
                    db.add(interview); db.commit()
                    st.success("Interview saved")
    finally:
        db.close()
