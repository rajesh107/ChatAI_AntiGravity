import pymysql
from datetime import date, timedelta

yesterday = (date.today() - timedelta(days=1)).strftime('%Y-%m-%d')
print(f"Yesterday: {yesterday}\n")

conn = pymysql.connect(
    host='3.144.243.97', port=3306,
    user='remoteroot', password='Y6A7pfEqhY3gnhHq@prod',
    database='ga4_117_analytics_prod_6383'
)
cur = conn.cursor()

# Check campaign table for yesterday
cur.execute(f"""
    SELECT first_user_campaign_name, sessions, total_users, new_users, active_users, screen_page_views, bounce_rate
    FROM campaign
    WHERE date = '{yesterday}'
""")
rows = cur.fetchall()
print(f"campaign table rows for {yesterday}:")
for r in rows:
    print(f"  {r}")

# Aggregated totals
cur.execute(f"""
    SELECT SUM(sessions), SUM(total_users), SUM(new_users), SUM(active_users), SUM(screen_page_views)
    FROM campaign WHERE date = '{yesterday}'
""")
r = cur.fetchone()
print(f"\nAggregated totals: sessions={r[0]}, total_users={r[1]}, new_users={r[2]}, active_users={r[3]}, page_views={r[4]}")

# Check geo table too
cur.execute(f"SELECT SUM(total_users), SUM(sessions) FROM geo WHERE date = '{yesterday}'")
r = cur.fetchone()
print(f"\ngeo table totals: total_users={r[0]}, sessions={r[1]}")

conn.close()
