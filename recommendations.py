import os
import anthropic
from dotenv import load_dotenv

load_dotenv()

import time

_client = None

def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            max_retries=0,  # we handle retries manually below
        )
    return _client


def _call_with_retry(client, **kwargs):
    """Call client.messages.create with exponential backoff on 529 overloaded errors."""
    delays = [5, 15, 30]
    for attempt, delay in enumerate(delays + [None]):
        try:
            return client.messages.create(**kwargs)
        except anthropic.APIStatusError as e:
            if e.status_code == 529 and delay is not None:
                print(f"[RECOMMENDATIONS] Anthropic overloaded (529), retrying in {delay}s (attempt {attempt+1}/3)...")
                time.sleep(delay)
                continue
            raise
        except anthropic.APIConnectionError:
            if delay is not None:
                print(f"[RECOMMENDATIONS] Connection error, retrying in {delay}s...")
                time.sleep(delay)
                continue
            raise


_RECOMMENDATION_TOOL = {
    "name": "generate_recommendations",
    "description": "Generate structured chart or prompt recommendations based on query results.",
    "input_schema": {
        "type": "object",
        "properties": {
            "recommendations": {
                "type": "array",
                "minItems": 1,
                "maxItems": 2,
                "items": {
                    "type": "object",
                    "properties": {
                        "kind": {
                            "type": "string",
                            "enum": ["prompt", "chart"]
                        },
                        "label": {"type": "string"},
                        "prompt": {"type": "string"},
                        "library": {
                            "type": "string",
                            "enum": ["plotly"]
                        },
                        "spec": {
                            "type": "object",
                            "properties": {
                                "data": {
                                    "type": "object",
                                    "properties": {
                                        "values": {
                                            "type": "array",
                                            "items": {"type": "object"}
                                        }
                                    },
                                    "required": ["values"]
                                },
                                "mark": {
                                    "type": "string",
                                    "enum": ["bar", "line", "pie", "scatter"]
                                },
                                "encoding": {
                                    "type": "object",
                                    "properties": {
                                        "x": {
                                            "type": "object",
                                            "properties": {
                                                "field": {"type": "string"},
                                                "type":  {"type": "string"},
                                                "title": {"type": "string"}
                                            },
                                            "required": ["field", "type", "title"]
                                        },
                                        "y": {
                                            "type": "object",
                                            "properties": {
                                                "field": {"type": "string"},
                                                "type":  {"type": "string"},
                                                "title": {"type": "string"}
                                            },
                                            "required": ["field", "type", "title"]
                                        },
                                        "color": {
                                            "type": "object",
                                            "properties": {
                                                "field": {"type": "string"},
                                                "type":  {"type": "string"},
                                                "title": {"type": "string"}
                                            }
                                        },
                                        "theta": {
                                            "type": "object",
                                            "properties": {
                                                "field": {"type": "string"},
                                                "type":  {"type": "string"},
                                                "title": {"type": "string"}
                                            }
                                        }
                                    }
                                }
                            },
                            "required": ["data", "mark", "encoding"]
                        }
                    },
                    "required": ["kind", "label"]
                }
            }
        },
        "required": ["recommendations"]
    }
}

_SYSTEM_PROMPT = """You are an assistant that generates chart recommendations for a marketing analytics chatbot.

You receive:
  - user_question: what the user asked
  - agent_response: the formatted text answer from the chatbot
  - sql_results: raw SQL tool outputs (may contain numeric rows)
  - chat_history: prior conversation turns

## STEP 1 — PICK THE SINGLE BEST CHART TYPE (from data shape only):

Look at sql_results first, then agent_response. Choose EXACTLY ONE chart type:

**LINE** — data has a date/time column (daily, monthly, weekly breakdown)
  x=date, y=primary metric; add color encoding if multiple orgs/series exist

**PIE** — data has 2-6 named parts making up a whole (organic vs paid, desktop vs mobile, share of total)
  theta=value, color=label

**BAR** — everything else: category rankings, multi-metric summaries, single-entity multi-metric
  x=category, y=value; use color for grouping when multiple dimensions exist
  For single entity with multiple metrics: reshape to [{metric, value}, ...]

## STEP 2 — ALWAYS EXACTLY ONE CHART:

Generate EXACTLY ONE chart recommendation. Never generate multiple charts.

For multi-metric data (page_views + impressions + followers):
- If data has dates → LINE chart; pick the most relevant metric as y-axis; use color=org if multiple orgs
- If data is a summary (no dates) → BAR chart; pick most important metric as y-axis OR use grouped bar with color=metric

For multi-org + multi-metric daily data:
- ONE LINE chart; x=date, y=the most asked-about metric, color=org
- Each org becomes a separate colored line

## STEP 3 — SPECS:

LINE: x={field,type:"ordinal",title}, y={field,type:"quantitative",title}, optional color={field,type:"nominal",title}
PIE:  theta={field,type:"quantitative"}, color={field,type:"nominal"}, x={field:"label",type:"nominal",title:""}, y={field:"value",type:"quantitative",title:""}
BAR:  x={field,type:"nominal",title}, y={field,type:"quantitative",title}, optional color for grouping

## STEP 4 — SKIP CHART ONLY WHEN:
Response is a single number, yes/no, or zero numeric data. Otherwise always chart.

## RULES:
- library: always "plotly"
- Extract ALL data rows from sql_results (preferred) or agent_response — never empty, never skip rows
- Decide chart type from DATA SHAPE only, never question keywords
- Return 1 chart + optionally 1 follow-up prompt (max 2 total)
"""


def get_recommendations(
    user_question: str,
    agent_response: str,
    sql_results: list,
    chat_history: list
) -> list:
    """
    Returns a list of 1-2 recommendation dicts:
      kind='chart' → {kind, label, library, spec: {data: {values}, mark, encoding}}
      kind='prompt' → {kind, label, prompt}
    """
    user_content = (
        f"user_question: {user_question}\n\n"
        f"agent_response: {agent_response}\n\n"
        f"sql_results: {sql_results}\n\n"
        f"chat_history: {chat_history}"
    )

    try:
        client = _get_client()
        response = _call_with_retry(
            client,
            model="claude-sonnet-4-6",
            max_tokens=8192,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
            tools=[_RECOMMENDATION_TOOL],
            tool_choice={"type": "tool", "name": "generate_recommendations"}
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == "generate_recommendations":
                return block.input.get("recommendations", [])

        return []

    except Exception as e:
        print(f"[RECOMMENDATIONS] Error: {e}")
        return []
