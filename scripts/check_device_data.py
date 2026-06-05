import pymysql

# Check GA4 DB for device columns
conn = pymysql.connect(
    host='3.144.243.97', port=3306,
    user='remoteroot', password='Y6A7pfEqhY3gnhHq@prod',
    database='ga4_117_analytics_prod_6383'
)
cur = conn.cursor()

# List all tables
cur.execute("SHOW TABLES")
tables = [r[0] for r in cur.fetchall()]
print(f"GA4 tables ({len(tables)} total):")

# Search for device columns
device_cols = []
for table in tables:
    cur.execute(f"SHOW COLUMNS FROM `{table}`")
    cols = cur.fetchall()
    for col in cols:
        if 'device' in col[0].lower():
            device_cols.append((table, col[0], col[1]))

if device_cols:
    print("\nFound device columns:")
    for t, c, dt in device_cols:
        print(f"  {t}.{c} ({dt})")
else:
    print("\nNo device columns found in any GA4 table.")

# Also check if any table name contains 'device'
device_tables = [t for t in tables if 'device' in t.lower()]
if device_tables:
    print(f"\nTables with 'device' in name: {device_tables}")
else:
    print("No tables with 'device' in name.")

conn.close()
