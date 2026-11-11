"""
Test authentication endpoints.
Make sure the backend server is running first: python backend/start.py
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_auth():
    print("=" * 60)
    print("Testing QCanvas Authentication Endpoints")
    print("=" * 60)
    print()
    
    # Test 1: Register a new user
    print("1. Testing Registration...")
    register_data = {
        "email": "testuser@qcanvas.dev",
        "username": "testuser",
        "password": "TestPass123!",
        "full_name": "Test User"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/auth/register", json=register_data)
        print(f"   Status: {response.status_code}")
        if response.status_code == 201:
            data = response.json()
            print("   ✅ Registration successful!")
            print(f"   User ID: {data['user']['id']}")
            print(f"   Email: {data['user']['email']}")
            print(f"   Token: {data['access_token'][:50]}...")
            access_token = data['access_token']
        else:
            print(f"   ❌ Registration failed: {response.json()}")
            # If user already exists, try logging in
            print("\n   Trying to login instead...")
            login_data = {
                "email": register_data["email"],
                "password": register_data["password"]
            }
            response = requests.post(f"{BASE_URL}/api/auth/login", json=login_data)
            if response.status_code == 200:
                data = response.json()
                print("   ✅ Login successful!")
                access_token = data['access_token']
            else:
                print(f"   ❌ Login also failed: {response.json()}")
                return
    except requests.exceptions.ConnectionError:
        print("   ❌ Could not connect to server!")
        print("   Make sure the backend is running: python backend/start.py")
        return
    
    print()
    
    # Test 2: Get current user
    print("2. Testing Get Current User...")
    headers = {"Authorization": f"Bearer {access_token}"}
    
    response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        user = response.json()
        print("   ✅ Got current user!")
        print(f"   Username: {user['username']}")
        print(f"   Email: {user['email']}")
        print(f"   Role: {user['role']}")
    else:
        print(f"   ❌ Failed: {response.json()}")
    
    print()
    
    # Test 3: Test invalid token
    print("3. Testing Invalid Token...")
    invalid_headers = {"Authorization": "Bearer invalid_token_12345"}
    
    response = requests.get(f"{BASE_URL}/api/auth/me", headers=invalid_headers)
    print(f"   Status: {response.status_code}")
    if response.status_code == 401:
        print("   ✅ Correctly rejected invalid token!")
    else:
        print(f"   ❌ Unexpected response: {response.json()}")
    
    print()
    
    # Test 4: Login with existing user
    print("4. Testing Login...")
    login_data = {
        "email": "admin@qcanvas.dev",
        "password": "SecurePass123!"
    }
    
    response = requests.post(f"{BASE_URL}/api/auth/login", json=login_data)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print("   ✅ Login successful!")
        print(f"   Username: {data['user']['username']}")
        print(f"   Last Login: {data['user']['last_login_at']}")
    else:
        print(f"   ❌ Login failed: {response.json()}")
    
    print()
    print("=" * 60)
    print("✅ Authentication tests completed!")
    print("=" * 60)

if __name__ == "__main__":
    test_auth()
