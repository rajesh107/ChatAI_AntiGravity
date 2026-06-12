"""
Reads the Facebook (FBADS) schema CSV files and applies column descriptions
as MySQL COMMENT on each column in the Facebook tenant database.

Mirrors scripts/add_ga4_column_comments.py (the Google Analytics agent's script).
Set DB_CONFIG["database"] to the Facebook tenant DB you want to annotate.
"""
import os
import csv
import pymysql
from dotenv import load_dotenv

load_dotenv()

# Credentials are read from .env (the Connector_* vars used by agent.py).
# Set FB_COMMENTS_DB to the Facebook tenant database you want to annotate
# (e.g. fb_<client>_ads_prod_<id>). Find it with: SHOW DATABASES LIKE 'fb_%';
DB_CONFIG = {
    "host": os.getenv("Connector_HOST", "localhost"),
    "port": int(os.getenv("Connector_PORT", "3306")),
    "user": os.getenv("Connector_USER", "root"),
    "password": os.getenv("Connector_PASSWORD", ""),
    "database": os.getenv("FB_COMMENTS_DB", ""),
    "charset": "utf8mb4",
}

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMAS_DIR = os.path.join(BASE_DIR, "schemas")

TABLE_CSV_MAP = {
    "basic_ad":                 "fb_basic_ad_schema.csv",
    "basic_campaign":           "fb_basic_campaign_schema.csv",
    "ad_history":               "fb_ad_history_schema.csv",
    "ad_conversion":            "fb_ad_conversion_schema.csv",
    "basic_campaign_actions":   "fb_basic_campaign_actions_schema.csv",
    "daily_page_metrics_total": "fb_daily_page_metrics_total_schema.csv",
    "campaign_history":         "fb_campaign_history_schema.csv",
}

def load_descriptions(csv_path):
    """Returns {column_name: description} from a schema CSV."""
    descriptions = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            descriptions[row["column_name"].strip()] = row["description"].strip()
    return descriptions

def get_column_defs(cur, table):
    """Returns {col_name: (data_type, is_nullable)} from SHOW FULL COLUMNS."""
    cur.execute(f"SHOW FULL COLUMNS FROM `{table}`")
    cols = {}
    for row in cur.fetchall():
        col_name   = row[0]
        data_type  = row[1]
        nullable   = row[3]   # YES / NO
        cols[col_name] = (data_type, nullable)
    return cols

def apply_comments(conn, table, col_defs, descriptions):
    cur = conn.cursor()
    applied = 0
    skipped = 0

    for col_name, (data_type, nullable) in col_defs.items():
        desc = descriptions.get(col_name)
        if not desc:
            print(f"    [SKIP] {col_name} — no description in CSV")
            skipped += 1
            continue

        null_clause = "NOT NULL" if nullable == "NO" else "NULL"
        safe_desc   = desc.replace("'", "\\'")

        sql = (
            f"ALTER TABLE `{table}` "
            f"MODIFY COLUMN `{col_name}` {data_type} {null_clause} "
            f"COMMENT '{safe_desc}'"
        )
        try:
            cur.execute(sql)
            print(f"    [OK]   {col_name}")
            applied += 1
        except Exception as e:
            print(f"    [ERR]  {col_name}: {e}")

    conn.commit()
    print(f"  => {applied} comments applied, {skipped} skipped\n")

def main():
    if not DB_CONFIG["database"]:
        raise SystemExit(
            "Set FB_COMMENTS_DB to the Facebook tenant database name "
            "(e.g. FB_COMMENTS_DB=fb_117_ads_prod). Find it with: SHOW DATABASES LIKE 'fb_%';"
        )

    print("Connecting to MySQL...")
    conn = pymysql.connect(**DB_CONFIG)
    print("Connected.\n")

    cur = conn.cursor()

    for table, csv_file in TABLE_CSV_MAP.items():
        csv_path = os.path.join(SCHEMAS_DIR, csv_file)
        print(f"=== Table: {table} ===")

        if not os.path.exists(csv_path):
            print(f"  [MISSING] CSV not found: {csv_path}\n")
            continue

        descriptions = load_descriptions(csv_path)
        col_defs     = get_column_defs(cur, table)
        apply_comments(conn, table, col_defs, descriptions)

    conn.close()
    print("Done.")

if __name__ == "__main__":
    main()
