# API Documentation — Dynamic Multi-Tenant Marketing Agent

REST API for a multi-tenant marketing-analytics chatbot. Clients authenticate to
get a JWT, then send natural-language questions; a LangGraph supervisor routes each
question to per-platform SQL agents (Google Ads, Facebook, Instagram, LinkedIn,
Google Analytics, Shopify) and returns a synthesized answer.

- **Base URL (local):** `http://localhost:8000`
- **Base URL (prod):** `http://18.191.191.139` *(EC2 — adjust to your host/port)*
- **Auth scheme:** OAuth2 password flow → JWT Bearer token
- **Content type:** `application/json` for `/chat`; `application/x-www-form-urlencoded` for `/token`
- **CORS:** all origins allowed (`*`)
- **Interactive docs:** `GET /docs` (Swagger UI) · `GET /openapi.json` (OpenAPI schema)

---

## Authentication

All data endpoints require a **Bearer token** in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

Tokens are JWTs signed with HS256 and **expire after 360 minutes (6 hours)**.
Request a new token via `POST /token` when one expires (expired/invalid tokens
return `401`).

---

## Endpoints

### 1. `POST /token` — Obtain an access token

Exchanges username + password for a JWT. Uses the OAuth2 "password" grant, so the
body is **form-encoded**, not JSON.

**Request**

| | |
|---|---|
| Method | `POST` |
| Path | `/token` |
| Content-Type | `application/x-www-form-urlencoded` |
| Auth | none |

**Form fields**

| Field | Type | Required | Description |
|---|---|---|---|
| `username` | string | yes | Account username |
| `password` | string | yes | Account password |
| `grant_type` | string | no | OAuth2 grant type (`password`); optional for this server |

**Response `200 OK`**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

| Field | Type | Description |
|---|---|---|
| `access_token` | string | JWT to send as `Authorization: Bearer <token>` |
| `token_type` | string | Always `bearer` |

**Errors**

| Status | When | Body |
|---|---|---|
| `401 Unauthorized` | Wrong username/password | `{"detail": "Incorrect username or password"}` |

**Example**

```bash
curl -X POST http://localhost:8000/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123"
```

---

### 2. `POST /chat` — Ask a question

Sends a natural-language query for a given tenant. The server looks up that
tenant's connected platforms, routes the query to the relevant SQL agent(s), and
returns the answer. Conversation state is kept per `thread_id` (last 10 messages).

**Request**

| | |
|---|---|
| Method | `POST` |
| Path | `/chat` |
| Content-Type | `application/json` |
| Auth | **Bearer token required** |

**Body**

| Field | Type | Required | Description |
|---|---|---|---|
| `query` | string | yes | The user's natural-language question |
| `thread_id` | string | yes | Tenant identifier (`user_id`) whose data to query **and** the conversation thread key |

```json
{
  "query": "What was my total ad spend last month?",
  "thread_id": "client_1"
}
```

> **Note on `thread_id`:** it is both the **target tenant** (whose connected
> platforms/databases are queried) and the **conversation key** (memory is scoped
> to it). It is independent of the logged-in user in the token.

**Response `200 OK`**

```json
{
  "response": "Your total ad spend last month was $12,480 across Google Ads ($8,200) and Facebook Ads ($4,280).",
  "thread_id": "client_1",
  "connected_platforms": ["google_ads", "facebook"]
}
```

| Field | Type | Description |
|---|---|---|
| `response` | string | The agent's complete answer (never truncated — see *Response completeness*) |
| `thread_id` | string | Echoes the request's `thread_id` |
| `connected_platforms` | string[] | Platform keys active for this tenant (see *Platform keys*) |

**Errors**

| Status | When | Body |
|---|---|---|
| `401 Unauthorized` | Missing/invalid/expired token | `{"detail": "Could not validate credentials"}` |
| `404 Not Found` | Tenant has no active platform connections | `{"detail": "No active databases found"}` |
| `500 Internal Server Error` | Agent/DB failure | `{"detail": "<error message>"}` |

**Example**

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123" | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "What was my total ad spend last month?", "thread_id": "client_1"}'
```

---

## Platform keys

`connected_platforms` values map from the tenant's `fivetran_connections` records:

| Connection type | Platform key | Agent |
|---|---|---|
| `GOOGLEADS` | `google_ads` | GoogleAdsAgent |
| `SHOPIFY` | `shopify` | ShopifyAgent |
| `LINKEDINADS` | `linkedin` | LinkedInAgent |
| `LINKEDIN` | `linkedin_pages` | LinkedInPagesAgent |
| `FBADS` | `facebook` | FacebookAdsAgent |
| `INSTA` | `instagram` | InstagramAgent |
| `GA` | `google_analytics` | GoogleAnalyticsAgent |

Only connections with `status = 1` are considered active.

---

## Behavior notes

**Response completeness.** The LLM (`claude-opus-4-8`) is configured with
`max_tokens` set to the model's full output capacity (fetched live from the
Anthropic Models API at startup — not hard-coded). If an answer ever hits the cap,
an automatic continuation loop completes it, so `/chat` always returns the full
response. `max_tokens` is a ceiling only — you are billed for actual tokens
generated.

**Prompt caching.** Large agent system prompts are cached (`cache_control:
ephemeral`), cutting cost/latency on repeated turns within a ~5-minute window.

**Latency.** A `/chat` call runs a multi-step agent loop (route → query DB →
synthesize), and the first call per tenant cold-loads data from MySQL into Redis;
subsequent calls are faster (cache hit). Expect several seconds per request.

**Statelessness vs. memory.** The HTTP API is stateless, but conversation memory
is persisted in Redis per `thread_id` (last 10 messages), so follow-up questions in
the same thread retain context.

---

## Quick reference

| Endpoint | Method | Auth | Body | Returns |
|---|---|---|---|---|
| `/token` | POST | none | form: `username`, `password` | `{access_token, token_type}` |
| `/chat` | POST | Bearer | json: `query`, `thread_id` | `{response, thread_id, connected_platforms}` |
| `/docs` | GET | none | — | Swagger UI |
| `/openapi.json` | GET | none | — | OpenAPI schema |
