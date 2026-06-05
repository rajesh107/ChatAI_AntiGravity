import pymysql

conn = pymysql.connect(
    host='3.144.243.97', port=3306,
    user='remoteroot', password='Y6A7pfEqhY3gnhHq@prod',
    database='ga4_117_analytics_prod_6383'
)
cur = conn.cursor()

cur.execute("""
    SELECT first_user_campaign_name,
           SUM(sessions)      AS sessions,
           SUM(total_users)   AS total_users,
           SUM(new_users)     AS new_users,
           SUM(transactions)  AS transactions
    FROM campaign
    WHERE date >= '2026-05-25' AND date <= '2026-05-31'
      AND first_user_campaign_name IS NOT NULL
    GROUP BY first_user_campaign_name
    ORDER BY transactions DESC, total_users DESC
""")
rows = cur.fetchall()
print("campaign | sessions | total_users | new_users | transactions")
for r in rows:
    print(r)

conn.close()
