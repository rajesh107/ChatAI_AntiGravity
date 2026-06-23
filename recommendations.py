import os
import anthropic
from dotenv import load_dotenv

load_dotenv()

_client = None

def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


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

## STEP 1 — ANALYSE THE DATA STRUCTURE (ignore how the question is phrased):

Look at the sql_results and agent_response to understand the shape of the data:

A. Does the data have a DATE or TIME column (day, month, week, year)?
   → The data is a TIME SERIES → use LINE chart

B. Does the data have exactly 2–6 named parts that together make up a whole (e.g. organic vs paid, desktop vs mobile, channel breakdown summing to 100%)?
   → The data is PROPORTIONAL → use PIE chart

C. Does the data compare MULTIPLE ITEMS across one metric (top N campaigns, regions, orgs, ads)?
   → The data is a CATEGORY COMPARISON → use BAR chart

D. Does the data show ONE ITEM with MULTIPLE METRICS (e.g. one ad: CPC=1.13, clicks=431, spend=487)?
   → Reshape into rows: [{metric, value}, ...] → use BAR chart

E. Does the data compare MULTIPLE ITEMS across MULTIPLE METRICS (e.g. org × device)?
   → use GROUPED BAR chart with color encoding for the second dimension

## STEP 2 — CHART SPECS:

**LINE chart:**
- x: date/month/period field (ordinal or temporal), y: metric (quantitative)
- Add color encoding if comparing multiple series (e.g. organic vs paid over time)

**PIE chart:**
- theta: value field (quantitative), color: label field (nominal)
- Also set x.field="label", x.type="nominal", x.title="" and y.field="value", y.type="quantitative", y.title="" as placeholders

**BAR chart (simple):**
- x: category (nominal), y: value (quantitative)

**BAR chart (grouped):**
- x: primary category (nominal), y: value (quantitative), color: grouping field (nominal)

## STEP 3 — WHEN TO USE PROMPT INSTEAD:
ONLY use kind="prompt" when the response is a SINGLE number, a yes/no, or pure text with zero numeric breakdown. If there is any numeric data across 2+ items → always use chart.

## RULES:
- library: always "plotly"
- Extract REAL data values from sql_results or agent_response into spec.data.values (never empty)
- Never decide chart type based on keywords in the question — decide from DATA SHAPE only
- Return 1 chart + 1 follow-up prompt when a natural drill-down exists
- Return 1 prompt only when truly nothing to chart
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
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
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
