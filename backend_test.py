#!/usr/bin/env python3
"""
Backend API Tests for Brain Desk Application

Tests the core API endpoints to verify:
1. Health check endpoint
2. Protected endpoints return proper 401 status
3. Auth login returns Google OAuth URL
4. No server crashes or 500 errors
"""

import requests
import json
import os
from datetime import datetime

# Get backend URL from environment or use default
BACKEND_URL = "https://brain-desk-1.preview.emergentagent.com/api"

def test_health_check():
    """Test the health check endpoint"""
    print("\n=== Testing Health Check Endpoint ===")
    try:
        response = requests.get(f"{BACKEND_URL}/")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ Health check endpoint working")
            return True
        else:
            print(f"❌ Health check failed with status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {str(e)}")
        return False

def test_dashboard_auth():
    """Test that dashboard endpoint requires authentication"""
    print("\n=== Testing Dashboard Authentication ===")
    try:
        response = requests.get(f"{BACKEND_URL}/dashboard")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 401:
            print("✅ Dashboard correctly requires authentication")
            return True
        else:
            print(f"❌ Dashboard auth test failed - expected 401, got {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Dashboard auth test error: {str(e)}")
        return False

def test_courses_auth():
    """Test that courses endpoint requires authentication"""
    print("\n=== Testing Courses Authentication ===")
    try:
        response = requests.get(f"{BACKEND_URL}/courses")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 401:
            print("✅ Courses correctly requires authentication")
            return True
        else:
            print(f"❌ Courses auth test failed - expected 401, got {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Courses auth test error: {str(e)}")
        return False

def test_auth_login():
    """Test that auth login endpoint returns Google OAuth URL"""
    print("\n=== Testing Auth Login Endpoint ===")
    try:
        response = requests.get(f"{BACKEND_URL}/auth/login")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                if "authorization_url" in data and "accounts.google.com" in data["authorization_url"]:
                    print("✅ Auth login returns valid Google OAuth URL")
                    return True
                else:
                    print("❌ Auth login response doesn't contain valid Google OAuth URL")
                    return False
            except json.JSONDecodeError:
                print("❌ Auth login response is not valid JSON")
                return False
        else:
            print(f"❌ Auth login failed with status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Auth login test error: {str(e)}")
        return False

def test_additional_endpoints():
    """Test additional endpoints to verify they're properly protected"""
    print("\n=== Testing Additional Protected Endpoints ===")
    endpoints = [
        "/assignments",
        "/notes", 
        "/auth/me",
        "/sync/classroom"
    ]
    
    results = []
    for endpoint in endpoints:
        try:
            response = requests.get(f"{BACKEND_URL}{endpoint}")
            print(f"{endpoint}: {response.status_code}")
            if response.status_code == 401:
                results.append(True)
                print(f"✅ {endpoint} correctly requires authentication")
            else:
                results.append(False)
                print(f"❌ {endpoint} auth check failed - expected 401, got {response.status_code}")
        except Exception as e:
            print(f"❌ {endpoint} test error: {str(e)}")
            results.append(False)
    
    return all(results)

def check_server_health():
    """Verify server is responsive and not returning 500 errors"""
    print("\n=== Server Health Check ===")
    try:
        # Test multiple endpoints to ensure server stability
        endpoints = ["/", "/courses", "/dashboard", "/auth/login"]
        server_healthy = True
        
        for endpoint in endpoints:
            response = requests.get(f"{BACKEND_URL}{endpoint}")
            if response.status_code == 500:
                print(f"❌ Server error (500) on {endpoint}")
                server_healthy = False
            else:
                print(f"✅ {endpoint} responsive (status: {response.status_code})")
        
        return server_healthy
    except Exception as e:
        print(f"❌ Server health check error: {str(e)}")
        return False

def run_all_tests():
    """Run all backend tests and return summary"""
    print(f"🚀 Starting Brain Desk Backend API Tests")
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    test_results = {
        "health_check": test_health_check(),
        "dashboard_auth": test_dashboard_auth(), 
        "courses_auth": test_courses_auth(),
        "auth_login": test_auth_login(),
        "additional_endpoints": test_additional_endpoints(),
        "server_health": check_server_health()
    }
    
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results.items():
        status = "PASS" if result else "FAIL"
        icon = "✅" if result else "❌"
        print(f"{icon} {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Backend API is working correctly.")
    else:
        print(f"⚠️  {total - passed} test(s) failed. Please check the issues above.")
    
    return test_results

if __name__ == "__main__":
    results = run_all_tests()
    
    # Exit with proper code
    if all(results.values()):
        exit(0)
    else:
        exit(1)