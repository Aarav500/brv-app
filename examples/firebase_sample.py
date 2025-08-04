"""
Firebase Sample Script

This script demonstrates how to use Firebase Firestore with Python.
It includes examples of:
1. Initializing Firebase
2. Adding or updating a document
3. Reading from Firestore
4. Querying documents
5. Deleting documents
"""

import firebase_admin
from firebase_admin import credentials, firestore
import os
from datetime import datetime

def initialize_firebase():
    """Initialize Firebase with service account credentials"""
    print("Step 1: Initializing Firebase...")
    
    try:
        # Check if Firebase is already initialized
        firebase_admin.get_app()
        print("Firebase already initialized")
    except ValueError:
        # Initialize Firebase with service account credentials
        cred = credentials.Certificate("google_key.json")
        firebase_admin.initialize_app(cred)
        print("Firebase initialized successfully")
    
    # Get Firestore client
    db = firestore.client()
    print("Firestore client created")
    
    return db

def add_document(db):
    """Add a document to Firestore"""
    print("\nStep 2: Adding a document...")
    
    # Create a reference to the users collection
    users_ref = db.collection("users")
    
    # User data
    user_data = {
        "name": "John Doe",
        "email": "john.doe@example.com",
        "role": "user",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # Add the document with auto-generated ID
    doc_ref = users_ref.add(user_data)
    print(f"Document added with ID: {doc_ref[1].id}")
    
    return doc_ref[1].id

def update_document(db, doc_id):
    """Update a document in Firestore"""
    print(f"\nStep 3: Updating document {doc_id}...")
    
    # Get a reference to the document
    doc_ref = db.collection("users").document(doc_id)
    
    # Update the document
    doc_ref.update({
        "role": "admin",
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    print("Document updated successfully")

def read_document(db, doc_id):
    """Read a document from Firestore"""
    print(f"\nStep 4: Reading document {doc_id}...")
    
    # Get a reference to the document
    doc_ref = db.collection("users").document(doc_id)
    
    # Get the document
    doc = doc_ref.get()
    
    if doc.exists:
        print("Document data:")
        print(doc.to_dict())
    else:
        print("No such document!")

def query_documents(db):
    """Query documents in Firestore"""
    print("\nStep 5: Querying documents...")
    
    # Create a reference to the users collection
    users_ref = db.collection("users")
    
    # Query for all admin users
    query = users_ref.where("role", "==", "admin")
    
    # Execute the query
    results = query.stream()
    
    # Print the results
    print("Admin users:")
    for doc in results:
        print(f"{doc.id} => {doc.to_dict()}")

def delete_document(db, doc_id):
    """Delete a document from Firestore"""
    print(f"\nStep 6: Deleting document {doc_id}...")
    
    # Get a reference to the document
    doc_ref = db.collection("users").document(doc_id)
    
    # Delete the document
    doc_ref.delete()
    
    print("Document deleted successfully")

def main():
    """Main function to run the demo"""
    print("Firebase Sample Script")
    print("=====================")
    
    # Step 1: Initialize Firebase
    db = initialize_firebase()
    
    # Step 2: Add a document
    doc_id = add_document(db)
    
    # Step 3: Update the document
    update_document(db, doc_id)
    
    # Step 4: Read the document
    read_document(db, doc_id)
    
    # Step 5: Query documents
    query_documents(db)
    
    # Step 6: Delete the document
    delete_document(db, doc_id)
    
    print("\nDemo completed successfully!")

if __name__ == "__main__":
    main()