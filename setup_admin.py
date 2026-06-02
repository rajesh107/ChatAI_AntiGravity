import os
import pymysql
from dotenv import load_dotenv

load_dotenv()

# Admin DB Credentials (usually root, to create the mapping table)
DB_USER = os.getenv("MYSQL_USER", "root")
DB_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
DB_HOST = os.getenv("MYSQL_HOST", "localhost")
DB_PORT = int(os.getenv("MYSQL_PORT", 3306))
ADMIN_DB_NAME = "marketing_admin" # We will create this DB to hold mappings

def setup_admin_db():
    # Connect to MySQL Server (no specific DB yet)
    conn = pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        port=DB_PORT,
        cursorclass=pymysql.cursors.DictCursor
    )
    
    try:
        with conn.cursor() as cursor:
            # 1. Create Admin Database
            print(f"Creating/Checking database '{ADMIN_DB_NAME}'...")
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {ADMIN_DB_NAME}")
            cursor.execute(f"USE {ADMIN_DB_NAME}")
            
            # 2. Create Mapping Table
            print("Creating 'user_db_mapping' table...")
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS user_db_mapping (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(255) NOT NULL UNIQUE,
                database_name VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
            cursor.execute(create_table_sql)
            
            # 3. Insert Dummy Data (Seed Data)
            # This simulates your existing setup
            print("Seeding initial users...")
            users = [
                ("admin", "marketing_data"),
                ("client_a", "marketing_data"),
                ("client_b", "marketing_data_2")
            ]
            
            for user, db in users:
                cursor.execute(
                    "INSERT IGNORE INTO user_db_mapping (username, database_name) VALUES (%s, %s)",
                    (user, db)
                )
            
            conn.commit()
            print("✅ Admin DB and Mapping Table setup successfully.")
            
    except Exception as e:
        print(f"❌ Error setting up admin DB: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    setup_admin_db()

