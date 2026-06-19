import os
from redis import Redis
from dotenv import load_dotenv

# Load environment variables to get REDIS_URL
load_dotenv()

redis_url = os.getenv("REDIS_URL")

if not redis_url:
    print("[FAIL] REDIS_URL not found in .env file.")
else:
    print(f"Attempting to connect to: {redis_url}")
    try:
        # Connect to Redis
        r = Redis.from_url(redis_url, decode_responses=False)

        # Flush All Data
        r.flushall()
        print(f"[OK] Redis memory cleared (FLUSHALL executed). DBSIZE now: {r.dbsize()}")
    except Exception as e:
        print(f"[FAIL] Failed to flush Redis: {e}")
