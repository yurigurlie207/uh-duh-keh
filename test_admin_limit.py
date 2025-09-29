#!/usr/bin/env python3
"""
Test script to verify only one admin per household
"""
import requests
import json

API_BASE = "http://localhost:3001/api"

def test_admin_limit():
    print("🧪 Testing admin limit per household...")
    
    # Test 1: First user in household should be admin
    print("\n1. Registering first user (should be admin)...")
    response1 = requests.post(f"{API_BASE}/auth/register", json={
        "username": "admin_user",
        "password": "password123",
        "household_name": "Test Household"
    })
    print(f"Status: {response1.status_code}")
    if response1.status_code == 200:
        data1 = response1.json()
        print(f"✅ First user is_admin: {data1.get('is_admin')}")
        assert data1.get('is_admin') == True, "First user should be admin"
    else:
        print(f"❌ Error: {response1.text}")
        return
    
    # Test 2: Second user in same household should NOT be admin
    print("\n2. Registering second user in same household (should NOT be admin)...")
    response2 = requests.post(f"{API_BASE}/auth/register", json={
        "username": "regular_user",
        "password": "password123",
        "household_name": "Test Household"
    })
    print(f"Status: {response2.status_code}")
    if response2.status_code == 200:
        data2 = response2.json()
        print(f"✅ Second user is_admin: {data2.get('is_admin')}")
        assert data2.get('is_admin') == False, "Second user should NOT be admin"
    else:
        print(f"❌ Error: {response2.text}")
        return
    
    # Test 3: Third user in same household should also NOT be admin
    print("\n3. Registering third user in same household (should NOT be admin)...")
    response3 = requests.post(f"{API_BASE}/auth/register", json={
        "username": "another_user",
        "password": "password123",
        "household_name": "Test Household"
    })
    print(f"Status: {response3.status_code}")
    if response3.status_code == 200:
        data3 = response3.json()
        print(f"✅ Third user is_admin: {data3.get('is_admin')}")
        assert data3.get('is_admin') == False, "Third user should NOT be admin"
    else:
        print(f"❌ Error: {response3.text}")
        return
    
    print("\n🎉 All tests passed! Only one admin per household is enforced.")

if __name__ == "__main__":
    test_admin_limit()
