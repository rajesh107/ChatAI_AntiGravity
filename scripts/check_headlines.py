import pymysql
conn = pymysql.connect(
    host='3.144.243.97', port=3306,
    user='remoteroot', password='Y6A7pfEqhY3gnhHq@prod',
    database='google_ads_280_prod_7097'
)
cur = conn.cursor()
cur.execute("""
    SELECT ch.name, agh.name, rsa.headlines, rsa.descriptions, rsa._fivetran_active
    FROM responsive_search_ad_history rsa
    JOIN ad_group_history agh ON rsa.ad_group_id = agh.id
    JOIN campaign_history ch ON agh.campaign_id = ch.id
    WHERE ch.name LIKE '%WW_FOODEVENTS%'
    LIMIT 3
""")
rows = cur.fetchall()
print("Sample RSA rows for WW_FOODEVENTS:")
for r in rows:
    print(r)
conn.close()
