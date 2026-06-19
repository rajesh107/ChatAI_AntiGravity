# Connectors Documentation
## Per-Platform Connector Reference — ChatAI AntiGravity

This document details each platform **connector** (data source + its specialist
agent): what it covers, the tables it owns, how the supervisor routes to it, and
example `/chat` request/response pairs.

All connectors are reached through the same endpoint — `POST /chat` — and differ
only in the query content and which agent the supervisor delegates to. A tenant's
active connectors come from `fivetran_connections` (rows with `status = 1`).

> **Note on responses:** the `response` text in the examples below is
> **illustrative** — actual values come from each tenant's live data. The request
> shape, routing, and `connected_platforms` values are exact.

---

## Connector Summary

| Connection type | Platform key | Agent | Domain |
|---|---|---|---|
| `GOOGLEADS` | `google_ads` | GoogleAdsAgent | Google Ads paid campaigns |
| `SHOPIFY` | `shopify` | ShopifyAgent | E-commerce orders/products |
| `LINKEDINADS` | `linkedin` | LinkedInAgent | LinkedIn paid ads |
| `LINKEDIN` | `linkedin_pages` | LinkedInPagesAgent | LinkedIn organic Company Page |
| `FBADS` | `facebook` | FacebookAdsAgent | Facebook paid ads |
| `INSTA` | `instagram` | InstagramAgent | Instagram organic content |
| `GA` | `google_analytics` | GoogleAnalyticsAgent | GA4 website/app analytics |

Common request/response envelope (all connectors):

```
POST /chat
Authorization: Bearer <jwt>
Content-Type: application/json
{ "query": "<question>", "thread_id": "<tenant>" }

→ 200 OK
{ "response": "<answer>", "thread_id": "<tenant>", "connected_platforms": [ ... ] }
```

---

## 1. Google Ads — `GOOGLEADS` → `google_ads` → GoogleAdsAgent

**Domain:** Google Ads paid-campaign metrics — campaign cost/performance, ads, ad
cost, returns, CTR, clicks.

**Tables:** `campaign_conversion_goal_history`, `campaign_history`, `campaign_stats`

**Routes when:** the query contains a Google Ads keyword
(`google`, `googleads`, `ga`, `_ga`) and asks about Google Ads metrics.
*(Note: GA4 website analytics goes to Google Analytics, not here.)*

**Example request**
```json
{ "query": "What was my Google Ads spend and CTR last month?", "thread_id": "client_1" }
```
**Example response**
```json
{
  "response": "Last month your Google Ads spend was $8,200 across 4 campaigns, with an average CTR of 3.1% and 12,400 clicks.",
  "thread_id": "client_1",
  "connected_platforms": ["google_ads"]
}
```

---

## 2. Shopify — `SHOPIFY` → `shopify` → ShopifyAgent

**Domain:** E-commerce — products, orders, customers, sales, SKU-level data, cost,
units sold, price. *(Not for ad campaigns.)*

**Tables:** `order`, `order_line`, `order_line_refund`, `product`

**Routes when:** the query contains `shopify` / `shopifyads` / `shopifyad`, or asks
about products, orders, customers, sales, SKUs, cost, or price.

**Example request**
```json
{ "query": "Top 5 best-selling products by revenue this quarter?", "thread_id": "client_1" }
```
**Example response**
```json
{
  "response": "Your top 5 products by revenue this quarter: 1) Aurora Jacket $14,200; 2) Trail Pack $9,850; 3) ...",
  "thread_id": "client_1",
  "connected_platforms": ["shopify"]
}
```

---

## 3. LinkedIn Ads — `LINKEDINADS` → `linkedin` → LinkedInAgent

**Domain:** LinkedIn **paid** ads — campaign, ad spend, impressions, clicks, CPC,
CTR, total engagements, landing-page clicks, ad performance, creatives.

**Tables:** `ad_analytics_by_creative`, `campaign_history`, `creative_history`,
`post_history`

**Routes when:** the query has **both** a LinkedIn platform keyword
(`linkedin`, `ln`, `linkedinads`, `lnads`) **and** an ads/metric keyword
(`campaign`, `spend`, `impressions`, `clicks`, `cpc`, `ctr`, `creatives`, …).
*(Organic page metrics → LinkedIn Pages connector.)*

**Example request**
```json
{ "query": "What's my LinkedIn ad campaign CPC and total spend this month?", "thread_id": "client_1" }
```
**Example response**
```json
{
  "response": "This month your LinkedIn Ads spend is $3,400 with an average CPC of $5.20 across 2 campaigns and 654 clicks.",
  "thread_id": "client_1",
  "connected_platforms": ["linkedin"]
}
```

---

## 4. LinkedIn Pages — `LINKEDIN` → `linkedin_pages` → LinkedInPagesAgent

**Domain:** LinkedIn **organic** Company Page — followers, follower growth, total/
desktop/mobile/section page views, post impressions, engagement, likes, comments,
shares.

**Tables:** `time_bound_follower_statistic`, `time_bound_share_statistic`,
`time_bound_page_statistic`
**Schemas:** `schemas/linkedin_pages_time_bound_*_schema.csv`

**Routes when:** the query has **both** a LinkedIn platform keyword **and** an
organic/pages metric keyword (`followers`, `page views`, `post impressions`,
`likes`, `comments`, `shares`, `organic`, …).
*(Paid campaigns/CPC/creatives → LinkedIn Ads connector.)*

**Example request**
```json
{ "query": "How many new LinkedIn page followers did we gain last 30 days?", "thread_id": "client_1" }
```
**Example response**
```json
{
  "response": "Your LinkedIn Company Page gained 312 new followers in the last 30 days, a 4.6% increase, for a total of 7,108.",
  "thread_id": "client_1",
  "connected_platforms": ["linkedin_pages"]
}
```

---

## 5. Facebook Ads — `FBADS` → `facebook` → FacebookAdsAgent

**Domain:** Facebook Ads — campaign cost/performance, ads, ad cost, returns, CTR,
clicks, page metrics.

**Tables:** `ad_conversion`, `ad_history`, `basic_ad`, `basic_campaign`,
`basic_campaign_actions`, `daily_page_metrics_total`, `campaign_history`
**Schemas:** `schemas/fb_*_schema.csv`

**Routes when:** the query contains `facebook` / `fb` / `fbads` / `facebookads`, or
asks about Facebook Ads metrics.

**Example request**
```json
{ "query": "Compare Facebook ad spend vs conversions for last week.", "thread_id": "client_1" }
```
**Example response**
```json
{
  "response": "Last week Facebook Ads spend was $4,280 driving 196 conversions at a $21.84 cost per conversion across 3 campaigns.",
  "thread_id": "client_1",
  "connected_platforms": ["facebook"]
}
```

---

## 6. Instagram — `INSTA` → `instagram` → InstagramAgent

**Domain:** Instagram **organic** content — posts, reach, views, comments, post
engagements, follower insights. *(Not for paid campaigns/ads.)*

**Tables:** `media_history`, `media_insights`, `user_history`, `user_insights`,
`user_lifetime_insights`

**Routes when:** the query contains `instagram` / `insta` / `ig`, or asks about
Instagram posts, reach, views, comments, or engagements.

**Example request**
```json
{ "query": "Which Instagram post got the most reach last month?", "thread_id": "client_1" }
```
**Example response**
```json
{
  "response": "Your top Instagram post last month reached 18,420 accounts with 2,310 likes and 142 comments (posted Mar 12).",
  "thread_id": "client_1",
  "connected_platforms": ["instagram"]
}
```

---

## 7. Google Analytics (GA4) — `GA` → `google_analytics` → GoogleAnalyticsAgent

**Domain:** GA4 website/app analytics — sessions, users, page views, bounce rate,
channel performance, geo traffic, events, page performance, device breakdowns, GA
campaign attribution. *(Google Ads cost/delivery metrics → Google Ads connector.)*

**Tables:** `geo`, `campaign`, `categorylabel`, `adslot`, `demochannel`, `pages`,
`tech_device_category_report`, `tech_device_model_report`,
`tech_platform_device_category_report`
**Schemas:** `schemas/ga4_*_schema.csv`

**Routes when:** the query contains a GA4 keyword (`ga4`, `google analytics`,
`sessions`, `page views`, `bounce rate`, `traffic`, `channel`, `geo`, `pages`,
`events`, `device`, …).

**Example request**
```json
{ "query": "What were my top 3 traffic channels and total sessions last month in GA4?", "thread_id": "client_1" }
```
**Example response**
```json
{
  "response": "Last month GA4 recorded 48,900 sessions. Top channels: Organic Search (41%), Paid Search (28%), Direct (17%).",
  "thread_id": "client_1",
  "connected_platforms": ["google_analytics"]
}
```

---

## Multi-Connector Queries

If a tenant has several platforms active and the query spans them, the supervisor
delegates to multiple agents and synthesizes one answer. `connected_platforms`
lists every active connector for that tenant (not only the ones used).

**Example request**
```json
{ "query": "Compare my total ad spend across Google Ads and Facebook last month.", "thread_id": "client_1" }
```
**Example response**
```json
{
  "response": "Last month total ad spend was $12,480 — Google Ads $8,200 and Facebook Ads $4,280. Google Ads drove the higher click volume; Facebook had the lower cost per conversion.",
  "thread_id": "client_1",
  "connected_platforms": ["google_ads", "facebook"]
}
```

---

## Routing Reference (keywords → connector)

| Connector | Platform keywords | Notes |
|---|---|---|
| Google Ads | google, googleads, ga, _ga | Ad cost/CTR/clicks (not GA4 analytics) |
| Shopify | shopify, shopifyads, shopifyad | Orders/products/SKU/sales (not ads) |
| LinkedIn Ads | linkedin, ln, linkedinads, lnads | **+ a metric keyword** (campaign/spend/cpc/ctr/creatives) |
| LinkedIn Pages | linkedin, ln, linkedinpages | **+ an organic keyword** (followers/page views/likes) |
| Facebook Ads | facebook, fb, fbads, facebookads | Ad cost/CTR/clicks |
| Instagram | instagram, insta, ig | Organic posts/reach/comments (not ads) |
| Google Analytics | ga4, analytics, sessions, traffic, channel, geo, pages, events, device | GA4 site analytics (not Google Ads cost) |

**Disambiguation rules built into the supervisor:**
- *LinkedIn Ads vs. Pages* — both share the `linkedin`/`ln` keyword; routing
  depends on whether the metric is **paid** (campaign, CPC, creatives → Ads) or
  **organic** (followers, page views → Pages).
- *Google Ads vs. GA4* — "Google Ads cost/clicks/impressions" → Google Ads;
  "sessions, traffic, bounce rate, channels, top pages" → Google Analytics.
- *Instagram / Shopify* — organic/e-commerce only; explicitly **not** for paid
  campaigns.

---

## Errors (any connector)

| Status | Meaning |
|---|---|
| `401` | Missing/invalid/expired token |
| `404` | Tenant has **no active connectors** (`{"detail": "No active databases found"}`) |
| `500` | Agent/DB/query failure |

---

*For the HTTP API contract see `API_DOCUMENTATION.md`; for system architecture see
`TECHNICAL_REPORT.md`.*
