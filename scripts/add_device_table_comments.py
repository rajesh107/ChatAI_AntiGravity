"""
Reads the device table CSV schema files and applies column descriptions
as MySQL COMMENT on each column in ga4_117_analytics_prod_6383.
"""
import os
import csv
import pymysql

DB_CONFIG = {
    "host": "3.144.243.97",
    "port": 3306,
    "user": "remoteroot",
    "password": "Y6A7pfEqhY3gnhHq@prod",
    "database": "ga4_117_analytics_prod_6383",
    "charset": "utf8mb4",
}

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMAS_DIR = os.path.join(BASE_DIR, "schemas")

TABLE_CSV_MAP = {
    "tech_device_category_report":          "ga4_tech_device_category_schema.csv",
    "tech_device_model_report":             "ga4_tech_device_model_schema.csv",
    "tech_platform_device_category_report": "ga4_tech_platform_device_category_schema.csv",
}

def load_descriptions(csv_path):
    descriptions = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            descriptions[row["column_name"].strip()] = row["description"].strip()
    return descriptions

def get_column_defs(cur, table):
    cur.execute(f"SHOW FULL COLUMNS FROM `{table}`")
    return {row[0]: (row[1], row[3]) for row in cur.fetchall()}

def apply_comments(conn, table, col_defs, descriptions):
    cur = conn.cursor()
    applied = skipped = 0
    for col_name, (data_type, nullable) in col_defs.items():
        desc = descriptions.get(col_name)
        if not desc:
            print(f"    [SKIP] {col_name} — no description in CSV")
            skipped += 1
            continue
        null_clause = "NOT NULL" if nullable == "NO" else "NULL"
        safe_desc = desc.replace("'", "\\'")
        sql = (f"ALTER TABLE `{table}` MODIFY COLUMN `{col_name}` {data_type} "
               f"{null_clause} COMMENT '{safe_desc}'")
        try:
            cur.execute(sql)
            print(f"    [OK]   {col_name}")
            applied += 1
        except Exception as e:
            print(f"    [ERR]  {col_name}: {e}")
    conn.commit()
    print(f"  => {applied} comments applied, {skipped} skipped\n")

def main():
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
        col_defs = get_column_defs(cur, table)
        apply_comments(conn, table, col_defs, descriptions)
    conn.close()
    print("Done.")

if __name__ == "__main__":
    main()
