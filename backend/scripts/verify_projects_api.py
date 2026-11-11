import requests
import sys

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

def create_project(token):
    print("\nCreating test project...")
    headers = {"Authorization": f"Bearer {token}"}
    data = {
        "name": "Integration Test Project",
        "description": "Created by verification script",
        "is_public": False
    }
    response = requests.post(f"{BASE_URL}/projects/", json=data, headers=headers)
    if response.status_code == 201:
        project = response.json()
        print(f"✅ Project created: {project['id']} - {project['name']}")
        return project['id']
    else:
        print(f"❌ Project creation failed: {response.text}")
        sys.exit(1)

def add_file(token, project_id):
    print("\nAdding file to project...")
    headers = {"Authorization": f"Bearer {token}"}
    data = {
        "filename": "quantum_circuit.py",
        "content": "import cirq\n\n# Test circuit",
        "is_main": True
    }
    response = requests.post(f"{BASE_URL}/projects/{project_id}/files", json=data, headers=headers)
    if response.status_code == 201:
        file_obj = response.json()
        print(f"✅ File added: {file_obj['id']} - {file_obj['filename']}")
        return file_obj
    else:
        print(f"❌ File addition failed: {response.text}")
        sys.exit(1)

def get_project_details(token, project_id):
    print("\nVerifying project details...")
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/projects/{project_id}", headers=headers)
    if response.status_code == 200:
        project = response.json()
        print(f"✅ Project retrieved successfully")
        print(f"   Files count: {len(project.get('files', []))}")
        for f in project.get('files', []):
            print(f"   - {f['filename']} (Main: {f['is_main']})")
    else:
        print(f"❌ Failed to get project details: {response.text}")

def main():
    try:
        token = login()
        project_id = create_project(token)
        add_file(token, project_id)
        get_project_details(token, project_id)
        print("\n🎉 Verification Completed Successfully!")
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to the backend. Is it running on port 8000?")

if __name__ == "__main__":
    main()
