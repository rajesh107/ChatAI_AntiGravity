import pandas as pd
import numpy as np
from sqlalchemy import create_engine, inspect
from sqlalchemy.types import Integer, BigInteger, Date, DateTime, Boolean, DECIMAL, String, Text

# Configuration: Define Types for every Table
TABLE_CONFIGS = {
    # =========================================================
    # --- SHARED / UNIFIED TABLES (Exist across platforms) ---
    # =========================================================
    # MERGED definition for Google, LinkedIn, and Facebook
    "campaign_history": {
        "dates": [
            # Google
            "updated_at", "start_date", "end_date",
            # LinkedIn
            "created_time", "last_modified_time", "run_schedule_start", "run_schedule_end",
            # Facebook
            "updated_time", "start_time", "stop_time", "last_budget_toggling_time"
        ],
        "ids": [
            # Google
            "id", "customer_id", "base_campaign_id",
            # LinkedIn
            "account_id", "campaign_group_id",
            # Facebook
            "source_campaign_id", "boosted_object_id", "topline_id",
            "promoted_object_application_id", "promoted_object_custom_conversion_id",
            "promoted_object_event_id", "promoted_object_offer_id",
            "promoted_object_offline_conversion_data_set_id", "promoted_object_page_id",
            "promoted_object_pixel_id", "promoted_object_place_page_set_id",
            "promoted_object_product_catalog_id", "promoted_object_product_set_id"
        ],
        "bools": [
            # Google
            "biddable",
            # LinkedIn
            "offsite_delivery_enabled", "audience_expansion_enabled",
            # Facebook
            "budget_rebalance_flag", "can_create_brand_lift_study", "can_use_spend_cap",
            "is_skadnetwork_attribution"
        ],
        "floats": [
            # Google
            "optimization_score",
            # LinkedIn
            "daily_budget_amount", "unit_cost_amount",
            # Facebook
            "budget_remaining", "daily_budget", "lifetime_budget", "spend_cap"
        ],
        "sql_types": {
            "id": BigInteger,
            "account_id": BigInteger,
            "campaign_id": String(255),  # Using String to be safe across platforms
            "updated_at": Date,          # Google format
            "created_time": DateTime,    # FB/LinkedIn format
            "start_time": DateTime,
            "stop_time": DateTime,
            "daily_budget": DECIMAL(15, 2),
            "lifetime_budget": DECIMAL(15, 2),
            "budget_remaining": DECIMAL(15, 2),
            "spend_cap": DECIMAL(15, 2)
        }
    },

    # ==========================================
    # --- GOOGLE ADS UNIQUE ---
    # ==========================================
    "campaign_stats": {
        "dates": ["date"],
        "ids": ["id", "customer_id", "base_campaign"],
        "floats": ["conversions", "conversions_value", "cost_micros", "active_view_viewability"],
        "sql_types": {
            "id": BigInteger,
            "date": Date,
            "conversions": DECIMAL(10, 2),
            "conversions_value": DECIMAL(10, 2),
            "cost_micros": BigInteger
        }
    },
    "campaign_conversion_goal_history": {
        "dates": ["updated_at"],
        "ids": ["campaign_id", "customer_id", "id"],
        "bools": ["biddable"],
        "sql_types": {
            "id": BigInteger,
            "campaign_id": BigInteger,
            "updated_at": DateTime
        }
    },

    # ==========================================
    # --- SHOPIFY ---
    # ==========================================
    "order": {
        "dates": ["created_at", "updated_at", "cancelled_at", "closed_at", "processed_at"],
        "ids": ["id", "user_id", "location_id", "customer_id"],
        "bools": ["taxes_included", "test", "confirmed", "buyer_accepts_marketing"],
        "floats": ["total_price", "subtotal_price", "total_tax", "total_discounts"],
        "sql_types": {
            "id": BigInteger,
            "created_at": DateTime,
            "total_price": DECIMAL(10, 2)
        }
    },
    "order_line": {
        "ids": ["id", "order_id", "product_id", "variant_id"],
        "bools": ["gift_card", "requires_shipping", "taxable", "product_exists"],
        "floats": ["price", "total_discount", "pre_tax_price"],
        "sql_types": {
            "id": BigInteger,
            "order_id": BigInteger,
            "price": DECIMAL(10, 2)
        }
    },
    "order_line_refund": {
        "ids": ["id", "refund_id", "order_line_id", "location_id"],
        "floats": ["quantity", "subtotal", "total_tax"],
        "sql_types": {
            "id": BigInteger,
            "refund_id": BigInteger,
            "subtotal": DECIMAL(10, 2)
        }
    },
    "product": {
        "dates": ["created_at", "updated_at", "published_at"],
        "ids": ["id"],
        "bools": ["has_out_of_stock_variants", "tracks_inventory"],
        "sql_types": {
            "id": BigInteger,
            "created_at": DateTime,
            "body_html": Text
        }
    },

    # ==========================================
    # --- LINKEDIN ADS UNIQUE ---
    # ==========================================
    "ad_analytics_by_creative": {
        "dates": ["day"],
        "ids": ["creative_id", "campaign_id"],
        "floats": ["cost_in_usd", "cost_in_local_currency", "impressions", "clicks", "total_engagements"],
        "sql_types": {
            "creative_id": BigInteger,
            "day": Date,
            "cost_in_usd": DECIMAL(10, 2)
        }
    },
    "creative_history": {
        "dates": ["created_time", "last_modified_time"],
        "ids": ["id", "campaign_id", "account_id"],
        "sql_types": {
            "id": BigInteger,
            "campaign_id": BigInteger,
            "created_time": DateTime,
            "click_uri": Text
        }
    },
    "post_history": {
        "dates": ["created_time", "last_modified_time"],
        "ids": ["id", "author_id"],
        "sql_types": {
            "id": String(255),
            "created_time": DateTime,
            "message": Text
        }
    },

    # ==========================================
    # --- FACEBOOK ADS UNIQUE ---
    # ==========================================
    "basic_campaign": {
        "dates": ["date"],
        "ids": ["campaign_id", "account_id"],
        "floats": ["spend", "cpc", "cpm", "ctr", "frequency", "reach", "impressions"],
        "sql_types": {
            "date": Date,
            "spend": DECIMAL(10, 2),
            "campaign_id": String(255)
        }
    },
    "basic_ad": {
        "dates": ["date"],
        "ids": ["ad_id", "account_id", "campaign_id", "adset_id"],
        "floats": ["spend", "cpc", "cpm", "ctr", "reach", "impressions"],
        "sql_types": {
            "date": Date,
            "spend": DECIMAL(10, 2),
            "ad_id": String(255)
        }
    },
    "ad_conversion": {
        "dates": ["date"],
        "ids": ["ad_id"],
        "floats": ["value", "1d_view", "1d_click", "7d_click", "28d_click"],
        "sql_types": {
            "ad_id": String(255),
            "value": DECIMAL(10, 2)
        }
    },
    "ad_history": {
        "dates": ["created_time", "updated_time"],
        "ids": ["id", "account_id", "campaign_id", "ad_set_id"],
        "bools": ["is_active_status"],
        "sql_types": {
            "id": String(255),
            "created_time": DateTime,
            "name": String(255)
        }
    },
    "basic_campaign_actions": {
        "dates": ["date"],
        "ids": ["campaign_id"],
        "floats": ["value", "1d_view", "1d_click"],
        "sql_types": {
            "campaign_id": String(255),
            "value": DECIMAL(10, 2),
            "action_type": String(100)
        }
    },
    "daily_page_metrics_total": {
        "dates": ["date"],
        "ids": ["page_id"],
        "floats": ["page_impressions", "page_engaged_users", "page_consumptions"],
        "sql_types": {
            "page_id": String(255),
            "date": Date
        }
    },

    # ==========================================
    # --- INSTAGRAM ---
    # ==========================================
    "user_insights": {
        "dates": ["date"],
        "ids": ["id"], 
        "floats": ["impressions", "reach", "follower_count", "profile_views"],
        "sql_types": {
            "id": BigInteger,
            "date": Date
        }
    },
    "user_history": {
        "ids": ["id"],
        "sql_types": {
            "id": BigInteger,
            "username": String(255),
            "website": Text,
            "biography": Text
        }
    },
    "media_history": {
        "dates": ["created_time"],
        "ids": ["id", "user_id", "ig_id", "owner_id"],
        "bools": ["is_story", "is_comment_enabled"],
        "sql_types": {
            "id": BigInteger,
            "created_time": DateTime,
            "user_id": BigInteger,
            "caption": Text
        }
    },
    "media_insights": {
        "dates": ["date"],
        "ids": ["id", "media_id"],
        "floats": ["engagement", "impressions", "reach", "saved"],
        "sql_types": {
            "id": BigInteger,
            "media_id": BigInteger
        }
    },
    "user_lifetime_insights": {
        "dates": ["date"],
        "ids": ["id"],
        "floats": ["value"],
        "sql_types": {
            "id": BigInteger,
            "date": Date,
            "metric": String(100),
            "value": DECIMAL(10, 2)
        }
    },

    # ==========================================
    # --- GOOGLE ANALYTICS (GA4) ---
    # ==========================================
    "geo": {
        "dates": ["date", "_fivetran_synced"],
        "ids": [],
        "floats": ["bounce_rate", "average_session_duration"],
        "sql_types": {
            "date": Date,
            "property": String(256),
            "_fivetran_id": String(256),
            "transactions": BigInteger,
            "engaged_sessions": BigInteger,
            "total_users": BigInteger,
            "active_users": BigInteger,
            "new_users": BigInteger,
            "sessions": BigInteger,
            "screen_page_views": BigInteger,
            "bounce_rate": DECIMAL(10, 6),
            "average_session_duration": DECIMAL(15, 6)
        }
    },
    "campaign": {
        "dates": ["date", "_fivetran_synced"],
        "ids": [],
        "floats": ["bounce_rate", "average_session_duration"],
        "sql_types": {
            "date": Date,
            "property": String(256),
            "_fivetran_id": String(256),
            "advertiser_ad_clicks": BigInteger,
            "sessions": BigInteger,
            "engaged_sessions": BigInteger,
            "active_users": BigInteger,
            "total_users": BigInteger,
            "new_users": BigInteger,
            "screen_page_views": BigInteger,
            "advertiser_ad_cost": BigInteger,
            "bounce_rate": DECIMAL(10, 6),
            "average_session_duration": DECIMAL(15, 6)
        }
    },
    "categorylabel": {
        "dates": ["date", "_fivetran_synced"],
        "ids": [],
        "floats": ["bounce_rate", "average_session_duration", "event_value"],
        "sql_types": {
            "date": Date,
            "property": String(256),
            "_fivetran_id": String(256),
            "sessions": BigInteger,
            "engaged_sessions": BigInteger,
            "event_count": BigInteger,
            "active_users": BigInteger,
            "total_users": BigInteger,
            "new_users": BigInteger,
            "screen_page_views": BigInteger,
            "bounce_rate": DECIMAL(10, 6),
            "average_session_duration": DECIMAL(15, 6),
            "event_value": DECIMAL(15, 6)
        }
    },
    "adslot": {
        "dates": ["date", "_fivetran_synced"],
        "ids": [],
        "floats": ["bounce_rate", "average_session_duration"],
        "sql_types": {
            "date": Date,
            "property": String(256),
            "_fivetran_id": String(256),
            "transactions": BigInteger,
            "engaged_sessions": BigInteger,
            "total_users": BigInteger,
            "active_users": BigInteger,
            "new_users": BigInteger,
            "sessions": BigInteger,
            "screen_page_views": BigInteger,
            "bounce_rate": DECIMAL(10, 6),
            "average_session_duration": DECIMAL(15, 6)
        }
    },
    "demochannel": {
        "dates": ["date", "_fivetran_synced"],
        "ids": [],
        "floats": ["bounce_rate", "average_session_duration"],
        "sql_types": {
            "date": Date,
            "property": String(256),
            "_fivetran_id": String(256),
            "transactions": BigInteger,
            "engaged_sessions": BigInteger,
            "total_users": BigInteger,
            "active_users": BigInteger,
            "new_users": BigInteger,
            "sessions": BigInteger,
            "screen_page_views": BigInteger,
            "bounce_rate": DECIMAL(10, 6),
            "average_session_duration": DECIMAL(15, 6)
        }
    },
    "pages": {
        "dates": ["date", "_fivetran_synced"],
        "ids": [],
        "floats": ["bounce_rate", "average_session_duration"],
        "sql_types": {
            "date": Date,
            "property": String(256),
            "_fivetran_id": String(256),
            "transactions": BigInteger,
            "engaged_sessions": BigInteger,
            "total_users": BigInteger,
            "active_users": BigInteger,
            "new_users": BigInteger,
            "sessions": BigInteger,
            "screen_page_views": BigInteger,
            "bounce_rate": DECIMAL(10, 6),
            "average_session_duration": DECIMAL(15, 6)
        }
    },

    # ==========================================
    # --- GOOGLE ANALYTICS (GA4) DEVICE ---
    # ==========================================
    "tech_device_category_report": {
        "dates": ["date", "_fivetran_synced"],
        "ids": [],
        "floats": ["engagement_rate", "key_events"],
        "sql_types": {
            "date": Date,
            "property": String(256),
            "_fivetran_id": String(256),
            "total_users": BigInteger,
            "new_users": BigInteger,
            "engaged_sessions": BigInteger,
            "event_count": BigInteger,
            "total_revenue": BigInteger,
            "engagement_rate": DECIMAL(10, 6),
            "key_events": DECIMAL(10, 2)
        }
    },
    "tech_device_model_report": {
        "dates": ["date", "_fivetran_synced"],
        "ids": [],
        "floats": ["engagement_rate", "key_events"],
        "sql_types": {
            "date": Date,
            "property": String(256),
            "_fivetran_id": String(256),
            "total_users": BigInteger,
            "new_users": BigInteger,
            "engaged_sessions": BigInteger,
            "event_count": BigInteger,
            "total_revenue": BigInteger,
            "engagement_rate": DECIMAL(10, 6),
            "key_events": DECIMAL(10, 2)
        }
    },
    "tech_platform_device_category_report": {
        "dates": ["date", "_fivetran_synced"],
        "ids": [],
        "floats": ["engagement_rate", "key_events"],
        "sql_types": {
            "date": Date,
            "property": String(256),
            "_fivetran_id": String(256),
            "total_users": BigInteger,
            "new_users": BigInteger,
            "engaged_sessions": BigInteger,
            "event_count": BigInteger,
            "total_revenue": BigInteger,
            "engagement_rate": DECIMAL(10, 6),
            "key_events": DECIMAL(10, 2)
        }
    },

    # ==========================================
    # --- LINKEDIN PAGES ---
    # ==========================================
    "organization": {
        "dates": ["_fivetran_synced"],
        "ids": ["id", "parent_relationship_parent_id"],
        "floats": [],
        "sql_types": {
            "id": BigInteger,
            "localized_name": String(512),
            "vanity_name": String(256),
            "localized_description": Text,
            "localized_website": String(512),
            "organization_type": String(128),
            "primary_organization_type": String(128),
            "organization_status": String(64),
            "staff_count_range": String(64),
            "founded_on_year": Integer,
            "founded_on_month": Integer,
            "founded_on_day": Integer,
            "default_locale_country": String(16),
            "default_locale_language": String(16),
            "parent_relationship_parent_id": BigInteger,
            "parent_relationship_type": String(64),
            "parent_relationship_status": String(64),
            "version_tag": String(64)
        }
    },
    "geo": {
        "dates": ["_fivetran_synced"],
        "ids": ["id"],
        "floats": [],
        "sql_types": {
            "id":               BigInteger,
            "value":            String(512),
        }
    },
    "followers_by_geo": {
        "dates": ["_fivetran_synced"],
        "ids": [],
        "floats": [],
        "sql_types": {
            "_fivetran_id":                          String(256),
            "follower_counts_organic_follower_count": Integer,
            "follower_counts_paid_follower_count":    Integer,
            "_organization_entity_urn":               Text,
            "geo":                                   String(64),
        }
    },
    "time_bound_follower_statistic": {
        "dates": ["day", "_fivetran_synced"],
        "ids": [],
        "floats": [],
        "sql_types": {
            "_fivetran_id": String(256),
            "day": DateTime,
            "follower_gains_organic_follower_gain": Integer,
            "follower_gains_paid_follower_gain": Integer
        }
    },
    "time_bound_share_statistic": {
        "dates": ["day", "_fivetran_synced"],
        "ids": [],
        "floats": ["engagement"],
        "sql_types": {
            "_fivetran_id": String(256),
            "day": DateTime,
            "engagement": DECIMAL(15, 8),
            "unique_impressions_count": Integer,
            "share_count": Integer,
            "click_count": Integer,
            "like_count": Integer,
            "impression_count": Integer,
            "comment_count": Integer
        }
    },
    "time_bound_page_statistic": {
        "dates": ["day", "_fivetran_synced"],
        "ids": [],
        "floats": [],
        "sql_types": {
            "_fivetran_id": String(256),
            "day": DateTime,
            "all_page_views": Integer,
            "all_unique_page_views": Integer,
            "all_desktop_page_views": Integer,
            "all_mobile_page_views": Integer,
            "overview_page_views": Integer,
            "about_page_views": Integer,
            "careers_page_views": Integer,
            "jobs_page_views": Integer,
            "people_page_views": Integer,
            "products_page_views": Integer,
            "life_at_page_views": Integer,
            "insights_page_views": Integer
        }
    }
}

def clean_and_load_data(df: pd.DataFrame, table_name: str, engine=None, if_exists='replace', return_only=False):
    """
    Refactored to support Caching.
    If return_only=True: Returns (cleaned_df, dtype_mapping) and DOES NOT write to DB.
    If return_only=False: Writes to DB immediately (Old behavior).
    """
    
    # Check if we have config for this table
    if table_name not in TABLE_CONFIGS:
        if return_only:
            return df, {}
        try:
            df.to_sql(table_name, engine, if_exists=if_exists, index=False)
        except Exception as e:
            print(f"         ❌ [ETL] Raw write failed: {e}")
        return

    config = TABLE_CONFIGS[table_name]
    
    try:
        # --- B. Transform: Clean Data in Memory ---
        if "dates" in config:
            for col in config["dates"]:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce')

        if "ids" in config:
            for col in config["ids"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').astype("Int64")

        if "bools" in config:
            for col in config["bools"]:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.lower().map({
                        '1': True, 'true': True, 'yes': True,
                        '0': False, 'false': False, 'no': False
                    }).astype("boolean")

        if "floats" in config:
            for col in config["floats"]:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.replace(r'[$,]', '', regex=True)
                    df[col] = pd.to_numeric(df[col], errors='coerce')

        dtype_mapping = config.get("sql_types", {})

        # --- Return for Caching if requested ---
        if return_only:
            return df, dtype_mapping

        # --- C. Load: Write Clean Data to Engine ---
        df.to_sql(
            name=table_name,
            con=engine,
            if_exists=if_exists,
            index=False,
            dtype=dtype_mapping,
            chunksize=1000
        )
        
    except Exception as e:
        print(f"         🔴 [ETL ERROR] Failed to process {table_name}: {e}")
        raise e