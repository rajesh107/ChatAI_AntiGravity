import os
import sys
import logging
import jwt

# Force UTF-8 output on Windows to prevent emoji UnicodeEncodeError
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")
from typing import List, Dict
from fastapi import FastAPI, HTTPException, Request, Depends, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordRequestForm
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
from auth import (
    Token, 
    authenticate_user, 
    create_access_token, 
    get_current_user
)

# Import our dynamic factory from agent.py
try:
    from agent import get_compiled_graph
except ImportError:
    def get_compiled_graph(*args): raise NotImplementedError("Agent not found")

load_dotenv()

# --- Logging Config ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)



# --- Admin DB Config ---
ADMIN_DB_NAME = os.getenv("MYSQL_DB_NAME")
DB_USER = os.getenv("MYSQL_USER", "root")
DB_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
DB_HOST = os.getenv("MYSQL_HOST", "localhost")
DB_PORT = os.getenv("MYSQL_PORT", "3306") 


encoded_user = quote_plus(DB_USER)
encoded_password = quote_plus(DB_PASSWORD)

# --- SECURITY CONFIGURATION ---
#security = HTTPBearer()


ADMIN_DB_URI = f"mysql+pymysql://{encoded_user}:{encoded_password}@{DB_HOST}:{DB_PORT}/{ADMIN_DB_NAME}"

# --- FastAPI Setup ---
app = FastAPI(title="Dynamic Multi-Tenant Marketing Agent ")

# --- CORS Configuration ---
cors_origins_str = os.getenv("CORS_ORIGINS", "*")
origins = [origin.strip() for origin in cors_origins_str.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Global Database Engine ---
admin_engine = None

@app.on_event("startup")
async def startup_event():
    global admin_engine
    try:
        if DB_HOST:
            admin_engine = create_engine(ADMIN_DB_URI, pool_pre_ping=True)
            print("✅ [STARTUP] Admin DB Connected")
    except Exception:
        pass

@app.on_event("shutdown")
async def shutdown_event():
    #global admin_engine
    if admin_engine:
        admin_engine.dispose()

# --- Mapping Configuration ---
# Kept simple as per request. Multiple DBs in Admin DB can map to 'FBADS', 
# which will all group under 'facebook' key.
TYPE_TO_AGENT_KEY = {
    "GOOGLEADS": "google_ads",
    "SHOPIFY": "shopify",
    "LINKEDINADS": "linkedin",
    "FBADS": "facebook",  # Map FBADS to the single facebook key
    "INSTA": "instagram",
    "GA": "google_analytics"  # GA4 analytics data
}

class ChatRequest(BaseModel):
    query: str
    thread_id: str

class ChatResponse(BaseModel):
    response: str
    thread_id: str
    connected_platforms: List[str]

# --- Helper: Lookup Active Databases ---
def get_active_databases(username: str) -> Dict[str, List[str]]:
    """
    Returns a Dict where Key = Agent Key (e.g. 'facebook') 
    and Value = List of Database Names (e.g. ['fb_db_1', 'fb_db_2'])
    """
    if not admin_engine:
        raise HTTPException(status_code=500, detail="Database engine not initialized.")

    # Initialize dictionary with lists
    active_db_map = {} 
    
    try:
        with admin_engine.connect() as conn:
            # Select DBs for user
            sql = text("""
                SELECT type, schema_name
                FROM fivetran_connections
                WHERE user_id = :username
                  AND type IN ('FBADS', 'GOOGLEADS', 'INSTA', 'LINKEDINADS','LINKEDIN','GA', 'SHOPIFY')
                  AND status = 1
            """)
            result = conn.execute(sql, {"username": username})
            rows = result.fetchall()
            
            for row in rows:
                db_type = row[0] 
                db_name = row[1]
                
                if db_type in TYPE_TO_AGENT_KEY:
                    agent_key = TYPE_TO_AGENT_KEY[db_type]
                    
                    # Initialize list if key doesn't exist
                    if agent_key not in active_db_map:
                        active_db_map[agent_key] = []
                    
                    # Append DB name to the list
                    active_db_map[agent_key].append(db_name)
                    print(f"      ✅ [MAPPED] Type '{db_type}' -> Key '{agent_key}' -> Added DB '{db_name}'")
                else:
                    print(f"      ⚠️ [SKIP] Unknown Type '{db_type}'")
            
            return active_db_map

    except Exception as e:
        logger.error(f"DB Lookup Error for {username}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database mapping lookup failed.")

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    # 1. Authenticate the user (checks username & password)
    user = authenticate_user(form_data.username, form_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 2. Create the JWT Token
    # The 'sub' (subject) field holds the username
    access_token = create_access_token(data={"sub": user["username"]})
    
    return {"access_token": access_token, "token_type": "bearer"}


# --- PROTECTED CHAT ENDPOINT ---
@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(
    request: ChatRequest,
    # This dependency validates the token from the header
    current_user: dict = Depends(get_current_user) 
):
    print(f"[AUTH] Request Authorized for User: {current_user['username']}")
    
    target_username = request.thread_id
    
    # Optional: Enforce that users can only access their own thread
    # if target_username != current_user['username']:
    #     raise HTTPException(status_code=403, detail="You can only access your own data")

    active_db_map = get_active_databases(target_username)
    
    if not active_db_map:
        raise HTTPException(status_code=404, detail="No active databases found")

    try:
        agent_app = get_compiled_graph(target_username, active_db_map)
        config = {"configurable": {"thread_id": target_username}}
        final_state = agent_app.invoke(
            {"messages": [HumanMessage(content=request.query)]}, 
            config=config
        )
        return ChatResponse(
            response=final_state["messages"][-1].content,
            thread_id=target_username,
            connected_platforms=list(active_db_map.keys())
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
