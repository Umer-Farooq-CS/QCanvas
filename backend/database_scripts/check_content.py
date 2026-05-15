import requests
import sys
import json

BASE_URL = "http://localhost:8000/api"

def login():
    response = requests.post(f"{BASE_URL}/auth/login", json={
        "email": "demo@qcanvas.dev",
        "password": "demo123"
    })
    if response.status_code == 200:
        return response.json()["access_token"]
    sys.exit(1)

def check_content(token, project_id, file_id):
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/projects/{project_id}", headers=headers)
    
    if response.status_code == 200:
        project = response.json()
        files = project.get('files', [])
        target_file = next((f for f in files if str(f['id']) == str(file_id)), None)
        
        if target_file:
            print(f"CONTENT_START\n{target_file['content']}\nCONTENT_END")
            if "# Test Save" in target_file['content']:
                print("✅ Found '# Test Save' in database!")
            else:
                print("❌ '# Test Save' NOT found in database.")
        else:
            print("File not found")

if __name__ == "__main__":
    token = login()
    check_content(token, 1, 1)
