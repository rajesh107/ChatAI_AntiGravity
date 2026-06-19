# Technical Documentation Report
## ChatAI AntiGravity — Dynamic Multi-Tenant Marketing Agent

**Document type:** Technical / System Documentation
**System:** FastAPI + LangGraph multi-tenant marketing-analytics chatbot
**LLM:** Anthropic Claude Opus 4.8 (`claude-opus-4-8`)
**Date:** 2026-06-18

---

## 1. Executive Summary

ChatAI AntiGravity is a multi-tenant conversational analytics service. Each tenant
connects one or more marketing platforms (Google Ads, Facebook/Instagram Ads,
LinkedIn Ads & Pages, Google Analytics, Shopify) whose data lands in MySQL via
Fivetran. A user asks a question in natural language; a **supervisor agent** routes
it to the relevant **platform SQL agent(s)**, which query the tenant's data and
return a synthesized answer over a REST API.

This report documents the system architecture, technology stack, API surface,
the LLM layer (recently migrated from OpenAI GPT-4.1 to Claude Opus 4.8), caching
strategy, deployment process, and the optimizations applied to guarantee complete,
cost-efficient responses.

---

## 2. System Architecture

```
                         ┌──────────────────────────────────────────┐
   Client (web/app) ───► │  FastAPI  (main.py)                       │
       JWT + query       │   • POST /token   (auth → JWT)            │
                         │   • POST /chat    (authenticated query)   │
                         └───────────────┬──────────────────────────┘
                                         │  thread_id (tenant)
                                         ▼
                         ┌──────────────────────────────────────────┐
                         │  LangGraph Supervisor  (agent.py)         │
                         │   routes to active platform agents only   │
                         └───────────────┬──────────────────────────┘
                       delegates │        │ synthesizes final answer
            ┌────────────────────┼────────┴───────────────────┐
            ▼                    ▼                             ▼
   GoogleAdsAgent        FacebookAdsAgent   ...   GoogleAnalyticsAgent
   (SQL tool-calling agents, one per connected platform)
            │                    │                             │
            └──────────── per-tenant SQLite (merged) ──────────┘
                                         ▲
                         ┌───────────────┴──────────────────────────┐
                         │  Redis  (data cache + graph checkpointer) │
                         │  MySQL  (source of platform data)         │
                         └──────────────────────────────────────────┘
```

**Key design points**

- **Multi-tenancy:** the `thread_id` in each request identifies the tenant. The
  server reads that tenant's active platform connections from the admin MySQL
  database (`fivetran_connections`, `status = 1`) and builds an agent graph
  containing only the agents for connected platforms.
- **Supervisor / sub-agent pattern:** a supervisor LLM decides which platform
  agent answers, delegates, then synthesizes a final response. Each sub-agent is a
  LangChain SQL tool-calling agent scoped to that platform's tables.
- **Per-tenant data engine:** platform data is pulled from MySQL, cleaned, and
  merged into an in-memory/SQLite engine the SQL agents query.
- **Caching at three layers:** compiled-graph cache (in-process), tenant data cache
  (Redis), and Anthropic prompt caching (on the LLM system prompts).

---

## 3. Technology Stack

| Layer | Technology | Version |
|---|---|---|
| API framework | FastAPI | 0.122.0 |
| ASGI server | Uvicorn (dev) / Gunicorn (prod option) | 0.38.0 / 23.0.0 |
| Agent orchestration | LangGraph | 0.2.76 |
| LLM framework | LangChain + langchain-anthropic | 0.3.13 / 0.3.0 |
| LLM SDK | anthropic | 0.40.0 |
| LLM model | Claude Opus 4.8 (`claude-opus-4-8`) | — |
| Data store (source) | MySQL (via PyMySQL + SQLAlchemy) | 1.1.2 / 2.0.44 |
| Cache / checkpointer | Redis (Redis Cloud) + langgraph-checkpoint-redis | 6.4.0 / 0.0.8 |
| Auth | JWT (PyJWT) + OAuth2 password flow + passlib/bcrypt | 2.10.1 |
| Data processing | pandas / numpy | 2.3.3 / 2.3.5 |
| Runtime | Python 3.12 | — |

---

## 4. Component Reference

| Module | Responsibility |
|---|---|
| `main.py` | FastAPI app; `/token` and `/chat` endpoints; tenant→platform lookup; CORS; JWT-protected routing into the agent graph. |
| `agent.py` | LangGraph graph builder; supervisor + per-platform SQL agents; Redis data cache + checkpointer; LLM configuration (`CompletingChatAnthropic`); prompt caching. |
| `auth.py` | OAuth2 password authentication, JWT issue/verify, password hashing. |
| `system_msg.py` | System prompts for the supervisor and each platform agent, plus shared agent rules and supervisor group config. |
| `etl_cleaner.py` | Cleans/normalizes platform tables (dtype mapping) before they are queried. |
| `upload_to_mysql.py` | Loads source data into MySQL. |
| `onboard_client.py` / `setup_admin.py` | Tenant onboarding and admin/database setup utilities. |
| `schemas/` | CSV schema definitions per platform table. |
| `scripts/` | Maintenance utilities (column comments, data checks, etc.). |

---

## 5. Request / Data Flow (`POST /chat`)

1. **Auth** — client presents a JWT Bearer token; the server validates it.
2. **Tenant resolution** — `thread_id` → query `fivetran_connections` for active
   platforms (`status = 1`), producing a platform→database map.
3. **Graph build / reuse** — a compiled LangGraph for the tenant is reused from the
   in-process cache (1-hour TTL) or built fresh.
4. **Data load** — each platform's tables are loaded from MySQL (or read from the
   Redis data cache on a hit), cleaned, and merged into a query engine.
5. **Supervisor** — routes the question to the relevant platform agent(s).
6. **SQL agent** — generates and runs SQL against the tenant's data, returns results.
7. **Synthesis** — the supervisor composes the final natural-language answer.
8. **Response** — returned as `{response, thread_id, connected_platforms}`.
   Conversation memory (last 10 messages) is checkpointed in Redis per `thread_id`.

---

## 6. API Reference (summary)

Full reference: **`API_DOCUMENTATION.md`** · Machine-readable spec: **`openapi.json`**
· Interactive: **Swagger UI at `/docs`**, ReDoc at `/redoc`.

| Endpoint | Method | Auth | Body | Returns |
|---|---|---|---|---|
| `/token` | POST | none | form: `username`, `password` | `{access_token, token_type}` |
| `/chat` | POST | Bearer JWT | json: `query`, `thread_id` | `{response, thread_id, connected_platforms}` |
| `/docs` | GET | none | — | Swagger UI |
| `/openapi.json` | GET | none | — | OpenAPI 3.1 schema |

- **Auth:** OAuth2 password grant → JWT (HS256), **6-hour (360-min) expiry**.
- **CORS:** all origins (`*`) — review before production exposure.

---

## 7. LLM Layer & Recent Enhancements

The LLM layer was migrated from **OpenAI GPT-4.1** to **Claude Opus 4.8** and then
hardened with three production optimizations. All changes are isolated to
`agent.py`.

### 7.1 Migration (OpenAI → Claude)
- `ChatOpenAI(model="gpt-4.1")` → `ChatAnthropic(model="claude-opus-4-8")`.
- `create_openai_tools_agent` → `create_tool_calling_agent`.
- Added content-block flattening (`_content_to_text`) because Claude returns
  message content as a list of blocks rather than a plain string.

### 7.2 Prompt caching (cost / latency)
- Each agent's large system prompt carries an ephemeral cache breakpoint
  (`cache_control: {type: "ephemeral"}`).
- The static prompt prefix (tools + system prompt) is cached and served at ~0.1×
  input cost on repeated turns within the ~5-minute window.
- **Verified:** first turn wrote 4,605 tokens to cache; second turn read them back
  from cache.

### 7.3 Complete-response guarantee
- Custom `CompletingChatAnthropic` subclass watches `stop_reason`; if an answer is
  cut off at the token cap (`stop_reason == "max_tokens"`), it auto-continues and
  stitches the parts until the model finishes naturally (`end_turn`).
- Required `stream_runnable=False` on the executors so the LLM is invoked via the
  non-streaming path where the continuation logic runs (this was a necessary fix —
  the default streaming path bypassed it).
- **Verified end-to-end** through `AgentExecutor`: a forced-truncation test
  returned the full answer instead of a cut-off one.

### 7.4 Output cap fetched dynamically (no hard-coded value)
- `max_tokens` is set to the model's true maximum output, **fetched at startup from
  the Anthropic Models API** (`GET /v1/models/{id}` → `max_tokens`), not hard-coded.
- Resolves to **128,000** for Claude Opus 4.8; a 16,000 fallback applies only if the
  Models API is unreachable at boot.
- `max_tokens` is a ceiling only — billing is on actual output tokens, so a high
  ceiling costs nothing extra and ensures answers are never artificially truncated.

### 7.5 Measured system-prompt sizes (cached prefix, per agent)

| Agent system prompt | Tokens |
|---|---:|
| Supervisor | 4,605 |
| InstagramAgent | 6,886 |
| ShopifyAgent | 7,430 |
| GoogleAdsAgent | 9,014 |
| LinkedInPagesAgent | 9,868 |
| LinkedInAgent | 10,842 |
| FacebookAdsAgent | 12,987 |
| GoogleAnalyticsAgent | 15,836 |

All exceed Opus's 4,096-token cache minimum, so every agent benefits from prompt
caching.

---

## 8. Caching Strategy

| Cache | Scope | TTL | Purpose |
|---|---|---|---|
| Compiled-graph cache | In-process (per `user_id`) | 1 hour | Avoid rebuilding the agent graph each request; refresh after Fivetran syncs. |
| Tenant data cache | Redis (`data_cache:{user_id}:{group}`) | 24 hours | Avoid re-pulling platform data from MySQL; compressed (zlib + pickle). |
| Conversation checkpoint | Redis (LangGraph checkpointer) | — | Per-`thread_id` memory (last 10 messages). |
| Prompt cache | Anthropic (ephemeral) | ~5 min | Cache LLM system-prompt prefix; ~0.1× input cost on repeat. |

---

## 9. Deployment & Operations

**Packaging (local):** `package.ps1` builds a versioned `chatbot_<timestamp>.tar.gz`
containing app code, requirements, the systemd unit, deploy scripts, schemas,
documentation (`API_DOCUMENTATION.md`, `openapi.json`), and a generated
`.env.example` (keys only, values stripped). `.env` is never bundled.

**Deploy (EC2):**
```bash
scp chatbot_<ts>.tar.gz ubuntu@<server>:~/
bash deploy_tarball.sh chatbot_<ts>.tar.gz
```
`deploy_tarball.sh` backs up the current deployment, stops the service, syncs files
(**preserving the server's `.env`**), installs dependencies into a venv (pinning
`bcrypt==4.0.1` for passlib compatibility), installs/enables the systemd unit,
restarts the service, and runs a `/docs` health check. Rollback is a re-deploy of a
backup archive.

**Runtime (systemd, `chatbot.service`):** runs `uvicorn main:app` on `0.0.0.0:8000`
with 2 workers, `Restart=always`, UTF-8/unbuffered logging to journald
(`journalctl -u chatbot -f`).

**Required environment (`.env`):** `ANTHROPIC_API_KEY`, `REDIS_URL`, MySQL host/
credentials, admin DB name, JWT secret. The app fails fast on a missing
`ANTHROPIC_API_KEY` or `REDIS_URL`.

---

## 10. Security Considerations

- **Authentication:** JWT Bearer (HS256), 6-hour expiry; invalid/expired tokens
  return 401.
- **Secrets:** loaded from `.env`; never bundled in deploy artifacts (`.env.example`
  ships keys only).
- **Items to review before production hardening:**
  - **CORS** is currently `*` — restrict to known origins.
  - **Seeded credentials** (`auth.py`) are in-code test users — replace with a real
    user store for production.
  - **Tenant isolation:** `/chat` does not currently enforce that the caller's token
    matches the requested `thread_id` (a commented-out check exists) — enable if
    cross-tenant access must be prevented.

---

## 11. Cost & Performance Notes

- **Token billing** is on actual output, not the `max_tokens` ceiling. A single
  `/chat` runs a multi-step loop (supervisor + SQL tool iterations), so input tokens
  processed per query are dominated by the repeated system prompts — which is
  exactly what prompt caching discounts (~0.1× after the first use).
- **Latency:** first query per tenant cold-loads data from MySQL into Redis;
  subsequent queries hit the cache. Expect several seconds per query due to the
  multi-step agent loop.
- **Model pricing (Opus 4.8):** $5 / 1M input, $25 / 1M output; cache read ~$0.50/1M,
  cache write ~$6.25/1M.

---

## 12. Change Log (this iteration)

| # | Change | File | Status |
|---|---|---|---|
| 1 | Migrated LLM OpenAI GPT-4.1 → Claude Opus 4.8 | `agent.py` | Done |
| 2 | Added `cache_control` prompt caching to all system prompts | `agent.py` | Done · verified |
| 3 | Added `CompletingChatAnthropic` continuation (complete answers) | `agent.py` | Done · verified e2e |
| 4 | `stream_runnable=False` so continuation runs through AgentExecutor | `agent.py` | Done · verified |
| 5 | `max_tokens` fetched from Models API (no hard-coded cap) | `agent.py` | Done · verified |
| 6 | API documentation + OpenAPI export | `API_DOCUMENTATION.md`, `openapi.json` | Done |
| 7 | Packaging includes docs; `flush_redis.py` console fix | `package.ps1`, `flush_redis.py` | Done |

---

*End of report.*
