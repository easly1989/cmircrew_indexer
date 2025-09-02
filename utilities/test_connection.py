#!/usr/bin/env python3
"""
Test basic connection to mircrew forum to debug search issues
"""

import requests
from login import MirCrewLogin

def test_basic_connection():
    print("🔍 Testing basic connection to mircrew forum...")

    # Test 1: Basic GET request to homepage
    print("\n1️⃣ Testing homepage access...")
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'})

    try:
        response = session.get("https://mircrew-releases.org/index.php", timeout=30)
        print(f"   Status: {response.status_code}")
        print(f"   Content length: {len(response.text)} chars")
        if "login" in response.text.lower():
            print("   ✅ Contains login reference (good)")
        if "forum" in response.text.lower():
            print("   ✅ Contains forum reference (good)")
        if "<form" in response.text:
            print("   ✅ Contains form tags (good)")

    except Exception as e:
        print(f"   ❌ Error: {e}")

    # Test 2: Search page access
    print("\n2️⃣ Testing search page access...")
    try:
        response = session.get("https://mircrew-releases.org/search.php", timeout=30)
        print(f"   Status: {response.status_code}")
        print(f"   Content length: {len(response.text)} chars")
        if "search" in response.text.lower():
            print("   ✅ Contains search references")
        if response.ok:
            print("   ✅ Response successful")
        forms_count = response.text.count("<form")
        print(f"   Found {forms_count} form tags")
        if "<input" in response.text:
            print("   ✅ Contains input tags")

        # Try to find search form
        form_start = response.text.find('<form')
        if form_start != -1:
            form_end = response.text.find('</form>', form_start)
            if form_end != -1:
                form_content = response.text[form_start:form_end+7]
                print("   📋 Search form preview:")
                print(form_content[:300] + "..." if len(form_content) > 300 else form_content)

    except Exception as e:
        print(f"   ❌ Error: {e}")

    # Test 3: Authenticated connection
    print("\n3️⃣ Testing authenticated connection...")
    try:
        login_client = MirCrewLogin()
        if login_client.login():
            print("   ✅ Authentication successful")
            response = login_client.session.get("https://mircrew-releases.org/search.php", timeout=30)
            print(f"   Search page (authenticated) status: {response.status_code}")
            print(f"   Content length: {len(response.text)} chars")

            # Look for forms in authenticated response
            forms_count = response.text.count("<form")
            print(f"   Found {forms_count} form tags (authenticated)")
        else:
            print("   ❌ Authentication failed")

    except Exception as e:
        print(f"   ❌ Error: {e}")

if __name__ == "__main__":
    test_basic_connection()