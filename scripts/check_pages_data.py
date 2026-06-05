import pymysql

conn = pymysql.connect(
    host='3.144.243.97', port=3306,
    user='remoteroot', password='Y6A7pfEqhY3gnhHq@prod',
    database='ga4_117_analytics_prod_6383'
)
cur = conn.cursor()

cur.execute("""
    SELECT
        COALESCE(NULLIF(unified_screen_name, ''), unified_page_path_screen) AS page_name,
        SUM(sessions)         AS sessions,
        SUM(engaged_sessions) AS engaged_sessions,
        SUM(total_users)      AS total_users,
        SUM(new_users)        AS new_users,
        SUM(screen_page_views) AS page_views,
        ROUND(AVG(bounce_rate) * 100, 2) AS bounce_rate_pct,
        ROUND(AVG(average_session_duration), 1) AS avg_duration_sec
    FROM pages
    GROUP BY page_name
    ORDER BY sessions DESC
    LIMIT 10
""")
rows = cur.fetchall()
print(f"{'Page Name':<55} {'Sessions':>8} {'Engaged':>8} {'Users':>7} {'Views':>7}")
print("-" * 90)
for r in rows:
    print(f"{str(r[0])[:54]:<55} {r[1]:>8} {r[2]:>8} {r[3]:>7} {r[5]:>7}")

conn.close()
