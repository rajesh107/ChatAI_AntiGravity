# Claude API Connection Guide
## How ChatAI AntiGravity Connects to the Anthropic API

This document describes the **connection mechanics** only — credentials, client
initialization, endpoints, authentication, network flow, and failure handling. For
model usage/optimizations see `CLAUDE_INTEGRATION.md`.

---

## 1. Connection Overview

The application opens HTTPS connections to Anthropic at **two points**:

| # | When | Endpoint | Mechanism |
|---|---|---|---|
| 1 | Once at startup | `GET https://api.anthropic.com/v1/models/{id}` | Raw `httpx` GET (fetches max output tokens) |
| 2 | Every LLM call | `POST https://api.anthropic.com/v1/messages` | `langchain-anthropic` → `anthropic` SDK |

Both go over **HTTPS (TCP 443)** to `api.anthropic.com` and authenticate with the
same API key. No inbound connection from Anthropic is ever made — all traffic is
outbound from the app server.

```
  app server (agent.py)
        │
        │  HTTPS 443 (outbound)        x-api-key: sk-ant-...
        ▼                              anthropic-version: 2023-06-01
  api.anthropic.com
     ├─ GET  /v1/models/{id}     ← once at startup (output limit)
     └─ POST /v1/messages        ← every supervisor / sub-agent LLM call
```

---

## 2. Credentials

The connection authenticates with a single secret: **`ANTHROPIC_API_KEY`**
(format `sk-ant-...`).

**Loading (`agent.py`):**

```python
from dotenv import load_dotenv
load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise RuntimeError(
        "ANTHROPIC_API_KEY environment variable is required. "
        "Add it to your .env (ANTHROPIC_API_KEY=sk-ant-...) and restart."
    )
```

- Stored in `.env` (never committed; `.env.example` ships keys-only).
- **Fail-fast:** the app refuses to start if the key is missing.
- In production the key is provided to the systemd service via
  `EnvironmentFile=/home/ubuntu/chatbot/.env`.

**`.env` entry:**
```
ANTHROPIC_API_KEY=sk-ant-...
```

---

## 3. Connection #1 — Messages API (the LLM calls)

This is the primary connection, used for every supervisor and sub-agent call.

### Client initialization
The key is passed into the LangChain wrapper, which constructs the underlying
`anthropic.Anthropic` SDK client:

```python
llm = CompletingChatAnthropic(        # subclass of langchain_anthropic.ChatAnthropic
    model=MODEL_ID,                   # "claude-opus-4-8"
    max_tokens=MODEL_MAX_OUTPUT_TOKENS,
    streaming=False,
    api_key=ANTHROPIC_API_KEY,        # ← the connection credential
)
```

### Connection stack
```
CompletingChatAnthropic (agent.py)
  └─ langchain_anthropic.ChatAnthropic   (0.3.0)
       └─ anthropic.Anthropic SDK        (0.40.0)
            └─ httpx HTTPS client → POST https://api.anthropic.com/v1/messages
```

### Authentication headers (set by the SDK)
| Header | Value |
|---|---|
| `x-api-key` | `ANTHROPIC_API_KEY` |
| `anthropic-version` | `2023-06-01` |
| `content-type` | `application/json` |

### Connection behavior (anthropic SDK defaults)
| Property | Default | Notes |
|---|---|---|
| Base URL | `https://api.anthropic.com` | Override via `ANTHROPIC_BASE_URL` if needed. |
| Transport | HTTPS / `httpx` | Keep-alive connection pooling. |
| Timeout | 10 minutes | Per request. |
| Retries | 2, exponential backoff | Auto-retries 429 and ≥500. |

---

## 4. Connection #2 — Models API (startup, output limit)

At startup the app makes one direct call to discover the model's true output limit,
so `max_tokens` is never hard-coded. The `anthropic` 0.40.0 SDK does not expose the
Models API (`client.models` is absent), so this uses a raw `httpx` GET:

```python
def _get_model_max_output_tokens(model_id: str, fallback: int = 16000) -> int:
    resp = httpx.get(
        f"https://api.anthropic.com/v1/models/{model_id}",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return int(resp.json()["max_tokens"])     # → 128000 for claude-opus-4-8
```

- Same host, same auth headers as the Messages API.
- **Resilient:** if this connection fails (network/DNS/timeout), the app catches the
  error and uses the **16,000 fallback** instead of crashing — logged as a warning.
- Confirmed response: `{"id": "claude-opus-4-8", "max_tokens": 128000, ...}`.

---

## 5. End-to-End Connection Flow

```
App startup
   1. load_dotenv() → read ANTHROPIC_API_KEY from .env
   2. Fail fast if key missing
   3. GET /v1/models/claude-opus-4-8  → max_tokens = 128000   (Connection #2)

Per /chat request (per tenant graph build)
   4. Construct CompletingChatAnthropic(api_key=ANTHROPIC_API_KEY)
   5. Supervisor / sub-agent invoke →
        POST /v1/messages  (model, system+cache_control, tools, messages)   (Connection #1)
   6. SDK auto-retries on 429/5xx; returns the response
```

---

## 6. Network / Firewall Requirements

| Requirement | Value |
|---|---|
| Outbound host | `api.anthropic.com` |
| Port | TCP 443 (HTTPS) |
| Direction | Outbound only (no inbound from Anthropic) |
| DNS | Must resolve `api.anthropic.com` |

If the app runs behind an egress proxy/firewall, allow outbound HTTPS to
`api.anthropic.com`. A blocked connection surfaces as: Models API → fallback to
16,000 at startup (logged); Messages API → request errors on `/chat`.

---

## 7. Verifying the Connection

**Raw connectivity + auth (curl):**
```bash
curl https://api.anthropic.com/v1/models/claude-opus-4-8 \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01"
# Expect HTTP 200 with {"id":"claude-opus-4-8","max_tokens":128000,...}
```

**Through the app's client (Python):**
```python
from langchain_anthropic import ChatAnthropic
import os
llm = ChatAnthropic(model="claude-opus-4-8", max_tokens=16,
                    api_key=os.getenv("ANTHROPIC_API_KEY"))
print(llm.invoke("Reply with just: OK").content)
```

**At startup**, a successful connection logs the Models API call; the server's boot
log shows `GET https://api.anthropic.com/v1/models/claude-opus-4-8 "HTTP/1.1 200 OK"`.

---

## 8. Connection Failure Modes

| Symptom | Cause | Handling |
|---|---|---|
| App won't start: `ANTHROPIC_API_KEY ... required` | Key missing from env/`.env` | Add the key, restart. |
| Startup logs `max-output lookup failed ... using fallback 16000` | Models API unreachable (network/DNS/proxy) | App continues with 16,000 cap; fix egress. |
| `401` from Anthropic | Invalid/revoked key | Replace the key in `.env`. |
| `429` / `5xx` on `/chat` | Rate limit / Anthropic transient error | SDK auto-retries (2×, backoff); persists → surfaces as a `/chat` 500. |
| Connection timeout | Network/firewall | Allow outbound 443 to `api.anthropic.com`. |

---

## 9. Code Locations (`agent.py`)

| Concern | Location |
|---|---|
| Load + validate `ANTHROPIC_API_KEY` | top of module (after `load_dotenv()`) |
| Models API connection (startup) | `_get_model_max_output_tokens()` |
| Messages API client construction | `llm = CompletingChatAnthropic(api_key=ANTHROPIC_API_KEY, ...)` |

---

*Connection mechanics only. See `CLAUDE_INTEGRATION.md` for model usage and
`API_DOCUMENTATION.md` for the application's own HTTP API.*
