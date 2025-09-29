#!/usr/bin/env python3
"""
Test script to verify login and registration work correctly
"""
import requests
import json

# Test configuration
API_BASE = "http://localhost:3001/api"

def test_auth_fix():
    """Test that login and registration work correctly"""
    
    print("🧪 Testing authentication fix...")
    
    # Test registration without household_id (should auto-generate)
    print("\n📝 Testing registration without household_id...")
    try:
        response = requests.post(f"{API_BASE}/auth/register", json={
            "username": "testuser",
            "password": "password123"
        })
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            print("✅ Registration without household_id works!")
        else:
            print("❌ Registration failed")
    except Exception as e:
        print(f"❌ Error during registration: {e}")
    
    # Test registration with household_id
    print("\n📝 Testing registration with household_id...")
    try:
        response = requests.post(f"{API_BASE}/auth/register", json={
            "username": "testuser2",
            "password": "password123",
            "household_id": "custom_household"
        })
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            print("✅ Registration with household_id works!")
        else:
            print("❌ Registration failed")
    except Exception as e:
        print(f"❌ Error during registration: {e}")
    
    # Test login
    print("\n🔐 Testing login...")
    try:
        response = requests.post(f"{API_BASE}/auth/login", json={
            "username": "testuser",
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
        else:
            print("❌ Login failed")
    except Exception as e:
        print(f"❌ Error during login: {e}")
    
    # Test login with wrong password
    print("\n🚫 Testing login with wrong password...")
    try:
        response = requests.post(f"{API_BASE}/auth/login", json={
            "username": "testuser",
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
    
    print("\n✅ Authentication fix test completed!")

if __name__ == "__main__":
    test_auth_fix()
