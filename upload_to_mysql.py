'''import os
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv
from urllib.parse import quote_plus 

# Load environment variables if you have them, or set them directly below
load_dotenv()

# --- CONFIGURATION ---
db_user = "root"
db_password = "LangGraph@1"  # <--- REPLACE THIS
db_host = "localhost"
db_name = "marketing_data"

encoded_password = quote_plus(db_password)

# Connect to MySQL
connection_str = f"mysql+pymysql://{db_user}:{encoded_password}@{db_host}/{db_name}"

engine = create_engine(connection_str)

# Directory Setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

# File Lists (Copied from your original code)
files_map = {
    "google_ads": [
        "googleads_campaign_conversion_goal_history.csv",
        "googleads_campaign_history.csv",
        "googleads_campaign_stats.csv"
    ],
    "shopify": [
        "shopify_order.csv",
        "shopify_order_line.csv",
        "shopify_order_line_refund.csv",
        "shopify_product.csv"
    ],
    "linkedin": [
        "linkedinads_ad_analytics_by_creative.csv",
        "linkedinads_campaign_history.csv",
        "linkedinads_creative_history.csv",
        "linkedinads_post_history.csv"
    ],
    "facebook": [
        "ad_conversion.csv",
        "fb_ad_history.csv",
        "fb_basic_ad.csv",
        "fb_basic_campaign.csv",
        "fb_campaign_actions.csv",
        "fb_daily_page_metrics_total.csv"
    ],
    "instagram": [
        "insta_media_history.csv",
        "insta_media_insights.csv",
        "insta_user_history.csv",
        "insta_user_insights.csv",
        "insta_user_lifetime_insights.csv"
    ]
}

def upload_data():
    print("--- Starting Upload to MySQL ---")
    for category, files in files_map.items():
        for filename in files:
            file_path = os.path.join(DATA_DIR, filename)
            table_name = os.path.splitext(filename)[0] # Removes .csv extension

            if os.path.exists(file_path):
                try:
                    print(f"Reading {filename}...")
                    df = pd.read_csv(file_path)
                    
                    # Upload to MySQL
                    # if_exists='replace' will drop the table if it exists and create a new one
                    df.to_sql(table_name, con=engine, if_exists='replace', index=False)
                    print(f"✅ Successfully uploaded table: {table_name}")
                except Exception as e:
                    print(f"❌ Error uploading {filename}: {e}")
            else:
                print(f"⚠️ File not found: {file_path}")
    print("--- Upload Complete ---")

if __name__ == "__main__":
    upload_data()'''


import os
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from urllib.parse import quote_plus 

# Load environment variables
load_dotenv()

# --- CONFIGURATION ---
db_user = "root"
db_password = "LangGraph@1" 
db_host = "localhost"

# Encode password
encoded_password = quote_plus(db_password)

# Directory Setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

# --- DATA MAPPING ---
# Structure: { DATABASE_NAME : { CATEGORY : [FILES] } }
database_structure = {
    "marketing_data": { 
        # These will go into the FIRST database
        "google_ads": [
            "googleads_campaign_conversion_goal_history.csv",
            "googleads_campaign_history.csv",
            "googleads_campaign_stats.csv"
        ],
        "shopify": [
            "shopify_order.csv",
            "shopify_order_line.csv",
            "shopify_order_line_refund.csv",
            "shopify_product.csv"
        ],
        "linkedin": [
            "linkedinads_ad_analytics_by_creative.csv",
            "linkedinads_campaign_history.csv",
            "linkedinads_creative_history.csv",
            "linkedinads_post_history.csv"
        ],
        "facebook": [
            "ad_conversion.csv",
            "fb_ad_history.csv",
            "fb_basic_ad.csv",
            "fb_basic_campaign.csv",
            "fb_campaign_actions.csv",
            "fb_daily_page_metrics_total.csv"
        ],
        "instagram": [
            "insta_media_history.csv",
            "insta_media_insights.csv",
            "insta_user_history.csv",
            "insta_user_insights.csv",
            "insta_user_lifetime_insights.csv"
        ]
    },
    "marketing_data_2": {
        # These will go into the SECOND database
        "facebook": [
            "ad_conversion.csv",
            "fb_ad_history.csv",
            "fb_basic_ad.csv",
            "fb_basic_campaign.csv",
            "fb_campaign_actions.csv",
            "fb_daily_page_metrics_total.csv"
        ],
        "instagram": [
            "insta_media_history.csv",
            "insta_media_insights.csv",
            "insta_user_history.csv",
            "insta_user_insights.csv",
            "insta_user_lifetime_insights.csv"
        ]
    },
    "ga4_analytics_data": {
        # GA4 analytics tables — table names must match exactly (no prefix)
        "google_analytics": [
            "geo.csv",
            "campaign.csv",
            "categorylabel.csv",
            "adslot.csv",
            "demochannel.csv",
            "pages.csv",
            "tech_device_category_report.csv",
            "tech_device_model_report.csv",
            "tech_platform_device_category_report.csv"
        ]
    },
    "linkedin_pages_data": {
        # LinkedIn Pages tables — table names must match exactly (no prefix)
        "linkedin_pages": [
            "organization.csv",
            "time_bound_follower_statistic.csv",
            "time_bound_share_statistic.csv",
            "time_bound_page_statistic.csv"
        ]
    }
}

def create_db_engine(database_name):
    """Creates a SQLAlchemy engine for a specific database"""
    connection_str = f"mysql+pymysql://{db_user}:{encoded_password}@{db_host}/{database_name}"
    return create_engine(connection_str)

def upload_data():
    print("--- Starting Multi-Database Upload ---")
    
    # Loop through the databases defined in the structure
    for db_name, categories in database_structure.items():
        print(f"\n📂 Switching to Database: {db_name}")
        
        try:
            # Create engine specifically for this database
            engine = create_db_engine(db_name)
            
            # Test connection
            with engine.connect() as conn:
                pass 
        except Exception as e:
            print(f"❌ Could not connect to database '{db_name}'. Does it exist? Error: {e}")
            continue

        # Loop through categories and files for this specific DB
        for category, files in categories.items():
            print(f"   --- Processing Category: {category} ---")
            for filename in files:
                file_path = os.path.join(DATA_DIR, filename)
                table_name = os.path.splitext(filename)[0]

                if os.path.exists(file_path):
                    try:
                        df = pd.read_csv(file_path)
                        
                        # Upload to the current database engine
                        df.to_sql(table_name, con=engine, if_exists='replace', index=False)
                        print(f"      ✅ Uploaded: {table_name} -> {db_name}")
                    except Exception as e:
                        print(f"      ❌ Error uploading {filename}: {e}")
                else:
                    print(f"      ⚠️ File not found: {file_path}")

    print("\n--- All Operations Complete ---")

if __name__ == "__main__":
    upload_data()