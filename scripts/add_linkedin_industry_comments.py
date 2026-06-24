"""Add column comments to industry, followers_by_industry, page_statistic_by_geo tables."""
import pymysql, os
from dotenv import load_dotenv
load_dotenv()

TABLES = {
    "industry": {
        "id":               "Numeric LinkedIn industry ID. Primary key. Join to followers_by_industry via: followers_by_industry.industry_id = industry.id",
        "name":             "Human-readable industry name (e.g. Information Technology, Financial Services). Use for display in responses.",
        "_fivetran_synced": "Timestamp when Fivetran last synced this row. Internal metadata, never expose to users.",
    },
    "followers_by_industry": {
        "_fivetran_id":                          "Fivetran-generated unique hash ID. Primary key for deduplication. Do not use as a business key.",
        "follower_counts_organic_follower_count": "Number of organic (unpaid) followers from this industry.",
        "follower_counts_paid_follower_count":    "Number of paid (sponsored) followers from this industry.",
        "_organization_entity_urn":               "LinkedIn org URN (e.g. urn:li:organization:65015275). Join to organization: CAST(REPLACE(_organization_entity_urn, urn:li:organization:, ) AS INTEGER) = organization.id",
        "industry_id":                            "Numeric industry ID. Foreign key to industry table: followers_by_industry.industry_id = industry.id",
        "_fivetran_synced":                       "Timestamp when Fivetran last synced this row. Internal metadata, never expose to users.",
    },
    "page_statistic_by_geo": {
        "_fivetran_id":              "Fivetran-generated unique hash ID. Primary key for deduplication. Do not use as a business key.",
        "all_desktop_page_views":    "Total desktop page views across all page sections.",
        "all_mobile_page_views":     "Total mobile page views across all page sections.",
        "all_page_views":            "Total page views (desktop + mobile) across all sections.",
        "about_page_views":          "Page views for the About section (desktop + mobile).",
        "careers_page_views":        "Page views for the Careers section (desktop + mobile).",
        "products_page_views":       "Page views for the Products section (desktop + mobile).",
        "jobs_page_views":           "Page views for the Jobs section (desktop + mobile).",
        "people_page_views":         "Page views for the People section (desktop + mobile).",
        "overview_page_views":       "Page views for the Overview/Home section (desktop + mobile).",
        "life_at_page_views":        "Page views for the Life At section (desktop + mobile).",
        "insights_page_views":       "Page views for the Insights section (desktop + mobile).",
        "mobile_careers_page_views": "Mobile-only page views for the Careers section.",
        "mobile_overview_page_views":"Mobile-only page views for the Overview/Home section.",
        "mobile_jobs_page_views":    "Mobile-only page views for the Jobs section.",
        "mobile_life_at_page_views": "Mobile-only page views for the Life At section.",
        "mobile_insights_page_views":"Mobile-only page views for the Insights section.",
        "mobile_products_page_views":"Mobile-only page views for the Products section.",
        "mobile_about_page_views":   "Mobile-only page views for the About section.",
        "mobile_people_page_views":  "Mobile-only page views for the People section.",
        "desktop_insights_page_views":  "Desktop-only page views for the Insights section.",
        "desktop_careers_page_views":   "Desktop-only page views for the Careers section.",
        "desktop_life_at_page_views":   "Desktop-only page views for the Life At section.",
        "desktop_jobs_page_views":      "Desktop-only page views for the Jobs section.",
        "desktop_people_page_views":    "Desktop-only page views for the People section.",
        "desktop_about_page_views":     "Desktop-only page views for the About section.",
        "desktop_overview_page_views":  "Desktop-only page views for the Overview/Home section.",
        "desktop_products_page_views":  "Desktop-only page views for the Products section.",
        "_organization_entity_urn":  "LinkedIn org URN (e.g. urn:li:organization:65015275). Join to organization: CAST(REPLACE(_organization_entity_urn, urn:li:organization:, ) AS INTEGER) = organization.id",
        "geo_id":                    "Numeric geo region ID as string. Join to geo table: CAST(page_statistic_by_geo.geo_id AS INTEGER) = geo.id",
        "_fivetran_synced":          "Timestamp when Fivetran last synced this row. Internal metadata, never expose to users.",
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
