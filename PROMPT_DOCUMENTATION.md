# Prompt Documentation
## System Prompt Architecture — ChatAI AntiGravity

All prompts live in **`system_msg.py`** and are assembled into LangChain
`ChatPromptTemplate`s in `agent.py`. There are two prompt families:

1. **Supervisor prompt** — routes a user question to the right connector agent(s).
2. **Connector agent prompts** (one per platform) — generate and run SQL, then
   summarize results.

A shared rule block (`SHARED_AGENT_RULES`) is embedded into every prompt for
consistent business logic.

---

## 1. Prompt Inventory

| Symbol (`system_msg.py`) | Used by | Purpose |
|---|---|---|
| `SHARED_AGENT_RULES` | All agents | Global business/answer rules embedded in every prompt |
| `google_system_msg` | GoogleAdsAgent | SQL agent prompt + Google Ads schema |
| `shopify_system_msg` | ShopifyAgent | SQL agent prompt + Shopify schema |
| `linkedin_system_msg` | LinkedInAgent | SQL agent prompt + LinkedIn Ads schema |
| `linkedin_pages_system_msg` | LinkedInPagesAgent | SQL agent prompt + LinkedIn Pages schema |
| `facebook_system_msg` | FacebookAdsAgent | SQL agent prompt + Facebook Ads schema |
| `instagram_system_msg` | InstagramAgent | SQL agent prompt + Instagram schema |
| `google_analytics_system_msg` | GoogleAnalyticsAgent | SQL agent prompt + GA4 schema |
| `SUPERVISOR_HEADER` | Supervisor | Router role + history protocol |
| `SUPERVISOR_GROUP_CONFIGS` | Supervisor | Per-connector description + routing rules |
| `SUPERVISOR_FOOTER` | Supervisor | Mandatory routing logic + output format |

---

## 2. Template Variables

Prompts are LangChain f-string templates. These placeholders are filled at request
time (in `agent.py`'s `supervisor_node` / `run_agent`):

| Variable | Filled with | Notes |
|---|---|---|
| `{SHARED_AGENT_RULES}` | The shared rules block | Injected into each agent prompt |
| `{current_date_str}` | `YYYY-MM-DD` (today) | Used only for relative time terms |
| `{current_year_str}` | `YYYY` | Used only for relative time terms |
| `{recent_start_date_str}` | today − 30 days | Sub-agents only |

> **Caching note:** `{current_date_str}` / `{current_year_str}` sit near the top of
> the prompt, so the cached prompt prefix is byte-stable only within a single day
> (acceptable with the ~5-minute prompt-cache TTL).

---

## 3. Shared Rules (`SHARED_AGENT_RULES`)

Embedded in every connector prompt to enforce consistent behavior. The six rules:

| # | Rule | Intent |
|---|---|---|
| 1 | **Context-Only History Usage** | Resolve follow-ups ("list for each", "show more", pronouns) by inheriting platform/subject/time from prior turn; never treat a follow-up as a new unrelated question. |
| 2 | **Mandatory Fresh Query Execution** | Always generate and run a new SQL query, even for repeated questions. |
| 3 | **Time Period Logic** | Undefined timeframe → query all history (never default to current year). Defined timeframe → filter strictly. Ignore Current Date/Year unless the question uses relative time terms. |
| 4 | **Zero-Result & Interpretation Protocol** | On empty results, explicitly say "There are no [subject] found" — never fabricate or imply a list. |
| 5 | **Mandatory Explicit Answer Protocol** | Always include actual values (names, numbers, dates) in the answer; forbidden phrases like "shown above". Responses must be self-contained. |
| 6 | **Date Filter Strictness** | Month+year → exact numeric date boundaries (`>= 'YYYY-MM-01' AND <= 'YYYY-MM-30/31'`); never `LIKE` on dates. |

**Excerpt:**
```
4. Zero-Result & Interpretation Protocol
- Empty List Detection: If a SQL query returns an empty list [] or COUNT of 0,
  you MUST NOT provide a descriptive summary ... say "Here is the list."
- Explicit Negation: state "There are no [subject] found".
```

---

## 4. Connector Agent Prompts

Each platform agent prompt (`<platform>_system_msg`) follows the **same four-section
structure**, with `SHARED_AGENT_RULES` and the date variables injected at the top:

```
You are an SQLite SQL generation agent operating on a fixed, known database schema.

{SHARED_AGENT_RULES}

Current Date: {current_date_str}
Current Year: {current_year_str}

1. SQL Query Generation & Sequence-Wise Tool Usage
   — how to interpret questions, handle ambiguity, SQL restrictions, error handling,
     and how to summarize results for non-technical users.
2. Tables & Schemas
   — authoritative list of that platform's tables, columns, types, business meaning.
3. Mandatory Relationships & Join Constraints
   — allowed join keys; prevents invalid joins / duplication / data loss.
4. (platform-specific query patterns, examples, date templates)
```

| Section | Role |
|---|---|
| 1. SQL Generation & Tool Usage | Behavior, ambiguity handling, SQL safety, summarization |
| 2. Tables & Schemas | The platform's schema (the connector-specific bulk) |
| 3. Relationships & Joins | Valid join keys, source-of-truth tables |
| 4. Patterns & Examples | Platform-specific query templates (e.g. YTD date ranges) |

The tables each prompt describes match the connector's `TABLE_GROUPS` entry — see
`CONNECTORS_DOCUMENTATION.md`.

---

## 5. Supervisor Prompt

Assembled in `agent.py` from three parts plus the active connectors' configs:

```python
final_supervisor_prompt = (
    SUPERVISOR_HEADER
    + "\n".join(active_descriptions)          # from SUPERVISOR_GROUP_CONFIGS[key]["description"]
    + "\n\nSPECIFIC DELEGATION RULES:"
    + "\n".join(active_rules)                  # from SUPERVISOR_GROUP_CONFIGS[key]["rules"]
    + SUPERVISOR_FOOTER
)
```

Only **active** connectors (the tenant's connected platforms) are included, so the
router never offers an agent that doesn't exist for that tenant.

### 5.1 `SUPERVISOR_HEADER`
Defines the router role and the history protocol:
```
You are a 'Data Router' managing a team of specialist SQL agents.
Your ONLY job is to route user requests to the correct worker agent.
YOU ARE FORBIDDEN FROM ANSWERING DATA QUESTIONS DIRECTLY.
...
Below are the ONLY Agents you can route to:
```

### 5.2 `SUPERVISOR_GROUP_CONFIGS[key]`
Per connector, two strings appended to the prompt:
- **`description`** — what the agent covers and a mandatory-delegation rule.
- **`rules`** — the platform keywords and delegation condition.

(Full per-connector text: see `CONNECTORS_DOCUMENTATION.md` → Routing Reference.)

### 5.3 `SUPERVISOR_FOOTER` — the routing decision logic
The most operationally important block. Ordered routing:

- **STEP 1:** check for a PLATFORM keyword (google/GA, facebook/fb, linkedin/ln,
  instagram/insta, shopify).
- **STEP 2:** **no** platform keyword → call **ALL** available agents (generic query).
- **STEP 3:** platform keyword present → platform-specific routing, including the two
  ambiguous cases:
  - `google`/`GA` + ad keywords → GoogleAds; + analytics keywords → GoogleAnalytics;
    alone → both.
  - `linkedin`/`ln` + ads-metric → LinkedInAds; + pages-metric → LinkedInPages;
    alone → both.
- Plus: Time Period Logic (same as shared rule 3), Consolidated Reporting (single
  sentence when all agents return no data), and a strict **Output Format** for chat
  readability.

---

## 6. How Prompts Are Wired (`agent.py`)

Each prompt is placed in a `ChatPromptTemplate` with an **ephemeral cache
breakpoint** on the system block (so the static prompt prefix is cached):

```python
# Connector agent
prompt = ChatPromptTemplate.from_messages([
    ("system", [{"type": "text", "text": system_msg,
                 "cache_control": {"type": "ephemeral"}}]),
    MessagesPlaceholder("messages"),
    MessagesPlaceholder("agent_scratchpad"),
])

# Supervisor
supervisor_prompt = ChatPromptTemplate.from_messages([
    ("system", [{"type": "text", "text": final_supervisor_prompt,
                 "cache_control": {"type": "ephemeral"}}]),
    MessagesPlaceholder("messages"),
    MessagesPlaceholder("agent_scratchpad"),
])
```

`MessagesPlaceholder("messages")` injects conversation history (last 10 messages);
`agent_scratchpad` holds the tool-calling loop state.

---

## 7. Prompt Sizes (measured, `claude-opus-4-8`)

These are the cached prefixes; all exceed Opus's 4,096-token cache minimum.

| Prompt | Tokens |
|---|---:|
| Supervisor (header+rules+footer) | 4,605 |
| InstagramAgent | 6,886 |
| ShopifyAgent | 7,430 |
| GoogleAdsAgent | 9,014 |
| LinkedInPagesAgent | 9,868 |
| LinkedInAgent | 10,842 |
| FacebookAdsAgent | 12,987 |
| GoogleAnalyticsAgent | 15,836 |
| `SHARED_AGENT_RULES` (inside each) | 1,553 |

---

## 8. Worked Example — Basic Request → Prompts → Response

This traces one `/chat` call end-to-end, showing where each prompt is used and the
actual request/response at each step.

### Step 0 — Client request (HTTP)
```json
POST /chat
Authorization: Bearer <jwt>
{ "query": "What were my top traffic channels last month?", "thread_id": "client_1" }
```

### Step 1 — Supervisor LLM call (routing)
The assembled **supervisor prompt** is the system message; the user query is the
message. Request sent to Claude:
```jsonc
POST https://api.anthropic.com/v1/messages
{
  "model": "claude-opus-4-8",
  "max_tokens": 128000,
  "system": [
    { "type": "text",
      "text": "You are a 'Data Router'... Below are the ONLY Agents you can route to: ...",
      "cache_control": { "type": "ephemeral" } }          // SUPERVISOR_HEADER + group configs + FOOTER
  ],
  "tools": [ { "name": "GoogleAnalyticsAgent", ... }, { "name": "GoogleAdsAgent", ... }, ... ],
  "messages": [ { "role": "user", "content": "What were my top traffic channels last month?" } ]
}
```
**Routing decision** (per `SUPERVISOR_FOOTER` STEP 3): keyword *"traffic / channels"* →
analytics metric → **GoogleAnalyticsAgent only**. Claude returns a `tool_use` block
calling `GoogleAnalyticsAgent`.

### Step 2 — Connector (GA4) LLM call (SQL generation)
The **`google_analytics_system_msg`** prompt is the system message; the routed query
is the input. Request sent to Claude:
```jsonc
{
  "model": "claude-opus-4-8",
  "max_tokens": 128000,
  "system": [
    { "type": "text",
      "text": "You are an SQLite SQL generation agent... {SHARED_AGENT_RULES} ... Tables & Schemas: geo, campaign, demochannel, pages ...",
      "cache_control": { "type": "ephemeral" } },
  ],
  "tools": [ { "name": "sql_db_query", ... }, { "name": "sql_db_schema", ... }, ... ],   // SQL toolkit
  "messages": [ { "role": "user", "content": "Show top traffic channels for last month" } ]
}
```
The agent runs the SQL toolkit loop (inspect schema → write SQL → execute), e.g.:
```sql
SELECT channel, SUM(sessions) AS sessions
FROM demochannel
WHERE date >= '2026-05-01' AND date <= '2026-05-31'
GROUP BY channel ORDER BY sessions DESC LIMIT 3;
```
Result rows returned to the agent → it summarizes (per `SHARED_AGENT_RULES` #5,
explicit values).

### Step 3 — Supervisor synthesizes → HTTP response
The supervisor composes the final answer and the API returns:
```json
{
  "response": "Last month your top traffic channels were Organic Search (20,050 sessions), Paid Search (13,700), and Direct (8,310).",
  "thread_id": "client_1",
  "connected_platforms": ["google_analytics", "google_ads"]
}
```

### Prompt-rule effects visible in this flow
| Rule | Effect here |
|---|---|
| `SUPERVISOR_FOOTER` STEP 3 | Routed to GA4 (not Google Ads) on the "traffic/channels" keyword |
| `SHARED_AGENT_RULES` #3 (Time Logic) | "last month" → explicit date filter `2026-05-01..2026-05-31` |
| `SHARED_AGENT_RULES` #6 (Date Strictness) | Numeric date boundaries, not `LIKE` |
| `SHARED_AGENT_RULES` #5 (Explicit Answer) | Channel names + session counts stated inline |
| `SHARED_AGENT_RULES` #4 (Zero-Result) | If no rows: "There are no channels found for last month" |

> The `response` values are illustrative (depend on live tenant data); the request
> shapes, routing, and rule effects are exact. A follow-up like *"break it down"* in
> the same `thread_id` would inherit platform + timeframe via `SHARED_AGENT_RULES` #1.

---

## 9. Maintenance Notes

- **Edit prompts in `system_msg.py` only.** `agent.py` assembles them; it does not
  contain prompt text.
- **Adding a connector:** add its `<platform>_system_msg`, a `SUPERVISOR_GROUP_CONFIGS`
  entry (description + rules), wire it in `agent.py` (`add_tool_if_exists`,
  `TABLE_GROUPS`, `TYPE_TO_AGENT_KEY` in `main.py`), and follow the four-section
  structure.
- **Keep routing keywords in sync** across `SUPERVISOR_GROUP_CONFIGS[*]["rules"]` and
  `SUPERVISOR_FOOTER` STEP 3 — both encode the same routing and must agree.
- **Avoid volatile content** (timestamps, IDs) in prompt bodies beyond the existing
  date variables, to preserve prompt-cache hit rates.
- **Answer-quality rules** (explicit values, zero-result negation, no "shown above")
  live in `SHARED_AGENT_RULES` — change once, applies to all agents.

---

*For connector domains/tables see `CONNECTORS_DOCUMENTATION.md`; for the LLM layer
see `CLAUDE_INTEGRATION.md`.*
