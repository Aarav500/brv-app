# test_resume_upload.py
import os
from db_postgres import (
    save_candidate_cv,
    get_candidate_cv,
    delete_candidate_cv,
    create_candidate_in_db,
)
import uuid

def main():
    # Step 1: create a dummy candidate
    candidate_id = str(uuid.uuid4())[:8].upper()
    print(f"🔹 Creating test candidate {candidate_id}")

    result = create_candidate_in_db(
        candidate_id=candidate_id,
        name="Test User",
        email="testuser@example.com",
        phone="1234567890",
        form_data={"test": "resume upload"},
        created_by="test_script",
    )
    if not result:
        print("❌ Failed to create candidate")
        return

    # Step 2: prepare a dummy CV file
    dummy_cv_path = "dummy_resume.txt"
    with open(dummy_cv_path, "w", encoding="utf-8") as f:
        f.write("This is a dummy resume file for testing.\n")

    with open(dummy_cv_path, "rb") as f:
        file_bytes = f.read()
        ok = save_candidate_cv(candidate_id, file_bytes, dummy_cv_path)

    if ok:
        print("✅ Resume uploaded successfully.")
    else:
        print("❌ Failed to upload resume.")
        return

    # Step 3: fetch resume back from DB
    file_bytes, filename = get_candidate_cv(candidate_id)
    if file_bytes:
        print(f"✅ Resume retrieved successfully: {filename}")
        # save it back to disk
        out_path = f"downloaded_{filename or 'resume.txt'}"
        with open(out_path, "wb") as f:
            f.write(file_bytes)
        print(f"📂 Resume saved locally as {out_path}")
    else:
        print("❌ Resume not found in DB.")

    # Step 4: delete resume
    ok = delete_candidate_cv(candidate_id)
    print("🗑️ Resume deleted." if ok else "❌ Failed to delete resume.")

if __name__ == "__main__":
    main()
