"""
Test script to diagnose CORS and authentication issues.
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

# Configuration
BASE_URL = os.getenv("API_BASE_URL", "http://localhost:5000")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

def test_cors_preflight():
    """Test CORS preflight request"""
    print("\n=== Testing CORS Preflight (OPTIONS) ===")
    url = f"{BASE_URL}/api/user-profile"
    headers = {
        "Origin": FRONTEND_URL,
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "authorization,content-type"
    }
    
    try:
        response = requests.options(url, headers=headers)
        print(f"Status: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            print("✓ CORS preflight successful")
            if "access-control-allow-origin" in response.headers:
                print(f"✓ Allowed Origin: {response.headers['access-control-allow-origin']}")
            else:
                print("✗ Missing Access-Control-Allow-Origin header")
        else:
            print(f"✗ CORS preflight failed with status {response.status_code}")
    except Exception as e:
        print(f"✗ Error: {e}")


def test_ping():
    """Test unprotected endpoint"""
    print("\n=== Testing Unprotected Endpoint (/api/ping) ===")
    url = f"{BASE_URL}/api/ping"
    headers = {"Origin": FRONTEND_URL}
    
    try:
        response = requests.get(url, headers=headers)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            print("✓ Server is running")
            if "access-control-allow-origin" in response.headers:
                print(f"✓ CORS header present: {response.headers['access-control-allow-origin']}")
            else:
                print("✗ Missing CORS header")
        else:
            print(f"✗ Request failed with status {response.status_code}")
    except Exception as e:
        print(f"✗ Error: {e}")


def test_protected_without_token():
    """Test protected endpoint without token"""
    print("\n=== Testing Protected Endpoint Without Token ===")
    url = f"{BASE_URL}/api/user-profile"
    headers = {"Origin": FRONTEND_URL}
    
    try:
        response = requests.get(url, headers=headers)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:200]}")
        
        if response.status_code == 403:
            print("✓ Returns 403 (as expected without token)")
            print("⚠ Issue: Frontend might not be sending Authorization header")
        elif response.status_code == 401:
            print("✓ Returns 401 (as expected without token)")
        else:
            print(f"⚠ Unexpected status code: {response.status_code}")
    except Exception as e:
        print(f"✗ Error: {e}")


def test_protected_with_invalid_token():
    """Test protected endpoint with invalid token"""
    print("\n=== Testing Protected Endpoint With Invalid Token ===")
    url = f"{BASE_URL}/api/user-profile"
    headers = {
        "Origin": FRONTEND_URL,
        "Authorization": "Bearer invalid_token_here"
    }
    
    try:
        response = requests.get(url, headers=headers)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:200]}")
        
        if response.status_code == 401:
            print("✓ Returns 401 for invalid token (correct behavior)")
        elif response.status_code == 403:
            print("⚠ Returns 403 instead of 401")
            print("⚠ This might indicate a CORS or authentication configuration issue")
        else:
            print(f"⚠ Unexpected status code: {response.status_code}")
    except Exception as e:
        print(f"✗ Error: {e}")


def check_env_config():
    """Check environment configuration"""
    print("\n=== Checking Environment Configuration ===")
    
    auth0_domain = os.getenv("AUTH0_DOMAIN")
    auth0_audience = os.getenv("AUTH0_AUDIENCE")
    cors_origins = os.getenv("CORS_ALLOWED_ORIGINS")
    
    print(f"AUTH0_DOMAIN: {auth0_domain or '✗ NOT SET'}")
    print(f"AUTH0_AUDIENCE: {auth0_audience or '✗ NOT SET'}")
    print(f"CORS_ALLOWED_ORIGINS: {cors_origins or '✗ NOT SET (using defaults)'}")
    
    if auth0_domain and auth0_audience:
        print("✓ Auth0 configuration present")
    else:
        print("✗ Auth0 configuration incomplete")


if __name__ == "__main__":
    print("=" * 60)
    print("CORS and Authentication Diagnostic Tool")
    print("=" * 60)
    print(f"Base URL: {BASE_URL}")
    print(f"Frontend URL: {FRONTEND_URL}")
    
    check_env_config()
    test_ping()
    test_cors_preflight()
    test_protected_without_token()
    test_protected_with_invalid_token()
    
    print("\n" + "=" * 60)
    print("Diagnosis Complete")
    print("=" * 60)
    print("\nNext Steps:")
    print("1. If CORS preflight fails, add your frontend URL to CORS_ALLOWED_ORIGINS in .env")
    print("2. If you see 403 with valid token, check Auth0 configuration")
    print("3. Check browser console for specific CORS errors")
    print("4. Verify Authorization header is being sent from frontend")
