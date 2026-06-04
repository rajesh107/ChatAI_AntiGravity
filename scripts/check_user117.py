import pymysql

conn = pymysql.connect(
    host='3.144.243.97', port=3306,
    user='remoteroot', password='Y6A7pfEqhY3gnhHq@prod',
    database='powerbi_latest'
)
cur = conn.cursor()

# Get user 117 DB mappings
cur.execute("SELECT type, schema_name FROM fivetran_connections WHERE user_id = '117' AND status = 1")
rows = cur.fetchall()
print("User 117 databases:")
for r in rows:
    print(f"  {r[0]:15s} -> {r[1]}")

conn.close()

# For each DB, check date range in relevant tables
for db_type, schema in rows:
    try:
        c2 = pymysql.connect(
            host='3.144.243.97', port=3306,
            user='remoteroot', password='Y6A7pfEqhY3gnhHq@prod',
            database=schema
        )
        cur2 = c2.cursor()

        if db_type == 'GOOGLEADS':
            cur2.execute("SELECT MIN(date), MAX(date), COUNT(*) FROM campaign_stats WHERE date >= '2025-09-01' AND date <= '2025-09-30'")
            r = cur2.fetchone()
            print(f"\n[{schema}] campaign_stats Sept 2025: min={r[0]} max={r[1]} rows={r[2]}")

            cur2.execute("SELECT ch.name, SUM(cs.cost_micros)/1000000 AS cost, SUM(cs.clicks) AS clicks FROM campaign_stats cs JOIN campaign_history ch ON cs.id = ch.id WHERE cs.date >= '2025-09-01' AND cs.date <= '2025-09-30' GROUP BY ch.name LIMIT 5")
            print("  Top campaigns:")
            for row in cur2.fetchall():
                print(f"    {row}")

        elif db_type == 'GA':
            cur2.execute("SELECT MIN(date), MAX(date), COUNT(*) FROM campaign WHERE date >= '2025-09-01' AND date <= '2025-09-30'")
            r = cur2.fetchone()
            print(f"\n[{schema}] GA4 campaign Sept 2025: min={r[0]} max={r[1]} rows={r[2]}")

            cur2.execute("SELECT MIN(date), MAX(date) FROM campaign")
            r = cur2.fetchone()
            print(f"  Full date range in campaign table: {r[0]} to {r[1]}")

        c2.close()
    except Exception as e:
        print(f"  Error checking {schema}: {e}")
