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

Look at sql_results first (raw data), then agent_response. Determine the shape:

A. Does the data have a DATE or TIME column (day, month, week, year)? → TIME SERIES → LINE chart
B. Does the data have 2–6 named parts summing to a whole (organic vs paid, desktop vs mobile)? → PROPORTIONAL → PIE chart
C. Multiple items ranked by one metric (top campaigns, regions, ads)? → CATEGORY COMPARISON → BAR chart
D. One item with multiple metrics (e.g. one ad: CPC + clicks + spend)? → reshape to [{metric, value}] → BAR chart
E. Multiple items × multiple metrics (e.g. org × device)? → GROUPED BAR with color encoding

## STEP 2 — MULTI-METRIC DAILY/MONTHLY DATA (most important case):

When the data is a daily or monthly breakdown with MULTIPLE metrics per row (e.g. page_views + impressions + followers per day):
- Pick the MOST IMPORTANT single metric for the chart (impressions > page_views > followers, or whatever is most relevant to the question)
- Use LINE chart with x=date, y=that metric
- In spec.data.values include ALL date rows with that metric value
- NEVER skip dates to save space — include every row from sql_results
- If there are multiple metrics and they are on similar scales, use color encoding to show multiple series on one LINE chart
- ALWAYS prefer sql_results over agent_response for extracting data values (raw data is more reliable)

## STEP 3 — CHART SPECS:

**LINE chart:**
- x: date field (type: "ordinal"), y: metric (type: "quantitative")
- Add color encoding if showing 2–3 metrics as separate lines

**PIE chart:**
- theta: value field (quantitative), color: label field (nominal)
- Also set x.field="label", x.type="nominal", x.title="" and y.field="value", y.type="quantitative", y.title="" as placeholders

**BAR chart:** x: category (nominal), y: value (quantitative)
**GROUPED BAR:** x: primary category, y: value, color: grouping field

## STEP 4 — WHEN TO USE PROMPT INSTEAD:
ONLY when the response is a SINGLE number, a yes/no answer, or contains zero numeric data. ANY breakdown across 2+ dates/items/categories → always use chart.

## RULES:
- library: always "plotly"
- Extract data values from sql_results (preferred) or agent_response — never empty
- Do NOT skip rows to save space — include all data points
- Never decide chart type from question keywords — use DATA SHAPE only
- Return 1 chart recommendation (the most useful visualization)
- Optionally add 1 follow-up prompt as a second recommendation when a drill-down is natural
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
            max_tokens=4096,
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
