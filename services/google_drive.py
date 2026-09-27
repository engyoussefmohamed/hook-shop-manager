import os
import json
from datetime import datetime

from config import APP_DIR

TOKEN_FILE  = os.path.join(APP_DIR, "google_token.json")
CREDS_FILE  = os.path.join(APP_DIR, "google_credentials.json")
SCOPES      = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]

def _has_custom_creds():
    if not os.path.exists(CREDS_FILE):
        return False
    try:
        with open(CREDS_FILE) as f:
            data = json.load(f)
        cid  = (data.get("installed") or data.get("web") or {}).get("client_id", "")
        return bool(cid) and cid != "YOUR_CLIENT_ID"
    except Exception:
        return False


def get_credentials():
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request

        if not os.path.exists(TOKEN_FILE):
            return None
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            _save_token(creds)
        return creds if creds and creds.valid else None
    except Exception:
        return None


def _save_token(creds):
    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())


def start_auth_flow(redirect_uri):
    from google_auth_oauthlib.flow import Flow

    if not _has_custom_creds():
        return None, "يرجى إعداد ملف google_credentials.json أولاً (راجع التعليمات)"

    flow = Flow.from_client_secrets_file(
        CREDS_FILE, scopes=SCOPES, redirect_uri=redirect_uri
    )
    url, state = flow.authorization_url(
        access_type="offline", prompt="select_account"
    )
    return url, state


def finish_auth_flow(code, redirect_uri):
    try:
        from google_auth_oauthlib.flow import Flow
        flow = Flow.from_client_secrets_file(
            CREDS_FILE, scopes=SCOPES, redirect_uri=redirect_uri
        )
        flow.fetch_token(code=code)
        creds = flow.credentials
        _save_token(creds)
        email = _get_email(creds)
        return email, None
    except Exception as e:
        return None, str(e)


def _get_email(creds):
    try:
        from googleapiclient.discovery import build
        svc  = build("oauth2", "v2", credentials=creds)
        info = svc.userinfo().get().execute()
        return info.get("email", "")
    except Exception:
        return ""


def get_connected_email():
    try:
        creds = get_credentials()
        if not creds:
            return None
        return _get_email(creds)
    except Exception:
        return None


def disconnect():
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)


def backup_to_drive(db_path):
    creds = get_credentials()
    if not creds:
        return False, "لم يتم ربط حساب جوجل"

    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        svc       = build("drive", "v3", credentials=creds)
        folder_id = _get_or_create_folder(svc, "shop_backup")

        filename = f"shop_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        media    = MediaFileUpload(
            db_path, mimetype="application/x-sqlite3", resumable=True
        )
        svc.files().create(
            body={"name": filename, "parents": [folder_id]},
            media_body=media,
            fields="id",
        ).execute()

        _cleanup(svc, folder_id)
        return True, f"تم الرفع إلى Drive: {filename}"
    except Exception as e:
        return False, str(e)


def _get_or_create_folder(svc, name):
    res = svc.files().list(
        q=f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id)",
    ).execute()
    files = res.get("files", [])
    if files:
        return files[0]["id"]
    folder = svc.files().create(
        body={"name": name, "mimeType": "application/vnd.google-apps.folder"},
        fields="id",
    ).execute()
    return folder["id"]


def _cleanup(svc, folder_id, keep=30):
    res = svc.files().list(
        q=f"'{folder_id}' in parents and trashed=false",
        orderBy="createdTime desc",
        fields="files(id)",
    ).execute()
    for f in res.get("files", [])[keep:]:
        try:
            svc.files().delete(fileId=f["id"]).execute()
        except Exception:
            pass
