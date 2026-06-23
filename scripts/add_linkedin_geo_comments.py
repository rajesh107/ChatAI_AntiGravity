"""Add column comments to linkedin_117_company_pages_prod_6937 geo tables."""
import pymysql, os
from dotenv import load_dotenv
load_dotenv()

TABLES = {
    "geo": {
        "id":               "Numeric LinkedIn geo/region ID. Primary key. Join to followers_by_geo via: CAST(followers_by_geo.geo AS UNSIGNED) = geo.id",
        "value":            "Human-readable geographic region name (e.g. Greater Boston, Greater Chicago Area). Use for display in responses.",
        "_fivetran_synced": "Timestamp when Fivetran last synced this row. Internal metadata, never expose to users.",
    },
    "followers_by_geo": {
        "_fivetran_id":                          "Fivetran-generated unique hash ID. Primary key for deduplication. Do not use as a business key.",
        "follower_counts_organic_follower_count": "Number of organic (unpaid) followers from this geographic region.",
        "follower_counts_paid_follower_count":    "Number of paid (sponsored) followers from this geographic region.",
        "_organization_entity_urn":               "LinkedIn org URN (e.g. urn:li:organization:65015275). Join to organization: CAST(REPLACE(_organization_entity_urn, urn:li:organization:, ) AS UNSIGNED) = organization.id",
        "geo":                                   "Numeric geo region ID as string. Join to geo table: CAST(geo AS UNSIGNED) = geo.id",
        "_fivetran_synced":                      "Timestamp when Fivetran last synced this row. Internal metadata, never expose to users.",
    }
}

conn = pymysql.connect(
    host=os.getenv("Connector_HOST"),
    user=os.getenv("Connector_USER"),
    password=os.getenv("Connector_PASSWORD"),
    port=int(os.getenv("Connector_PORT", 3306)),
    database="linkedin_117_company_pages_prod_6937"
)
cur = conn.cursor()

total_ok = 0
total_all = 0

for table_name, comments in TABLES.items():
    print(f"\n=== {table_name} ===")
    cur.execute(f"SHOW FULL COLUMNS FROM `{table_name}`")
    columns = {row[0]: row for row in cur.fetchall()}

    for col, comment in comments.items():
        total_all += 1
        if col not in columns:
            print(f"  [SKIP] Column not found: {col}")
            continue
        row = columns[col]
        col_type    = row[1]
        is_nullable = "NULL" if row[3] == "YES" else "NOT NULL"
        default_val = f"DEFAULT '{row[5]}'" if row[5] is not None else ""
        safe_comment = comment.replace("'", "''")
        try:
            sql = f"ALTER TABLE `{table_name}` MODIFY COLUMN `{col}` {col_type} {is_nullable} {default_val} COMMENT '{safe_comment}'"
            cur.execute(sql)
            print(f"  [OK] {col}")
            total_ok += 1
        except Exception as e:
            print(f"  [ERR] {col}: {e}")

conn.commit()
conn.close()
print(f"\nDone: {total_ok}/{total_all} columns commented.")
