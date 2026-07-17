#!/usr/bin/env python3
"""
Diagnostic script to check if the Upstox API token is valid and working
"""

import os
import sys
import requests
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

print("=" * 80)
print("🔍 UPSTOX TOKEN DIAGNOSTIC")
print("=" * 80)

# Check if token is set
token = os.getenv('UPSTOX_ANALYTICS_TOKEN')
if not token:
    print("\n❌ ERROR: UPSTOX_ANALYTICS_TOKEN not set in environment!")
    print("   Set it in .env file or export it as an environment variable")
    sys.exit(1)

print(f"\n✅ Token found in environment")
print(f"   Token length: {len(token)} characters")
print(f"   Token (first 50 chars): {token[:50]}...")

# Test the API endpoint
print("\n" + "=" * 80)
print("Testing API Authentication...")
print("=" * 80)

url = "https://api.upstox.com/v3/feed/market-data-feed/authorize"
headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0",
}

try:
    print(f"\n📤 Sending request to: {url}")
    response = requests.get(url, headers=headers, timeout=10)

    print(f"📥 Response status code: {response.status_code}")
    print(f"📥 Response content-type: {response.headers.get('content-type', 'unknown')}")

    # Check if response is JSON
    try:
        data = response.json()
        print(f"\n✅ Response is valid JSON")
        print(f"📋 Response (first 500 chars):")
        print(json.dumps(data, indent=2)[:500])

        if response.status_code == 200 and data.get("status") == "success":
            print("\n✅ SUCCESS! Token is valid and working!")
            print(f"✅ WebSocket URL obtained: {data['data']['authorized_redirect_uri'][:60]}...")
        elif response.status_code == 401:
            print("\n❌ ERROR: Token is expired or invalid (401 Unauthorized)")
            print("   Go to: https://account.upstox.com/developer/apps#analytics")
            print("   Generate a new Analytics token and update .env file")
        else:
            print(f"\n⚠️  Unexpected response status: {response.status_code}")
            print(f"   Response: {data}")

    except json.JSONDecodeError as e:
        print(f"\n❌ ERROR: Response is not valid JSON")
        print(f"   This usually means the API returned an error page (HTML)")
        print(f"   Status code: {response.status_code}")
        print(f"\n   Response (first 500 chars):")
        print(response.text[:500])

        if response.status_code == 401:
            print("\n❌ Token is likely expired or invalid")
            print("   Go to: https://account.upstox.com/developer/apps#analytics")
            print("   Generate a new Analytics token and update .env file")
        elif response.status_code >= 500:
            print("\n⚠️  Upstox API server error - try again later")
        else:
            print(f"\n⚠️  Unexpected error (status {response.status_code})")

except requests.exceptions.Timeout:
    print("\n❌ ERROR: Request timed out")
    print("   The API server took too long to respond")
    print("   Check your internet connection and try again")

except requests.exceptions.ConnectionError as e:
    print(f"\n❌ ERROR: Connection failed: {e}")
    print("   Check your internet connection")

except Exception as e:
    print(f"\n❌ ERROR: {type(e).__name__}: {e}")

print("\n" + "=" * 80)
