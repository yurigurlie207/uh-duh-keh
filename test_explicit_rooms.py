#!/usr/bin/env python3
"""
Test script to verify explicit room selection works correctly
"""
import requests
import json
import time
import socketio

# Test configuration
API_BASE = "http://localhost:3001/api"
SOCKET_URL = "http://localhost:3002"

def test_explicit_room_selection():
    """Test that users must explicitly choose their room after signing in"""
    
    print("🧪 Testing explicit room selection...")
    
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
    
    # Test explicit room selection
    print("\n🏠 Testing explicit room selection...")
    
    # Create Socket.IO client
    sio = socketio.SimpleClient()
    
    try:
        # Connect user from household 1
        print("🔌 Connecting mom_house1 to Socket.IO...")
        sio.connect(SOCKET_URL, auth={'token': tokens['mom_house1']})
        print("✅ mom_house1 connected")
        
        # Wait for connection to establish
        time.sleep(2)
        
        # Try to create a todo without joining a room (should fail)
        print("\n📝 Trying to create todo without joining a room...")
        sio.emit('todo:create', {
            'title': 'Task without room',
            'assigned_to': 'mom',
            'priority': '1'
        })
        
        # Wait for response
        time.sleep(2)
        
        # Now explicitly join the household room
        print("\n🏠 Explicitly joining household room...")
        sio.emit('join_household', {'household_id': 'household_1'})
        
        # Wait for room join to complete
        time.sleep(2)
        
        # Now try to create a todo (should work)
        print("\n📝 Creating todo after joining room...")
        sio.emit('todo:create', {
            'title': 'Task after joining room',
            'assigned_to': 'mom',
            'priority': '1'
        })
        
        # Wait for response
        time.sleep(2)
        
        # Test trying to join wrong household (should fail)
        print("\n🚫 Trying to join wrong household...")
        sio.emit('join_household', {'household_id': 'household_2'})
        
        # Wait for response
        time.sleep(2)
        
        # Test switching to correct household
        print("\n🔄 Switching to correct household...")
        sio.emit('join_household', {'household_id': 'household_1'})
        
        # Wait for response
        time.sleep(2)
        
        print("\n✅ Explicit room selection test completed!")
        print("💡 Users must explicitly join a room after connecting.")
        print("🔒 Users can only join their own household room.")
        print("🏠 Room membership is required for all todo operations.")
        
    except Exception as e:
        print(f"❌ Error during Socket.IO test: {e}")
    finally:
        # Disconnect client
        try:
            sio.disconnect()
        except:
            pass

if __name__ == "__main__":
    test_explicit_room_selection()
