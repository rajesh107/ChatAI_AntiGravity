# How to Access Anthropic Claude's Messages API through Postman

**Owner:** Rajesh

**Subject:** How to Access Anthropic Claude's Messages API through Postman

---

## Objective of the Document

The objective of this document is to provide a comprehensive guide on how to access
and interact with Anthropic Claude's `https://api.anthropic.com/v1/messages` API
using Postman. The document covers the necessary prerequisites, setup, and
step-by-step instructions to send requests and receive responses from the API.

> **Note:** This project uses **Anthropic Claude** (model `claude-opus-4-8`), not
> OpenAI. The Claude Messages API differs from OpenAI's Chat Completions API in three
> key ways: (1) authentication uses an `x-api-key` header instead of
> `Authorization: Bearer`, (2) a required `anthropic-version` header, and (3)
> `max_tokens` is **required** in the body. The response format also differs (see
> Step 4).

---

## Introduction

Anthropic's Messages API provides advanced conversational AI capabilities. It allows
users to interact with Claude models, such as **Claude Opus 4.8**, to generate
human-like text based on user input. Postman, a popular tool for testing APIs, offers
a convenient way to experiment with the API without writing any code. This guide
details how to configure and test Claude's Messages API using Postman.

---

## Step-by-Step Process

### Step 1: Prerequisites

**Anthropic API Key:**
- Sign up or log in to the Anthropic Console at **https://console.anthropic.com**.
- Navigate to **API Keys** under your account settings and generate an API key
  (format `sk-ant-...`). Copy this key for later use.

**Postman Installation:**
- Download and install Postman from **https://www.postman.com/downloads/** if you
  haven't already.
- Create a Postman account or log in to your existing account.

---

### Step 2: Setting Up Postman

**Create a New Request:**
- Open Postman and click **+ New Tab** or **New Request**.
- Set the request type to **POST**.
- Enter the following URL: `https://api.anthropic.com/v1/messages`

**Add Headers:**
Go to the **Headers** tab in Postman and add the following three key-value pairs:

| Key | Value |
|---|---|
| `x-api-key` | `YOUR_API_KEY` (the key you copied earlier — **no** "Bearer" prefix) |
| `anthropic-version` | `2023-06-01` |
| `Content-Type` | `application/json` |

> ⚠️ **Common mistake:** Claude uses `x-api-key`, **not** `Authorization: Bearer`.
> The `anthropic-version` header is **mandatory** — requests without it are rejected.

---

### Step 3: Configuring the Request Body

**Switch to the Body Tab:**
- Click on the **Body** tab and select the **raw** option.
- Ensure the format is set to **JSON** (use the dropdown on the right).

**Input the JSON Payload:**
Enter the following JSON in the request body. Note that the instruction goes in the
top-level `system` field, and `max_tokens` is **required**.

```json
{
    "model": "claude-opus-4-8",
    "max_tokens": 1024,
    "system": "You are an RDS assistant. Based on the user question, generate a valid RDS SQL query. Return only the query.",
    "messages": [
        {
            "role": "user",
            "content": "Here are the schema details:\nschema : ga4_27_analytics_dev_4231\nTable : geo(date date, property varchar, country varchar, city varchar, screen_page_views bigint, sessions bigint, total_users bigint, active_users bigint, new_users bigint)\nQuestion: show me india records city wise with users count, give me only query"
        }
    ]
}
```

Customize the payload based on your desired input and context.

**Body field reference:**

| Field | Required | Description |
|---|---|---|
| `model` | Yes | The Claude model id, e.g. `claude-opus-4-8` |
| `max_tokens` | **Yes** | Maximum output tokens (a ceiling; you are billed for actual output) |
| `system` | No | System instruction (top-level, **not** a message with `role: "system"`) |
| `messages` | Yes | Conversation array of `{ "role": "user"/"assistant", "content": "..." }` |

---

### Step 4: Sending the Request

**Send the Request:**
- Click the **Send** button in Postman.

**View the Response:**
- After sending, the response from the API appears in the lower panel of Postman.
- The response includes the generated content and metadata.

**Example Response** (a real response from `claude-opus-4-8` for the payload above):

```json
{
    "id": "msg_01QHLT8YhZBUcZsABFXytXfQ",
    "type": "message",
    "role": "assistant",
    "model": "claude-opus-4-8",
    "content": [
        {
            "type": "text",
            "text": "```sql\nSELECT city, SUM(total_users) AS users_count\nFROM ga4_27_analytics_dev_4231.geo\nWHERE country = 'India'\nGROUP BY city;\n```"
        }
    ],
    "stop_reason": "end_turn",
    "stop_sequence": null,
    "usage": {
        "input_tokens": 152,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "output_tokens": 69,
        "service_tier": "standard"
    }
}
```

> **Reading the response (vs OpenAI):**
> - The generated text is in **`content[0].text`** (a list of content blocks), not
>   `choices[0].message.content`.
> - `stop_reason: "end_turn"` means Claude finished naturally. `"max_tokens"` means
>   the answer was cut off — raise `max_tokens` to get the full response.
> - Token usage is under `usage` as `input_tokens` / `output_tokens` (not
>   `prompt_tokens` / `completion_tokens`).

---

## Bowerydata Question for Claude (worked example)

**System instruction:**
```
You are an RDS assistant. Based on the user question, generate a valid RDS SQL query.
Return only the query.
```

**User content (schema + question):**
```
Here are the schema details:
schema : ga4_27_analytics_dev_4231
Table : geo(date date, property varchar, country varchar, city varchar,
            screen_page_views bigint, sessions bigint, total_users bigint,
            active_users bigint, new_users bigint)
Question: show me india records city wise with users count, give me only query
```

**Response (generated SQL):**
```sql
SELECT city, SUM(total_users) AS users_count
FROM ga4_27_analytics_dev_4231.geo
WHERE country = 'India'
GROUP BY city;
```

---

## Quick Reference: OpenAI → Claude (Postman differences)

| | OpenAI Chat Completions | Anthropic Claude Messages |
|---|---|---|
| Endpoint | `api.openai.com/v1/chat/completions` | `api.anthropic.com/v1/messages` |
| Auth header | `Authorization: Bearer <key>` | `x-api-key: <key>` |
| Version header | — | `anthropic-version: 2023-06-01` (required) |
| `max_tokens` | optional | **required** |
| System prompt | message with `role: "system"` | top-level `system` field |
| Answer location | `choices[0].message.content` | `content[0].text` |
| Token usage | `prompt_tokens` / `completion_tokens` | `input_tokens` / `output_tokens` |

---

## cURL Equivalent (optional)

The same request, runnable from a terminal:

```bash
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{
    "model": "claude-opus-4-8",
    "max_tokens": 1024,
    "system": "You are an RDS assistant. Return only the SQL query.",
    "messages": [{"role": "user", "content": "...schema + question..."}]
  }'
```
