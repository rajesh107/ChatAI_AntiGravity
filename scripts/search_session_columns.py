import pymysql

conn = pymysql.connect(
    host='3.144.243.97', port=3306,
    user='remoteroot', password='Y6A7pfEqhY3gnhHq@prod',
    database='google_ads_117_prod_4234'
)
cur = conn.cursor()

# Get all tables
cur.execute("SHOW TABLES")
tables = [r[0] for r in cur.fetchall()]
print(f"Total tables: {len(tables)}\n")

# Search every table for columns containing 'session'
found = []
for table in tables:
    cur.execute(f"SHOW COLUMNS FROM `{table}`")
    cols = cur.fetchall()
    for col in cols:
        if 'session' in col[0].lower():
            found.append((table, col[0], col[1]))

if found:
    print(f"Found {len(found)} session column(s):\n")
    for table, col, dtype in found:
        print(f"  Table: {table:55s}  Column: {col:40s}  Type: {dtype}")
else:
    print("No direct 'session' column found in any table.")

conn.close()
