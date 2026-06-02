import os
import sys
import pandas as pd
import pymysql
from sqlalchemy import create_engine
from dotenv import load_dotenv
from urllib.parse import quote_plus

# --- 1. Setup & Configuration ---
load_dotenv()

DB_USER = os.getenv("MYSQL_USER", "root")
DB_PASSWORD = os.getenv("MYSQL_PASSWORD", "LangGraph@1") 
DB_HOST = os.getenv("MYSQL_HOST", "localhost")
DB_PORT = int(os.getenv("MYSQL_PORT", 3306))

# Directory Setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

encoded_password = quote_plus(DB_PASSWORD)

# Admin Database Name (As requested)
ADMIN_DB_NAME = "project_db"

# --- PLATFORM CONFIGURATION ---
# Grouping files by their platform prefix
PLATFORM_FILES = {
    "google": {
        "googleads_campaign_conversion_goal_history.csv",
        "googleads_campaign_history.csv",
        "googleads_campaign_stats.csv"
    },
    "shopify": {
        "shopify_order.csv",
        "shopify_order_line.csv",
        "shopify_order_line_refund.csv",
        "shopify_product.csv"
    },
    "linkedin": {
        "linkedinads_ad_analytics_by_creative.csv",
        "linkedinads_campaign_history.csv",
        "linkedinads_creative_history.csv",
        "linkedinads_post_history.csv"
    },
    "fb": {
        "ad_conversion.csv",
        "fb_ad_history.csv",
        "fb_basic_ad.csv",
        "fb_basic_campaign.csv",
        "fb_campaign_actions.csv",
        "fb_daily_page_metrics_total.csv"
    },
    "insta": {
        "insta_media_history.csv",
        "insta_media_insights.csv",
        "insta_user_history.csv",
        "insta_user_insights.csv",
        "insta_user_lifetime_insights.csv"
    }
}

def get_mysql_connection(db_name=None):
    """Raw connection for creating databases/tables."""
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        port=DB_PORT,
        database=db_name, 
        autocommit=True
    )

def setup_admin_db():
    """
    Ensures 'project_db' and the 'User_db_mapping' table exist.
    """
    print(f"⚙️  Checking Admin DB '{ADMIN_DB_NAME}'...")
    
    # 1. Create DB if not exists
    conn = get_mysql_connection()
    with conn.cursor() as cursor:
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {ADMIN_DB_NAME}")
    conn.close()

    # 2. Create Table
    conn = get_mysql_connection(ADMIN_DB_NAME)
    with conn.cursor() as cursor:
        sql = """
        CREATE TABLE IF NOT EXISTS User_db_mapping (
            username VARCHAR(50),
            db_name VARCHAR(100),
            status INT DEFAULT 0,
            PRIMARY KEY (username, db_name)
        );
        """
        cursor.execute(sql)
    conn.close()
    print(f"✅ Admin DB setup complete.")

def create_client_database(new_db_name):
    """Create a specific client database (e.g. google_ajinkya)."""
    try:
        conn = get_mysql_connection()
        with conn.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {new_db_name}")
        conn.close()
        print(f"   🔨 Database created: {new_db_name}")
    except Exception as e:
        print(f"   ❌ Error creating database {new_db_name}: {e}")

def upload_files_to_db(db_name, allowed_file_set):
    """
    Uploads only the files belonging to the specific platform.
    Returns True if data was uploaded, False otherwise.
    """
    # Check if data directory exists
    if not os.path.exists(DATA_DIR):
        return False

    # Filter files present in directory that match the platform list
    files_in_folder = set(os.listdir(DATA_DIR))
    files_to_process = files_in_folder.intersection(allowed_file_set)

    if not files_to_process:
        return False

    print(f"   📂 Found {len(files_to_process)} files for '{db_name}'. Uploading...")
    
    engine = create_engine(f"mysql+pymysql://{DB_USER}:{encoded_password}@{DB_HOST}/{db_name}")
    
    for filename in files_to_process:
        file_path = os.path.join(DATA_DIR, filename)
        table_name = os.path.splitext(filename)[0]
        try:
            df = pd.read_csv(file_path)
            df.to_sql(table_name, con=engine, if_exists='replace', index=False)
            print(f"      -> Uploaded: {table_name}")
        except Exception as e:
            print(f"      ❌ Failed: {filename} - {e}")
            
    return True

def register_user_mapping(username, db_name, status):
    """
    Inserts or updates the mapping in project_db.
    """
    try:
        conn = get_mysql_connection(ADMIN_DB_NAME)
        with conn.cursor() as cursor:
            sql = """
            INSERT INTO User_db_mapping (username, db_name, status) 
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE status = VALUES(status)
            """
            cursor.execute(sql, (username, db_name, status))
        conn.close()
        print(f"   🔗 Mapped: {username} | {db_name} | Status: {status}")
    except Exception as e:
        print(f"   ❌ Error mapping user: {e}")

# --- Main Execution ---
if __name__ == "__main__":
    print("--- 🚀 Multi-DB Client Onboarding ---")
    
    # 1. Input Handling
    if len(sys.argv) == 2:
        CLIENT_USERNAME = sys.argv[1]
    else:
        CLIENT_USERNAME = input("Enter Client Username (e.g., Ajinkya): ").strip()
        
    if not CLIENT_USERNAME:
        print("❌ Username is required.")
        sys.exit(1)

    print(f"\nProcessing User: [{CLIENT_USERNAME}]\n")

    # 2. Setup Admin Infrastructure
    setup_admin_db()

    # 3. Iterate over Platforms
    for platform, file_set in PLATFORM_FILES.items():
        # Generate DB Name: e.g., google_Ajinkya
        target_db_name = f"{platform}_{CLIENT_USERNAME}" # e.g. google_ajinkya
        
        print(f"\n🔹 Processing Platform: {platform.upper()} ({target_db_name})")

        # Check if files exist for this platform in the data folder
        files_present_in_dir = set(os.listdir(DATA_DIR)) if os.path.exists(DATA_DIR) else set()
        has_files = not files_present_in_dir.isdisjoint(file_set)

        status = 0

        if has_files:
            # 1. Create the specific DB
            create_client_database(target_db_name)
            # 2. Upload data
            upload_success = upload_files_to_db(target_db_name, file_set)
            if upload_success:
                status = 1
        else:
            print(f"   ⚠️ No files found for {platform}. Skipping DB creation.")

        # 4. Register Mapping (Status 1 if active, 0 if skipped)
        register_user_mapping(CLIENT_USERNAME, target_db_name, status)

    print("\n🎉 Onboarding Complete!")