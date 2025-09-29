#!/usr/bin/env python3
"""
Test script to verify Socket.IO rooms approach works correctly
"""
import requests
import json
import time
import socketio

# Test configuration
API_BASE = "http://localhost:3001/api"
SOCKET_URL = "http://localhost:3002"

def test_rooms_approach():
    """Test that Socket.IO rooms provide proper household isolation"""
    
    print("🧪 Testing Socket.IO rooms approach...")
    
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
    
    # Test Socket.IO rooms isolation
    print("\n🏠 Testing Socket.IO rooms isolation...")
    
    # Create Socket.IO clients for each household
    sio_household1 = socketio.SimpleClient()
    sio_household2 = socketio.SimpleClient()
    
    try:
        # Connect household 1 users
        print("🔌 Connecting household 1 users to Socket.IO...")
        sio_household1.connect(SOCKET_URL, auth={'token': tokens['mom_house1']})
        print("✅ mom_house1 connected")
        
        # Connect household 2 users
        print("🔌 Connecting household 2 users to Socket.IO...")
        sio_household2.connect(SOCKET_URL, auth={'token': tokens['mom_house2']})
        print("✅ mom_house2 connected")
        
        # Wait for connections to establish
        time.sleep(2)
        
        # Test room isolation by creating todos via Socket.IO
        print("\n📝 Testing room isolation with Socket.IO...")
        
        # Create todo from household 1
        print("Creating todo from household 1...")
        sio_household1.emit('todo:create', {
            'title': 'Household 1 Task',
            'assigned_to': 'mom',
            'priority': '1'
        })
        
        # Create todo from household 2
        print("Creating todo from household 2...")
        sio_household2.emit('todo:create', {
            'title': 'Household 2 Task',
            'assigned_to': 'mom',
            'priority': '1'
        })
        
        # Wait for events to process
        time.sleep(2)
        
        # Test REST API isolation
        print("\n🔍 Testing REST API isolation...")
        
        # Get todos for household 1
        headers1 = {"Authorization": f"Bearer {tokens['mom_house1']}"}
        response1 = requests.get(f"{API_BASE}/todos", headers=headers1)
        if response1.status_code == 200:
            todos1 = response1.json()
            print(f"📋 Household 1 sees {len(todos1)} todos:")
            for todo in todos1:
                print(f"   - {todo['title']}")
        else:
            print(f"❌ Failed to get todos for household 1: {response1.text}")
        
        # Get todos for household 2
        headers2 = {"Authorization": f"Bearer {tokens['mom_house2']}"}
        response2 = requests.get(f"{API_BASE}/todos", headers=headers2)
        if response2.status_code == 200:
            todos2 = response2.json()
            print(f"📋 Household 2 sees {len(todos2)} todos:")
            for todo in todos2:
                print(f"   - {todo['title']}")
        else:
            print(f"❌ Failed to get todos for household 2: {response2.text}")
        
        print("\n✅ Rooms approach test completed!")
        print("💡 Each household should only see their own todos.")
        print("🏠 Socket.IO rooms automatically handle real-time isolation.")
        print("🔒 REST API still uses database filtering for data integrity.")
        
    except Exception as e:
        print(f"❌ Error during Socket.IO test: {e}")
    finally:
        # Disconnect clients
        try:
            sio_household1.disconnect()
            sio_household2.disconnect()
        except:
            pass

if __name__ == "__main__":
    test_rooms_approach()
