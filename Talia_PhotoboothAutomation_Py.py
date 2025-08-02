import os
import pickle
import time
import json
from pathlib import Path
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileCreatedEvent, FileSystemEventHandler

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# 1. AUTH CONFIG
SCOPES = ['https://www.googleapis.com/auth/drive.file']
TOKEN_FILE = 'token.json'
CREDENTIALS_FILE = 'client_secret_talia_photobooth.json'


def get_drive_service():
    creds = None
    if os.path.exists(TOKEN_FILE) and os.path.getsize(TOKEN_FILE) > 0:
        try:
            with open(TOKEN_FILE, 'rb') as t:
                creds = pickle.load(t)
        except (EOFError, pickle.UnpicklingError):
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'wb') as f:
            pickle.dump(creds, f)

    return build('drive', 'v3', credentials=creds)


# 2. UPLOAD FUNCTION
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
        if response:
            file_id = response.get('id')
    print(f"✅ Uploaded {file_name} (ID: {file_id})")
    return file_id


# 3. FILE EVENT HANDLER
class PhotoHandler(FileSystemEventHandler):
    def __init__(self, service, log_path, folder_id=None):
        super().__init__()
        self.service = service
        self.log_path = Path(log_path)
        self.folder_id = folder_id
        self.uploaded = self._load_uploaded()

    def _load_uploaded(self):
        if self.log_path.exists():
            try:
                return set(json.loads(self.log_path.read_text()))
            except json.JSONDecodeError:
                return set()
        return set()

    def _save_uploaded(self):
        self.log_path.write_text(json.dumps(list(self.uploaded)))

    def on_created(self, event):
        if not isinstance(event, FileCreatedEvent) or event.is_directory:
            return

        filepath = Path(event.src_path)
        if filepath.suffix.lower() not in {'.jpg', '.jpeg', '.png'}:
            return

        # Wait for file to finish writing
        for _ in range(10):
            try:
                prev_size = filepath.stat().st_size
                time.sleep(0.5)
                curr_size = filepath.stat().st_size
                if curr_size == prev_size:
                    break
            except FileNotFoundError:
                time.sleep(0.5)
        else:
            print(f"⚠️ File not stable or missing: {filepath.name}")
            return

        if filepath.name in self.uploaded:
            print(f"— Already uploaded: {filepath.name}")
            return

        try:
            upload_file(self.service, str(filepath), drive_folder_id=self.folder_id)
            self.uploaded.add(filepath.name)
            self._save_uploaded()
        except Exception as e:
            print(f"❌ Error uploading {filepath.name}: {e}")


# 4. MAIN WATCHER
def main(watch_dir, track_log, drive_folder_id=None):
    service = get_drive_service()
    handler = PhotoHandler(service, track_log, drive_folder_id)
    observer = PollingObserver()
    observer.schedule(handler, path=watch_dir, recursive=False)
    observer.start()
    print(f"▶️ Watching {watch_dir} for new images to upload...")

    try:
        while observer.is_alive():
            observer.join(1)
    except KeyboardInterrupt:
        print("🛑 Stopping watcher…")
        observer.stop()
    observer.join()


# 5. CONFIG & EXECUTION
if __name__ == '__main__':
    WATCH_FOLDER = r"C:\Users\satri\Pictures\Internet"
    UPLOAD_LOG = 'uploaded_photos.json'
    DRIVE_FOLDER_ID = '1XSXxYx5EbwSPYP0EkqhlQvRIhHIjFbDU'  # Just the ID part!
    main(WATCH_FOLDER, UPLOAD_LOG, DRIVE_FOLDER_ID)
