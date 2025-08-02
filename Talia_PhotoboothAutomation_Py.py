import os
import time
import json
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileCreatedEvent, FileSystemEventHandler

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# 1. DRIVE AUTHENTICATION
SCOPES = ['https://www.googleapis.com/auth/drive.file'] #ini maksudnya scope apa ya?
TOKEN_FILE = 'token.json'
CREDENTIALS_FILE = 'credentials.json'


def get_drive_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        import pickle
        with open(TOKEN_FILE, 'rb') as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'wb') as f:
            pickle.dump(creds, f)
    return build('drive', 'v3', credentials=creds)


# 2. UPLOAD FILE FUNCTION
def upload_file(service, filepath, drive_folder_id=None):
    file_name = Path(filepath).name
    metadata = {'name': file_name}
    if drive_folder_id:
        metadata['parents'] = [drive_folder_id]
    media = MediaFileUpload(filepath, mimetype='image/jpeg', resumable=True)
    request = service.files().create(body=metadata, media_body=media, fields='id')
    file_id = None
    while file_id is None:
        status, response = request.next_chunk()
        if status:
            print(f"Uploading {file_name}: {int(status.progress() * 100)}%")
    file_id = response.get('id')
    print(f"✅ Uploaded {file_name} (ID: {file_id})")
    return file_id


# 3. WATCHDOG HANDLER
class PhotoHandler(FileSystemEventHandler):
    def __init__(self, service, log_path, folder_id=None):
        super().__init__()
        self.service = service
        self.log_path = Path(log_path)
        self.forder_id = folder_id
        self.uploaded = self._load_uploaded()

    def _load_uploaded(self):
        if self.log_path.exists():
            return set(json.loads(self.log_path.read_text()))
        return set()

    def _save_uploaded(self):
        self.log_path.write_text(json.dumps(list(self.uploaded)))

    def on_created(self, event):
        if not isinstance(event, FileCreatedEvent) or event.is_directory:
            return
        filepath = Path(event.src_path)
        if filepath.suffix.lower() not in {'.jpg', '.jpeg', '.png'}:
            return

        # WAIT for file to finish writing
        prev_size = -1
        for _ in range(20):
            curr_size = filepath.stat().st_size
            if curr_size == prev_size:
                break
            prev_size = curr_size
            time.sleep(0.5)
        else:
            print(f"⚠️ Timeout waiting for {filepath.name}")

        if filepath.name in self.uploaded:
            print(f"— Already uploaded: {filepath.name}")
            return

        try:
            upload_file(self.service, str(filepath), drive_folder_id=self.forder_id)
            self.uploaded.add(filepath.name)
            self._save_uploaded()
        except Exception as e:
            print(f"❌ Error uploading {filepath.name}: {e}")


def main(watch_dir, track_log, drive_folder_id=None):
    service = get_drive_service()
    handler = PhotoHandler(service, track_log, drive_folder_id)
    observer = Observer()
    observer.schedule(handler, path=watch_dir, recursive=False)
    observer.start()
    print(f"▶️ Watching {watch_dir} for new images to upload...")

    try:
        while observer.is_alive():
            observer.join(1)
    except KeyboardInterrupt:
        print("Stopping watcher…")
        observer.stop()
    observer.join()


if __name__ == '__main__':
    WATCH_FOLDER = '/path/to/DCIM/Camera'   # adjust this path
    UPLOAD_LOG = 'uploaded_photos.json'
    DRIVE_FOLDER_ID = 'https://drive.google.com/drive/folders/1XSXxYx5EbwSPYP0EkqhlQvRIhHIjFbDU?usp=sharing'  # ini masukin folder id dimananya gdrive ya?
    main(WATCH_FOLDER, UPLOAD_LOG, DRIVE_FOLDER_ID)
