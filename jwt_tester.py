import jwt
import requests
import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# CONFIG
API_URL = "http://3.144.229.33:8000/chat"
SECRET_KEY = os.getenv("JWT_SECRET_KEY") # This will load the long hash from .env
USERNAME = os.getenv("API_USER_USERNAME") # admin
PASSWORD = os.getenv("API_USER_PASSWORD") # admin123

def generate_token():
    # Payload matching the client credentials
    payload = {
        "username": USERNAME, 
        "password": PASSWORD,
        "exp": datetime.utcnow() + timedelta(hours=1)
    }
    
    # Encode using the specific Secret Key
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    return token

def test_api():
    if not SECRET_KEY:
        print("❌ Error: Missing JWT_SECRET_KEY in .env")
        return

    print(f"1️⃣  Generating Token for user: {USERNAME}")
    token = generate_token()
    print(f"🔑 Token: {token}")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Replace 'client_1' with a username that actually exists in your user_db_mapping table
    data = {
        "query": "Hello Agent",
        "thread_id": "295" 
    }

    print("\n2️⃣  Sending POST Request...")
    try:
        response = requests.post(API_URL, json=data, headers=headers)
        if response.status_code == 200:
            print("✅ Success! API Accepted the Token.")
            print(response.json())
        else:
            print(f"❌ Failed ({response.status_code}): {response.text}")
    except Exception as e:
        print(f"❌ Connection Error: {e}")

if __name__ == "__main__":
    test_api()