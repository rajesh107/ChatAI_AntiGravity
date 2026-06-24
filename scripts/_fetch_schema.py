import pymysql, os
from dotenv import load_dotenv
load_dotenv()

conn = pymysql.connect(
    host=os.getenv("Connector_HOST"),
    user=os.getenv("Connector_USER"),
    password=os.getenv("Connector_PASSWORD"),
    port=int(os.getenv("Connector_PORT", 3306)),
    database="linkedin_117_company_pages_prod_6937"
)
cur = conn.cursor()

for table in ["industry", "followers_by_industry", "page_statistic_by_geo"]:
    print(f"\n=== {table} ===")
    cur.execute(f"SHOW FULL COLUMNS FROM `{table}`")
    for row in cur.fetchall():
        print(f"  col={row[0]}  type={row[1]}  comment={row[8]!r}")

conn.close()
