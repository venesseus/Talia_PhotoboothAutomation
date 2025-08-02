import os
import requests
import base64

# Your ImgBB API key (get it from https://api.imgbb.com/)
API_KEY = "c56a409c4139a48a4c6c649816f94109"

# Folder containing your images
FOLDER_PATH = r"./test_images"

def upload_to_imgbb(file_path):
    with open(file_path, "rb") as file:
        encoded_image = base64.b64encode(file.read())
    
    url = API_KEY
    payload = {
        "key": 'c56a409c4139a48a4c6c649816f94109',
        "image": encoded_image
    }
    
    response = requests.post(url, data=payload)
    if response.status_code == 200:
        data = response.json()
        return data["data"]["url"]
    else:
        print(f"Failed to upload {file_path}. Error:", response.text)
        return None

if __name__ == "__main__":
    for filename in os.listdir(FOLDER_PATH):
        if filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp")):
            file_path = os.path.join(FOLDER_PATH, filename)
            print(f"Uploading: {filename}")
            link = upload_to_imgbb(file_path)
            if link:
                print(f"Uploaded successfully: {link}")
