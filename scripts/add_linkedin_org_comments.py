"""Add column comments to linkedin_117_company_pages_prod_6937.organization table."""
import pymysql, os
from dotenv import load_dotenv
load_dotenv()

COMMENTS = {
    "id":                           "Numeric LinkedIn organization ID. Join to other tables via: CAST(REPLACE(organization_entity, 'urn:li:organization:', '') AS UNSIGNED) = id",
    "localized_name":               "Human-readable company/page name (e.g. 'BlueHippo', 'Ask Bee'). Use this for display and name-based filtering.",
    "vanity_name":                  "LinkedIn URL slug (e.g. 'usbluehippo'). Used in linkedin.com/company/<vanity_name>.",
    "localized_description":        "Company description text in the default locale.",
    "localized_website":            "Company website URL.",
    "organization_type":            "Legal entity type: PRIVATELY_HELD, SELF_EMPLOYED, etc.",
    "primary_organization_type":    "Primary category type (usually NONE or a sector value).",
    "organization_status":          "Active/inactive status of the organization on LinkedIn.",
    "staff_count_range":            "Employee count band: SIZE_1, SIZE_2_TO_10, SIZE_11_TO_50, SIZE_51_TO_200, etc.",
    "founded_on_year":              "Year the organization was founded.",
    "founded_on_month":             "Month the organization was founded.",
    "founded_on_day":               "Day the organization was founded.",
    "default_locale_country":       "Country code of the default locale (e.g. US).",
    "default_locale_language":      "Language code of the default locale (e.g. en).",
    "cover_photo_v_2_cropped":      "LinkedIn CDN URN for the cropped cover photo. Internal asset reference.",
    "cover_photo_v_2_original":     "LinkedIn CDN URN for the original cover photo. Internal asset reference.",
    "logo_v_2_cropped":             "LinkedIn CDN URN for the cropped logo. Internal asset reference.",
    "logo_v_2_original":            "LinkedIn CDN URN for the original logo. Internal asset reference.",
    "parent_relationship_parent_id":"Numeric ID of the parent organization (if this is a subsidiary).",
    "parent_relationship_type":     "Relationship type to parent org (e.g. DIVISION).",
    "parent_relationship_status":   "Status of the parent relationship.",
    "version_tag":                  "Internal LinkedIn version tag for this record.",
    "_fivetran_synced":             "Timestamp when Fivetran last synced this row. Internal metadata, never expose to users.",
}

conn = pymysql.connect(
    host=os.getenv("Connector_HOST"),
    user=os.getenv("Connector_USER"),
    password=os.getenv("Connector_PASSWORD"),
    port=int(os.getenv("Connector_PORT", 3306)),
    database="linkedin_117_company_pages_prod_6937"
)
cur = conn.cursor()

# Get current column definitions
cur.execute("SHOW FULL COLUMNS FROM organization")
columns = {row[0]: row for row in cur.fetchall()}

success = 0
for col, comment in COMMENTS.items():
    if col not in columns:
        print(f"  [SKIP] Column not found: {col}")
        continue
    row = columns[col]
    col_type    = row[1]
    is_nullable = "NULL" if row[3] == "YES" else "NOT NULL"
    default_val = f"DEFAULT '{row[5]}'" if row[5] is not None else ""
    try:
        sql = f"ALTER TABLE organization MODIFY COLUMN `{col}` {col_type} {is_nullable} {default_val} COMMENT '{comment.replace(chr(39), chr(39)+chr(39))}'"
        cur.execute(sql)
        print(f"  [OK] {col}")
        success += 1
    except Exception as e:
        print(f"  [ERR] {col}: {e}")

conn.commit()
conn.close()
print(f"\nDone: {success}/{len(COMMENTS)} columns commented.")
