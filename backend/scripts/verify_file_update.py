import requests
import sys
import json

BASE_URL = "http://localhost:8000/api"

def login():
    print("Logging in as demo user...")
    response = requests.post(f"{BASE_URL}/auth/login", json={
        "email": "demo@qcanvas.dev",
        "password": "demo123"
    })
    if response.status_code == 200:
        print("✅ Login successful")
        return response.json()["access_token"]
    else:
        print(f"❌ Login failed: {response.text}")
        sys.exit(1)

def update_file(token, project_id, file_id):
    print(f"\nUpdating file {file_id} in project {project_id}...")
    headers = {"Authorization": f"Bearer {token}"}
    
    new_content = "import cirq\n\n# Updated content by verification script"
    data = {"content": new_content}
    
    url = f"{BASE_URL}/projects/{project_id}/files/{file_id}"
    print(f"PUT {url}")
    
    response = requests.put(url, json=data, headers=headers)
    
    if response.status_code == 200:
        print("✅ File update request successful")
        return new_content
    else:
        print(f"❌ File update failed: {response.status_code} - {response.text}")
        sys.exit(1)

def verify_content(token, project_id, file_id, expected_content):
    print(f"\nVerifying content for file {file_id}...")
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/projects/{project_id}", headers=headers)
    
    if response.status_code == 200:
        project = response.json()
        files = project.get('files', [])
        target_file = next((f for f in files if str(f['id']) == str(file_id)), None)
        
        if target_file:
            print(f"Current content found: {target_file['content'].strip()}")
            if target_file['content'] == expected_content:
                print("✅ Content verification passed!")
            else:
                print("❌ Content verification failed! Content mismatch.")
                print(f"Expected: {expected_content}")
                print(f"Got: {target_file['content']}")
        else:
            print("❌ File not found in project details")
    else:
        print(f"❌ Failed to get project details: {response.text}")

def main():
    try:
        token = login()
        # We assume project 1 and file 1 exist from previous steps
        # If not, this might fail, but let's try with known IDs from user output
        project_id = 1
        file_id = 1
        
        expected_content = update_file(token, project_id, file_id)
        verify_content(token, project_id, file_id, expected_content)
        
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to the backend. Is it running on port 8000?")

if __name__ == "__main__":
    main()
