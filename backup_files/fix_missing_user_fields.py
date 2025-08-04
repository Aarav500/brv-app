from google.cloud import firestore
from datetime import datetime

db = firestore.Client()
users_ref = db.collection("users")
users = users_ref.stream()

for doc in users:
    data = doc.to_dict()
    doc_id = doc.id
    updates = {}

    if "email" not in data:
        updates["email"] = doc_id

    if "username" not in data:
        updates["username"] = doc_id.split("@")[0]

    if "role" not in data:
        updates["role"] = "interviewer"

    if "force_password_reset" not in data:
        updates["force_password_reset"] = True  # Force reset

    if "last_password_change" not in data:
        updates["last_password_change"] = None

    if updates:
        print(f"Patching {doc_id}: {updates}")
        users_ref.document(doc_id).update(updates)

print("✅ User documents patched successfully.")