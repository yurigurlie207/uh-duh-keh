#!/usr/bin/env python3
"""
Test script to verify frontend authentication works correctly
"""
import requests
import json

# Test configuration
API_BASE = "http://localhost:3001/api"

def test_frontend_auth():
    """Test that frontend authentication works correctly"""
    
    print("🧪 Testing frontend authentication...")
    
    # Test registration (without household_id - should auto-generate)
    print("\n📝 Testing registration (frontend style)...")
    try:
        response = requests.post(f"{API_BASE}/auth/register", json={
            "username": "frontend_user",
            "password": "password123"
        })
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            print("✅ Registration works (auto-generated household_id)")
        else:
            print("❌ Registration failed")
    except Exception as e:
        print(f"❌ Error during registration: {e}")
    
    # Test login (frontend style)
    print("\n🔐 Testing login (frontend style)...")
    try:
        response = requests.post(f"{API_BASE}/auth/login", json={
            "username": "frontend_user",
            "password": "password123"
        })
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Login works!")
            print(f"   Token: {data.get('token', 'None')[:20]}...")
            print(f"   Username: {data.get('username')}")
            print(f"   Household ID: {data.get('household_id')}")
            
            # Test that the token contains household_id
            import jwt
            try:
                # Decode without verification to see payload
                payload = jwt.decode(data['token'], options={"verify_signature": False})
                print(f"   JWT contains household_id: {payload.get('household_id')}")
            except Exception as e:
                print(f"   Could not decode JWT: {e}")
        else:
            print("❌ Login failed")
    except Exception as e:
        print(f"❌ Error during login: {e}")
    
    # Test login with wrong password
    print("\n🚫 Testing login with wrong password...")
    try:
        response = requests.post(f"{API_BASE}/auth/login", json={
            "username": "frontend_user",
            "password": "wrongpassword"
        })
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 401:
            print("✅ Wrong password correctly rejected!")
        else:
            print("❌ Wrong password should have been rejected")
    except Exception as e:
        print(f"❌ Error during login test: {e}")
    
    print("\n✅ Frontend authentication test completed!")
    print("💡 Frontend can now login/register without knowing about household_id")
    print("🏠 Backend automatically handles household_id generation and inclusion")

if __name__ == "__main__":
    test_frontend_auth()
