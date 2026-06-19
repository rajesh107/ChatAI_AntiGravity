# Claude Integration Guide
## ChatAI AntiGravity — How Anthropic Claude Is Used

**Model:** Claude Opus 4.8 (`claude-opus-4-8`)
**SDK:** `anthropic` 0.40.0 via `langchain-anthropic` 0.3.0 (LangChain 0.3.13 / LangGraph 0.2.76)
**Scope:** All LLM usage lives in `agent.py`. This document covers the model
configuration, prompt caching, the complete-response mechanism, the dynamic output
limit, the request shape sent to Claude, and token/cost characteristics.

---

## 1. Why Claude Opus 4.8

The system was migrated from OpenAI GPT-4.1 to Claude Opus 4.8 (commit
`Migrate LLM from OpenAI GPT-4.1 to Claude Opus 4.8`). Opus 4.8 is Anthropic's most
capable Opus-tier model: strong multi-step/agentic reasoning (suits the
supervisor + SQL-agent pattern), a 1M-token context window, up to 128K output
tokens, and native prompt caching for cost control.

| Property | Value |
|---|---|
| Model ID | `claude-opus-4-8` |
| Context window | 1,000,000 tokens |
| Max output | 128,000 tokens |
| Pricing | $5 / 1M input · $25 / 1M output |
| Cache read / write | ~$0.50 / 1M · ~$6.25 / 1M |
| Thinking | Adaptive only (not configured here) |

---

## 2. Model Configuration

Defined once per tenant graph build in `agent.py`:

```python
MODEL_ID = "claude-opus-4-8"
MODEL_MAX_OUTPUT_TOKENS = _get_model_max_output_tokens(MODEL_ID)   # fetched at startup

llm = CompletingChatAnthropic(
    model=MODEL_ID,
    max_tokens=MODEL_MAX_OUTPUT_TOKENS,   # model's true max (128000), not hard-coded
    streaming=False,                      # required for the continuation logic
    api_key=ANTHROPIC_API_KEY,
)
```

This single `llm` is shared by the supervisor and every platform sub-agent.

| Setting | Value | Reason |
|---|---|---|
| `model` | `claude-opus-4-8` | Most capable Opus-tier model for agentic routing + synthesis. |
| `max_tokens` | 128,000 (fetched) | Full output capacity → answers never artificially truncated. |
| `streaming` | `False` | The complete-response logic runs on the non-streaming `_generate` path. |
| `api_key` | from `.env` | `ANTHROPIC_API_KEY`; app fails fast if missing. |

---

## 3. Prompt Caching (`cache_control`)

Each agent's large, static system prompt is tagged with an **ephemeral cache
breakpoint** so Claude caches the prompt prefix (tools + system) and serves it at
~0.1× input cost on repeated turns (≈5-minute TTL).

```python
prompt = ChatPromptTemplate.from_messages([
    ("system", [{
        "type": "text",
        "text": system_msg,                       # the platform / supervisor prompt
        "cache_control": {"type": "ephemeral"},   # cache breakpoint
    }]),
    MessagesPlaceholder("messages"),
    MessagesPlaceholder("agent_scratchpad"),
])
```

Applied to **both** the supervisor prompt and every sub-agent prompt.

**Caching minimum:** Opus requires a ≥4,096-token prefix to cache. All prompts here
exceed it:

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

**Verification (live):**

| | Turn 1 | Turn 2 |
|---|---|---|
| `cache_creation_input_tokens` | 4,605 | — |
| `cache_read_input_tokens` | 0 | 4,605 |

Turn 1 wrote the prefix to cache; Turn 2 read it back at ~0.1× cost.

> **Caveat:** the prompts interpolate `{current_date_str}` / `{current_year_str}`,
> so the cached prefix is byte-stable only within a single day — fine with the
> ~5-minute TTL, which re-warms continuously during active use.

---

## 4. Complete-Response Mechanism (`CompletingChatAnthropic`)

Anthropic returns `stop_reason == "max_tokens"` when output hits the cap mid-answer.
A custom subclass detects this and continues generation until the model finishes
naturally, so callers always receive the full answer.

```python
class CompletingChatAnthropic(ChatAnthropic):
    """Finishes answers cut off by the output-token cap."""
    max_continuations: int = 4

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        result = super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
        gen = result.generations[0]; msg = gen.message
        if getattr(msg, "tool_calls", None):                 # never touch tool-call turns
            return result
        if self._stop_reason(result) != "max_tokens":        # only continue truncated text
            return result
        # ... re-prompt "continue where you left off", stitch text, until end_turn ...
```

Key facts:
- **Only plain-text answers** are continued. Tool-call turns are returned untouched
  (continuing them would corrupt the tool-call JSON).
- **`stop_reason` source:** at `_generate` time it lives in `ChatResult.llm_output`,
  not `message.response_metadata` (which langchain-core populates afterward).
- **Bound:** up to `max_continuations = 4` follow-ups (a single answer up to ~5×
  `max_tokens` before giving up); stops early on `end_turn`.
- **Critical pairing — `stream_runnable=False`:** `AgentExecutor` streams the agent
  runnable by default, which routes through `_stream` and **bypasses** this override.
  Both executors are therefore built with the non-streaming runnable:

  ```python
  agent = RunnableMultiActionAgent(
      runnable=create_tool_calling_agent(llm, tools, prompt),
      stream_runnable=False,
  )
  agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
  ```

**Verification (end-to-end through AgentExecutor):** with a forced low cap, the
baseline `ChatAnthropic` returned a truncated list; `CompletingChatAnthropic`
returned the full list (`stop_reason: end_turn`).

---

## 5. Dynamic Output Limit (no hard-coded cap)

`max_tokens` is set to the model's true maximum, fetched from the Anthropic Models
API at startup — so the value is never hard-coded and auto-adjusts if the model
changes.

```python
def _get_model_max_output_tokens(model_id: str, fallback: int = 16000) -> int:
    resp = httpx.get(
        f"https://api.anthropic.com/v1/models/{model_id}",
        headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01"},
        timeout=10,
    )
    resp.raise_for_status()
    return int(resp.json()["max_tokens"])     # → 128000 for claude-opus-4-8
```

- Resolves to **128,000** at startup (confirmed via the Models REST endpoint).
- **Fallback = 16,000** only if the Models API is unreachable at boot (prevents a
  crash), logged as a warning.
- `max_tokens` is a **ceiling, not a target** — billing is on actual output tokens,
  so a high ceiling costs nothing extra and only prevents truncation.

> The `anthropic` 0.40.0 SDK does not wrap the Models API (`client.models` is
> absent), so this uses a raw `httpx` GET. It also does not enforce a non-streaming
> timeout guard, so `max_tokens=128000` with `streaming=False` is accepted.

---

## 6. The Request Sent to Claude

Every LLM call POSTs to `https://api.anthropic.com/v1/messages`. A supervisor call
looks like this (captured via `_get_request_payload`):

```jsonc
{
  "model": "claude-opus-4-8",
  "max_tokens": 128000,
  "stream": false,
  "system": [
    {
      "type": "text",
      "text": "You are a 'Data Router' managing a team of specialist SQL agents...",
      "cache_control": { "type": "ephemeral" }      // caching breakpoint
    }
  ],
  "tools": [
    { "name": "GoogleAdsAgent",   "description": "...", "input_schema": {...} },
    { "name": "FacebookAdsAgent", "description": "...", "input_schema": {...} }
  ],
  "messages": [
    { "role": "user", "content": "What was my total ad spend last month?" }
  ]
}
```

Anthropic processes the cache prefix in order **tools → system → messages**, so the
`cache_control` on the system block caches both the tools and the system prompt.
Sub-agent calls have the same shape with that platform's larger system prompt and
the SQL toolkit's tools.

---

## 7. Token & Cost Characteristics

A single `/chat` is a multi-step loop (supervisor routes → SQL agent runs a
tool-loop of ~4–6 LLM calls → supervisor synthesizes). The dominant token cost is
the **system prompts re-sent on every loop iteration** — which is exactly what
prompt caching discounts.

- **Per query (typical single platform):** roughly 60k–120k input tokens processed
  across the internal calls, ~1k–4k output.
- **With caching:** the repeated system-prompt prefix bills at ~0.1× after first
  use, cutting input cost on a typical query roughly in half or more.
- **Billing:** only actual `output_tokens` are billed for output; `max_tokens` is
  not billed. Verify cache effectiveness via
  `response.usage.cache_read_input_tokens` (> 0 on repeat turns).

---

## 8. Code Map (`agent.py`)

| Concern | Location |
|---|---|
| Model id | `MODEL_ID` |
| Dynamic max-output fetch | `_get_model_max_output_tokens()` → `MODEL_MAX_OUTPUT_TOKENS` |
| Continuation subclass | `class CompletingChatAnthropic` |
| LLM construction | `llm = CompletingChatAnthropic(...)` |
| Sub-agent prompt + `cache_control` | inside `create_agent_tool()` |
| Supervisor prompt + `cache_control` | supervisor setup section |
| `stream_runnable=False` wrappers | both `RunnableMultiActionAgent(...)` |
| Content-block flattening | `_content_to_text()` |

---

## 9. Operational Notes

- **Required env var:** `ANTHROPIC_API_KEY` (app fails fast if missing).
- **Startup dependency:** the Models API is queried once at boot for the output
  limit; if unreachable, the 16,000 fallback applies (logged).
- **SDK versions are pinned** (`anthropic==0.40.0`, `langchain-anthropic==0.3.0`).
  Upgrading would enable `client.models` (replacing the raw `httpx` lookup) and the
  newer Models API capabilities, but is a dependency change to validate separately.
- **Diagnostics:** standalone probe scripts were used to verify caching, continuation
  (isolated and end-to-end), token counts, and the request payload. They are
  development-only and not part of the runtime.

---

*This document describes the Claude/Anthropic integration only. For the full system
see `TECHNICAL_REPORT.md`; for the HTTP API see `API_DOCUMENTATION.md`.*
