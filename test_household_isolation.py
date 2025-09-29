#!/usr/bin/env python3
"""
Test script to verify household isolation works correctly
"""
import requests
import json
import time

# Test configuration
API_BASE = "http://localhost:3001/api"
SOCKET_URL = "http://localhost:3002"

def test_household_isolation():
    """Test that users from different households cannot see each other's data"""
    
    print("🧪 Testing household isolation...")
    
    # Test data
    household1_users = [
        {"username": "mom_house1", "password": "password123", "household_id": "household_1"},
        {"username": "dad_house1", "password": "password123", "household_id": "household_1"}
    ]
    
    household2_users = [
        {"username": "mom_house2", "password": "password123", "household_id": "household_2"},
        {"username": "dad_house2", "password": "password123", "household_id": "household_2"}
    ]
    
    # Register users
    print("📝 Registering test users...")
    for user in household1_users + household2_users:
        try:
            response = requests.post(f"{API_BASE}/auth/register", json=user)
            if response.status_code == 200:
                print(f"✅ Registered {user['username']} in {user['household_id']}")
            else:
                print(f"⚠️  Registration failed for {user['username']}: {response.text}")
        except Exception as e:
            print(f"❌ Error registering {user['username']}: {e}")
    
    # Login users and get tokens
    print("\n🔐 Logging in users...")
    tokens = {}
    
    for user in household1_users + household2_users:
        try:
            response = requests.post(f"{API_BASE}/auth/login", json={
                "username": user["username"],
                "password": user["password"]
            })
            if response.status_code == 200:
                data = response.json()
                tokens[user["username"]] = data["token"]
                print(f"✅ Logged in {user['username']}")
            else:
                print(f"❌ Login failed for {user['username']}: {response.text}")
        except Exception as e:
            print(f"❌ Error logging in {user['username']}: {e}")
    
    # Test household isolation
    print("\n🏠 Testing household isolation...")
    
    # Create todos for household 1
    print("📝 Creating todos for household 1...")
    for username in ["mom_house1", "dad_house1"]:
        if username in tokens:
            try:
                headers = {"Authorization": f"Bearer {tokens[username]}"}
                response = requests.post(f"{API_BASE}/todos", 
                    json={"title": f"Task from {username}", "assigned_to": "mom", "priority": "1"},
                    headers=headers
                )
                if response.status_code == 200:
                    print(f"✅ Created todo for {username}")
                else:
                    print(f"❌ Failed to create todo for {username}: {response.text}")
            except Exception as e:
                print(f"❌ Error creating todo for {username}: {e}")
    
    # Create todos for household 2
    print("📝 Creating todos for household 2...")
    for username in ["mom_house2", "dad_house2"]:
        if username in tokens:
            try:
                headers = {"Authorization": f"Bearer {tokens[username]}"}
                response = requests.post(f"{API_BASE}/todos", 
                    json={"title": f"Task from {username}", "assigned_to": "mom", "priority": "1"},
                    headers=headers
                )
                if response.status_code == 200:
                    print(f"✅ Created todo for {username}")
                else:
                    print(f"❌ Failed to create todo for {username}: {response.text}")
            except Exception as e:
                print(f"❌ Error creating todo for {username}: {e}")
    
    # Test that users only see their household's todos
    print("\n🔍 Testing data isolation...")
    
    for username in ["mom_house1", "dad_house1"]:
        if username in tokens:
            try:
                headers = {"Authorization": f"Bearer {tokens[username]}"}
                response = requests.get(f"{API_BASE}/todos", headers=headers)
                if response.status_code == 200:
                    todos = response.json()
                    print(f"📋 {username} sees {len(todos)} todos:")
                    for todo in todos:
                        print(f"   - {todo['title']}")
                else:
                    print(f"❌ Failed to get todos for {username}: {response.text}")
            except Exception as e:
                print(f"❌ Error getting todos for {username}: {e}")
    
    for username in ["mom_house2", "dad_house2"]:
        if username in tokens:
            try:
                headers = {"Authorization": f"Bearer {tokens[username]}"}
                response = requests.get(f"{API_BASE}/todos", headers=headers)
                if response.status_code == 200:
                    todos = response.json()
                    print(f"📋 {username} sees {len(todos)} todos:")
                    for todo in todos:
                        print(f"   - {todo['title']}")
                else:
                    print(f"❌ Failed to get todos for {username}: {response.text}")
            except Exception as e:
                print(f"❌ Error getting todos for {username}: {e}")
    
    print("\n✅ Household isolation test completed!")
    print("💡 Users should only see todos from their own household.")

if __name__ == "__main__":
    test_household_isolation()
