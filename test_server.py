"""
Quick test script to verify server is accessible
"""
import requests
import sys

try:
    response = requests.get('http://127.0.0.1:5000/health', timeout=5)
    if response.status_code == 200:
        print("✅ Server is running and accessible!")
        print(f"Response: {response.json()}")
        print("\n🌐 Open your browser and go to: http://localhost:5000")
    else:
        print(f"❌ Server returned status code: {response.status_code}")
        print(f"Response: {response.text}")
except requests.exceptions.ConnectionRefused:
    print("❌ Server is not running. Please start it with: python3 web_app.py")
except Exception as e:
    print(f"❌ Error: {e}")

