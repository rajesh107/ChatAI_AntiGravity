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

## CHART TYPE SELECTION RULES (follow strictly):

**Use BAR chart when:**
- Multiple items/categories being compared on a single metric (e.g. top 5 campaigns by spend)
- Single item with multiple metrics shown together (e.g. one ad's CPC + clicks + spend) → reshape data: each metric becomes a row {metric, value}
- Geographic breakdown (country/region by follower count, sessions, etc.)
- Platform-wise or org-wise comparison

**Use LINE chart when:**
- Data is across time (daily, weekly, monthly trend)
- Showing growth or change over a period (e.g. follower growth by month, impressions over time)
- Comparing trends across two time periods (e.g. this month vs last month)

**Use PIE chart when:**
- Showing proportions or share of a total (e.g. organic vs paid followers, desktop vs mobile traffic)
- Breaking down a total into 2–6 named parts
- Questions like "what % of...", "how is X distributed", "breakdown of X"
- For pie charts: use theta encoding (for the value) and color encoding (for the category), x/y are not needed — set x.field="label", x.type="nominal", x.title="" and y.field="value", y.type="quantitative", y.title="" as placeholders

**Use PROMPT (follow-up question) when:**
- The response is a single number with no breakdown
- The answer is yes/no or purely qualitative
- There is literally no numeric data to chart

## DECISION PRIORITY:
If the response contains ANY numeric breakdown across categories, time, or metrics → use chart, NOT prompt.
Multi-metric single entity (e.g. CPC=1.13, clicks=431, spend=487) → BAR chart with reshaped data.

## FOR CHARTS:
- library: always "plotly"
- Extract REAL data values from agent_response or sql_results into spec.data.values
- spec.data.values MUST be non-empty with actual numbers from the response
- For BAR: x=category (nominal), y=value (quantitative)
- For LINE: x=date/time (temporal or ordinal), y=metric (quantitative); add color if multiple series
- For PIE: theta=value field, color=label field; still populate x/y as nominal/quantitative placeholders
- For grouped bars (multiple metrics, multiple entities): add color encoding for the grouping field

## OUTPUT:
- Return 1 chart recommendation when data is chartable
- Return 1 chart + 1 prompt when the chart naturally leads to a useful drill-down question
- Return 1 prompt only when there is truly nothing to chart
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
