# google_drive.py
import os
import io
import traceback
from datetime import datetime
from dotenv import load_dotenv
import streamlit as st

# Google Drive imports
try:
    from oauth2client.service_account import ServiceAccountCredentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload

    GOOGLE_IMPORTS_AVAILABLE = True
except ImportError:
    GOOGLE_IMPORTS_AVAILABLE = False

load_dotenv()

# Configuration
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")


def check_google_drive_config():
    """Check if Google Drive is properly configured"""
    if not GOOGLE_IMPORTS_AVAILABLE:
        return False, "Google API libraries not installed. Run: pip install google-api-python-client oauth2client"

    if not GOOGLE_SERVICE_ACCOUNT_FILE:
        return False, "GOOGLE_SERVICE_ACCOUNT_FILE environment variable not set"

    if not os.path.exists(GOOGLE_SERVICE_ACCOUNT_FILE):
        return False, f"Service account file not found: {GOOGLE_SERVICE_ACCOUNT_FILE}"

    return True, "Google Drive configuration OK"


def get_drive_service():
    """Return an authenticated Drive v3 service for the service account JSON path."""
    is_ok, message = check_google_drive_config()
    if not is_ok:
        raise RuntimeError(message)

    scopes = ['https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SERVICE_ACCOUNT_FILE, scopes)
    service = build('drive', 'v3', credentials=creds, cache_discovery=False)
    return service


def ensure_drive_folder(folder_name="BRV_CVs"):
    """
    Ensure a folder exists in Drive. If GOOGLE_DRIVE_FOLDER_ID is set in env, use it.
    Otherwise search for a folder with the name under the service account drive and create it if missing.
    Returns folder_id.
    """
    global GOOGLE_DRIVE_FOLDER_ID
    if GOOGLE_DRIVE_FOLDER_ID:
        return GOOGLE_DRIVE_FOLDER_ID

    svc = get_drive_service()
    # try to find an existing folder
    q = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    try:
        resp = svc.files().list(q=q, spaces='drive', fields='files(id,name)', pageSize=10).execute()
        files = resp.get('files', [])
        if files:
            GOOGLE_DRIVE_FOLDER_ID = files[0]['id']
            print("Using existing Drive folder id:", GOOGLE_DRIVE_FOLDER_ID)
            return GOOGLE_DRIVE_FOLDER_ID

        # create folder
        metadata = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder"}
        newf = svc.files().create(body=metadata, fields='id').execute()
        GOOGLE_DRIVE_FOLDER_ID = newf.get('id')
        print("Created Drive folder id:", GOOGLE_DRIVE_FOLDER_ID)
        return GOOGLE_DRIVE_FOLDER_ID
    except Exception as e:
        print("Error ensuring Drive folder:", e)
        traceback.print_exc()
        raise


def upload_resume_to_drive(candidate_id: str, file_bytes: bytes, filename: str):
    """
    Upload file bytes to Drive into the configured folder.
    Returns (True, webViewLink, message) or (False, None, error_message)
    """
    try:
        # Check configuration
        is_ok, message = check_google_drive_config()
        if not is_ok:
            return False, None, f"Google Drive not configured: {message}"

        svc = get_drive_service()
        folder_id = ensure_drive_folder()

        # Build a unique name to avoid collisions
        timestamp = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        safe_name = f"{candidate_id}_{timestamp}_{filename}"

        # Determine MIME type based on file extension
        file_ext = os.path.splitext(filename)[1].lower()
        mime_type = "application/pdf"  # default
        if file_ext == ".doc":
            mime_type = "application/msword"
        elif file_ext == ".docx":
            mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif file_ext == ".pdf":
            mime_type = "application/pdf"

        # Upload file
        fh = io.BytesIO(file_bytes)
        media = MediaIoBaseUpload(fh, mimetype=mime_type, resumable=False)
        metadata = {
            'name': safe_name,
            'parents': [folder_id],
        }

        file = svc.files().create(
            body=metadata,
            media_body=media,
            fields='id,webViewLink,webContentLink'
        ).execute()

        file_id = file.get('id')

        # Make file readable by anyone with the link (optional security setting)
        svc.permissions().create(
            fileId=file_id,
            body={"role": "reader", "type": "anyone"}
        ).execute()

        webview = file.get('webViewLink') or f"https://drive.google.com/file/d/{file_id}/view"

        return True, webview, "Successfully uploaded to Google Drive"

    except Exception as e:
        print("Drive upload error:", e)
        traceback.print_exc()
        return False, None, str(e)


def download_resume_bytes_from_drive(file_id: str):
    """Download file bytes from Google Drive"""
    try:
        svc = get_drive_service()
        request = svc.files().get_media(fileId=file_id)
        fh = io.BytesIO()

        from googleapiclient.http import MediaIoBaseDownload
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()

        fh.seek(0)
        return fh.read()

    except Exception as e:
        print("Download error:", e)
        traceback.print_exc()
        return None


def extract_drive_file_id_from_link(link: str):
    """
    Extract file ID from various Google Drive link formats
    """
    if not link:
        return None

    try:
        if "drive.google.com" in link:
            # Format: https://drive.google.com/file/d/<id>/view?usp=sharing
            if "/d/" in link:
                parts = link.split("/d/")
                after = parts[1]
                file_id = after.split("/")[0]
                return file_id
            # Format: https://drive.google.com/open?id=<id>
            if "id=" in link:
                parts = link.split("id=")
                return parts[1].split("&")[0]
    except Exception:
        pass

    return None


def test_google_drive_connection():
    """Test Google Drive connection and return status"""
    try:
        is_ok, message = check_google_drive_config()
        if not is_ok:
            return False, message

        svc = get_drive_service()

        # Test by listing files in the root (limited)
        result = svc.files().list(pageSize=1, fields="files(id, name)").execute()

        # Try to ensure folder exists
        folder_id = ensure_drive_folder()

        return True, f"Google Drive connection successful. Folder ID: {folder_id}"

    except Exception as e:
        return False, f"Google Drive connection failed: {str(e)}"


def get_drive_usage_info():
    """Get Google Drive usage information"""
    try:
        svc = get_drive_service()
        about = svc.about().get(fields="storageQuota").execute()
        quota = about.get('storageQuota', {})

        limit = int(quota.get('limit', 0))
        usage = int(quota.get('usage', 0))

        if limit > 0:
            usage_percent = (usage / limit) * 100
            return {
                'limit_gb': round(limit / (1024 ** 3), 2),
                'used_gb': round(usage / (1024 ** 3), 2),
                'usage_percent': round(usage_percent, 1)
            }
        else:
            return {
                'limit_gb': 'Unlimited',
                'used_gb': round(usage / (1024 ** 3), 2),
                'usage_percent': 0
            }

    except Exception as e:
        print(f"Error getting drive usage: {e}")
        return None


# Streamlit UI components for Google Drive management
def show_drive_config_status():
    """Show Google Drive configuration status in Streamlit"""
    st.subheader("🔧 Google Drive Configuration")

    is_ok, message = check_google_drive_config()

    if is_ok:
        st.success(f"✅ {message}")

        # Test connection
        if st.button("Test Drive Connection"):
            with st.spinner("Testing connection..."):
                test_ok, test_message = test_google_drive_connection()
                if test_ok:
                    st.success(f"✅ {test_message}")

                    # Show usage info
                    usage_info = get_drive_usage_info()
                    if usage_info:
                        st.info(
                            f"📊 Drive Usage: {usage_info['used_gb']} GB used of {usage_info['limit_gb']} GB ({usage_info['usage_percent']}% used)")
                else:
                    st.error(f"❌ {test_message}")
    else:
        st.error(f"❌ {message}")

        # Show setup instructions
        with st.expander("📖 Setup Instructions"):
            st.markdown("""
            **To configure Google Drive integration:**

            1. **Create a Google Cloud Project:**
               - Go to [Google Cloud Console](https://console.cloud.google.com/)
               - Create a new project or select existing one

            2. **Enable Google Drive API:**
               - Go to APIs & Services > Library
               - Search for "Google Drive API" and enable it

            3. **Create Service Account:**
               - Go to APIs & Services > Credentials
               - Click "Create Credentials" > "Service Account"
               - Download the JSON key file

            4. **Set Environment Variables:**
               ```
               GOOGLE_SERVICE_ACCOUNT_FILE=/path/to/service-account.json
               GOOGLE_DRIVE_FOLDER_ID=optional-folder-id
               ```

            5. **Share Drive Folder (Optional):**
               - Create a folder in Google Drive
               - Share it with the service account email
               - Copy the folder ID from the URL
            """)


def local_file_fallback(candidate_id: str, file_bytes: bytes, filename: str):
    """
    Fallback function to save files locally when Google Drive is not available
    """
    try:
        # Create local storage directory
        storage_dir = os.path.join(os.getcwd(), "local_storage", "resumes")
        os.makedirs(storage_dir, exist_ok=True)

        # Create unique filename
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        safe_filename = f"{candidate_id}_{timestamp}_{filename}"
        file_path = os.path.join(storage_dir, safe_filename)

        # Save file
        with open(file_path, 'wb') as f:
            f.write(file_bytes)

        # Return local file path as "link"
        return True, f"file://{os.path.abspath(file_path)}", "Saved locally (Google Drive not configured)"

    except Exception as e:
        return False, None, f"Local storage failed: {str(e)}"


def smart_resume_upload(candidate_id: str, file_bytes: bytes, filename: str):
    """
    Smart resume upload that tries Google Drive first, falls back to local storage
    """
    # Try Google Drive first
    is_configured, _ = check_google_drive_config()

    if is_configured:
        success, link, message = upload_resume_to_drive(candidate_id, file_bytes, filename)
        if success:
            return success, link, message
        else:
            st.warning(f"Google Drive upload failed: {message}")
            st.info("Trying local storage fallback...")

    # Fallback to local storage
    return local_file_fallback(candidate_id, file_bytes, filename)