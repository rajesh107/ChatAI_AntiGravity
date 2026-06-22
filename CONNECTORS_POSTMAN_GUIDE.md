# Accessing Claude's Messages API through Postman — All Connectors (Full Request & Response)

**Owner:** Rajesh

**Subject:** Full Claude Messages API request and response for each platform connector

---

## Objective

For **every connector** (Google Ads, Shopify, LinkedIn Ads, LinkedIn Pages, Facebook
Ads, Instagram, Google Analytics) this document shows the **complete** Claude API
request and the **full raw response** — exactly as sent to / returned by
`https://api.anthropic.com/v1/messages`. All responses are real outputs from
`claude-opus-4-8`.

> Setup (API key, Postman steps) is in `CLAUDE_POSTMAN_GUIDE.md`. Every request below
> uses the same three headers.

---

## Common Headers (all requests)

```http
POST https://api.anthropic.com/v1/messages
x-api-key: YOUR_API_KEY
anthropic-version: 2023-06-01
Content-Type: application/json
```

## Response field reference (same shape for every connector)

| Field | Meaning |
|---|---|
| `id` | Unique message id (`msg_...`) |
| `model` | Model that produced the response |
| `content[0].text` | The generated SQL (inside a ```` ```sql ```` block) |
| `stop_reason` | `end_turn` = finished naturally; `max_tokens` = truncated |
| `usage.input_tokens` | Tokens in the request (schema + question + system) |
| `usage.output_tokens` | Tokens generated (billed as output) |

---

## 1. Google Ads Connector

**Question:** `Show total cost (cost_micros/1000000) and clicks per campaign id, give me only query`

**Full request body:**
```json
{
    "model": "claude-opus-4-8",
    "max_tokens": 512,
    "system": "You are an RDS assistant. Based on the user question, generate a valid RDS SQL query. Return only the query.",
    "messages": [
        {
            "role": "user",
            "content": "Here are the schema details:\nTable : campaign_stats(customer_id bigint, date date, id bigint, impressions bigint, clicks bigint, conversions double precision, conversions_value double precision, cost_micros bigint, device varchar, ad_network_type varchar)\nQuestion: Show total cost (cost_micros/1000000) and clicks per campaign id, give me only query"
        }
    ]
}
```

**Full raw response:**
```json
{
    "id": "msg_01WZKbpvS9PsU9mxJEGRnFPz",
    "type": "message",
    "role": "assistant",
    "model": "claude-opus-4-8",
    "content": [
        {
            "type": "text",
            "text": "```sql\nSELECT id, SUM(cost_micros)/1000000.0 AS total_cost, SUM(clicks) AS total_clicks\nFROM campaign_stats\nGROUP BY id;\n```"
        }
    ],
    "stop_reason": "end_turn",
    "stop_sequence": null,
    "stop_details": null,
    "usage": {
        "input_tokens": 166,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "output_tokens": 72,
        "service_tier": "standard"
    }
}
```

---

## 2. Shopify Connector

**Question:** `Show total revenue (total_price) by currency, give me only query`

**Full request body:**
```json
{
    "model": "claude-opus-4-8",
    "max_tokens": 512,
    "system": "You are an RDS assistant. Based on the user question, generate a valid RDS SQL query. Return only the query.",
    "messages": [
        {
            "role": "user",
            "content": "Here are the schema details:\nTable : \"order\"(id bigint, email varchar, currency varchar, subtotal_price double precision, total_tax double precision, total_price double precision)\nQuestion: Show total revenue (total_price) by currency, give me only query"
        }
    ]
}
```

**Full raw response:**
```json
{
    "id": "msg_01EMjyDKM5ttxS4vLFh7oYdo",
    "type": "message",
    "role": "assistant",
    "model": "claude-opus-4-8",
    "content": [
        {
            "type": "text",
            "text": "```sql\nSELECT currency, SUM(total_price) AS total_revenue\nFROM \"order\"\nGROUP BY currency;\n```"
        }
    ],
    "stop_reason": "end_turn",
    "stop_sequence": null,
    "stop_details": null,
    "usage": {
        "input_tokens": 123,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "output_tokens": 47,
        "service_tier": "standard"
    }
}
```

---

## 3. LinkedIn Ads Connector

**Question:** `Show total clicks and cost in usd per creative_id, give me only query`

**Full request body:**
```json
{
    "model": "claude-opus-4-8",
    "max_tokens": 512,
    "system": "You are an RDS assistant. Based on the user question, generate a valid RDS SQL query. Return only the query.",
    "messages": [
        {
            "role": "user",
            "content": "Here are the schema details:\nTable : ad_analytics_by_creative(creative_id bigint, day timestamp, clicks bigint, impressions bigint, cost_in_usd numeric, comments bigint, follows bigint)\nQuestion: Show total clicks and cost in usd per creative_id, give me only query"
        }
    ]
}
```

**Full raw response:**
```json
{
    "id": "msg_012nQ85Mj56rouGVur7VEsrf",
    "type": "message",
    "role": "assistant",
    "model": "claude-opus-4-8",
    "content": [
        {
            "type": "text",
            "text": "```sql\nSELECT creative_id, SUM(clicks) AS total_clicks, SUM(cost_in_usd) AS total_cost_in_usd\nFROM ad_analytics_by_creative\nGROUP BY creative_id;\n```"
        }
    ],
    "stop_reason": "end_turn",
    "stop_sequence": null,
    "stop_details": null,
    "usage": {
        "input_tokens": 144,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "output_tokens": 83,
        "service_tier": "standard"
    }
}
```

---

## 4. LinkedIn Pages Connector

**Question:** `Show total organic follower gains by day, give me only query`

**Full request body:**
```json
{
    "model": "claude-opus-4-8",
    "max_tokens": 512,
    "system": "You are an RDS assistant. Based on the user question, generate a valid RDS SQL query. Return only the query.",
    "messages": [
        {
            "role": "user",
            "content": "Here are the schema details:\nTable : time_bound_follower_statistic(_fivetran_id varchar, day timestamp, follower_gains_organic_follower_gain int, follower_gains_paid_follower_gain int, organization_entity longtext)\nQuestion: Show total organic follower gains by day, give me only query"
        }
    ]
}
```

**Full raw response:**
```json
{
    "id": "msg_01KHKJm9DVTwphogEJWkLVhn",
    "type": "message",
    "role": "assistant",
    "model": "claude-opus-4-8",
    "content": [
        {
            "type": "text",
            "text": "```sql\nSELECT day, SUM(follower_gains_organic_follower_gain) AS total_organic_follower_gain\nFROM time_bound_follower_statistic\nGROUP BY day\nORDER BY day;\n```"
        }
    ],
    "stop_reason": "end_turn",
    "stop_sequence": null,
    "stop_details": null,
    "usage": {
        "input_tokens": 145,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "output_tokens": 77,
        "service_tier": "standard"
    }
}
```

---

## 5. Facebook Ads Connector

**Question:** `Show total spend and average ctr per ad_name, give me only query`

**Full request body:**
```json
{
    "model": "claude-opus-4-8",
    "max_tokens": 512,
    "system": "You are an RDS assistant. Based on the user question, generate a valid RDS SQL query. Return only the query.",
    "messages": [
        {
            "role": "user",
            "content": "Here are the schema details:\nTable : basic_ad(ad_id varchar, date date, impressions bigint, inline_link_clicks bigint, reach bigint, cpc double, cpm double, ctr double, spend double, ad_name varchar)\nQuestion: Show total spend and average ctr per ad_name, give me only query"
        }
    ]
}
```

**Full raw response:**
```json
{
    "id": "msg_01QpGecxtfnzWGHJq6wNBoAr",
    "type": "message",
    "role": "assistant",
    "model": "claude-opus-4-8",
    "content": [
        {
            "type": "text",
            "text": "```sql\nSELECT ad_name, SUM(spend) AS total_spend, AVG(ctr) AS average_ctr\nFROM basic_ad\nGROUP BY ad_name;\n```"
        }
    ],
    "stop_reason": "end_turn",
    "stop_sequence": null,
    "stop_details": null,
    "usage": {
        "input_tokens": 148,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "output_tokens": 67,
        "service_tier": "standard"
    }
}
```

---

## 6. Instagram Connector

**Question:** `Show top media by like_count, give me only query`

**Full request body:**
```json
{
    "model": "claude-opus-4-8",
    "max_tokens": 512,
    "system": "You are an RDS assistant. Based on the user question, generate a valid RDS SQL query. Return only the query.",
    "messages": [
        {
            "role": "user",
            "content": "Here are the schema details:\nTable : media_insights(id bigint, like_count bigint, comment_count bigint, video_photo_impressions bigint, video_photo_reach bigint, video_photo_saved bigint, video_photo_views bigint)\nQuestion: Show top media by like_count, give me only query"
        }
    ]
}
```

**Full raw response:**
```json
{
    "id": "msg_01TLtRQnac2yXCJBXP4L8JY4",
    "type": "message",
    "role": "assistant",
    "model": "claude-opus-4-8",
    "content": [
        {
            "type": "text",
            "text": "```sql\nSELECT id, like_count\nFROM media_insights\nORDER BY like_count DESC;\n```"
        }
    ],
    "stop_reason": "end_turn",
    "stop_sequence": null,
    "stop_details": null,
    "usage": {
        "input_tokens": 141,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "output_tokens": 39,
        "service_tier": "standard"
    }
}
```

---

## 7. Google Analytics (GA4) Connector

**Question:** `Show india records city wise with users count, give me only query`

**Full request body:**
```json
{
    "model": "claude-opus-4-8",
    "max_tokens": 512,
    "system": "You are an RDS assistant. Based on the user question, generate a valid RDS SQL query. Return only the query.",
    "messages": [
        {
            "role": "user",
            "content": "Here are the schema details:\nTable : geo(date date, country varchar, city varchar, sessions bigint, total_users bigint, active_users bigint, new_users bigint)\nQuestion: Show india records city wise with users count, give me only query"
        }
    ]
}
```

**Full raw response:**
```json
{
    "id": "msg_014bkMSJwbBLxX3tEQKJo3c3",
    "type": "message",
    "role": "assistant",
    "model": "claude-opus-4-8",
    "content": [
        {
            "type": "text",
            "text": "```sql\nSELECT city, SUM(total_users) AS users_count\nFROM geo\nWHERE country = 'India'\nGROUP BY city;\n```"
        }
    ],
    "stop_reason": "end_turn",
    "stop_sequence": null,
    "stop_details": null,
    "usage": {
        "input_tokens": 118,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "output_tokens": 53,
        "service_tier": "standard"
    }
}
```

---

## cURL Commands (all connectors)

Set your key once, then run any connector's command (Linux / macOS / Git Bash):

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

### 1. Google Ads

```bash
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model": "claude-opus-4-8", "max_tokens": 512, "system": "You are an RDS assistant. Based on the user question, generate a valid RDS SQL query. Return only the query.", "messages": [{"role": "user", "content": "Here are the schema details:\nTable : campaign_stats(customer_id bigint, date date, id bigint, impressions bigint, clicks bigint, conversions double precision, conversions_value double precision, cost_micros bigint, device varchar, ad_network_type varchar)\nQuestion: Show total cost (cost_micros/1000000) and clicks per campaign id, give me only query"}]}'
```

### 2. Shopify

```bash
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model": "claude-opus-4-8", "max_tokens": 512, "system": "You are an RDS assistant. Based on the user question, generate a valid RDS SQL query. Return only the query.", "messages": [{"role": "user", "content": "Here are the schema details:\nTable : \"order\"(id bigint, email varchar, currency varchar, subtotal_price double precision, total_tax double precision, total_price double precision)\nQuestion: Show total revenue (total_price) by currency, give me only query"}]}'
```

### 3. LinkedIn Ads

```bash
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model": "claude-opus-4-8", "max_tokens": 512, "system": "You are an RDS assistant. Based on the user question, generate a valid RDS SQL query. Return only the query.", "messages": [{"role": "user", "content": "Here are the schema details:\nTable : ad_analytics_by_creative(creative_id bigint, day timestamp, clicks bigint, impressions bigint, cost_in_usd numeric, comments bigint, follows bigint)\nQuestion: Show total clicks and cost in usd per creative_id, give me only query"}]}'
```

### 4. LinkedIn Pages

```bash
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model": "claude-opus-4-8", "max_tokens": 512, "system": "You are an RDS assistant. Based on the user question, generate a valid RDS SQL query. Return only the query.", "messages": [{"role": "user", "content": "Here are the schema details:\nTable : time_bound_follower_statistic(_fivetran_id varchar, day timestamp, follower_gains_organic_follower_gain int, follower_gains_paid_follower_gain int, organization_entity longtext)\nQuestion: Show total organic follower gains by day, give me only query"}]}'
```

### 5. Facebook Ads

```bash
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model": "claude-opus-4-8", "max_tokens": 512, "system": "You are an RDS assistant. Based on the user question, generate a valid RDS SQL query. Return only the query.", "messages": [{"role": "user", "content": "Here are the schema details:\nTable : basic_ad(ad_id varchar, date date, impressions bigint, inline_link_clicks bigint, reach bigint, cpc double, cpm double, ctr double, spend double, ad_name varchar)\nQuestion: Show total spend and average ctr per ad_name, give me only query"}]}'
```

### 6. Instagram

```bash
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model": "claude-opus-4-8", "max_tokens": 512, "system": "You are an RDS assistant. Based on the user question, generate a valid RDS SQL query. Return only the query.", "messages": [{"role": "user", "content": "Here are the schema details:\nTable : media_insights(id bigint, like_count bigint, comment_count bigint, video_photo_impressions bigint, video_photo_reach bigint, video_photo_saved bigint, video_photo_views bigint)\nQuestion: Show top media by like_count, give me only query"}]}'
```

### 7. Google Analytics (GA4)

```bash
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model": "claude-opus-4-8", "max_tokens": 512, "system": "You are an RDS assistant. Based on the user question, generate a valid RDS SQL query. Return only the query.", "messages": [{"role": "user", "content": "Here are the schema details:\nTable : geo(date date, country varchar, city varchar, sessions bigint, total_users bigint, active_users bigint, new_users bigint)\nQuestion: Show india records city wise with users count, give me only query"}]}'
```

> **Windows:** in PowerShell use `$env:ANTHROPIC_API_KEY` and put the JSON on one line; in CMD use `%ANTHROPIC_API_KEY%`. Git Bash runs the commands above as-is.

---

## Notes

- Only the user `content` (schema + question) and the returned `content[0].text`
  change between connectors; headers, `system`, and the response envelope are
  identical.
- Schemas shown are representative columns; full schemas live in `system_msg.py` and
  `schemas/*.csv`.
- The SQL is generated text — validate before running in production.
