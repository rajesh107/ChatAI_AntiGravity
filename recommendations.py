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
                "maxItems": 5,
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

## STEP 2 — MULTI-METRIC DATA (most important case):

When the response contains MULTIPLE distinct metrics (e.g. page_views + impressions + followers, or CPC + clicks + spend):
- Generate ONE SEPARATE CHART per metric — do NOT combine them into one chart
- Each chart has its own spec.data.values containing only that metric's data
- For time-series (daily/monthly): each metric gets a LINE chart (x=date, y=metric value)
- For single-point multi-metric (e.g. one ad's totals): each metric gets a BAR chart with one bar, OR group them if scales are similar
- NEVER combine metrics with different units/scales (e.g. dollars and counts) onto the same chart
- ALWAYS prefer sql_results over agent_response for extracting data values (raw data is more reliable)
- Include ALL date rows — never skip dates to save space

Example A — single org, multiple metrics → 3 separate LINE charts:
  Chart 1: label="Daily Page Views", data=[{date, page_views}], mark=line, x=date, y=page_views
  Chart 2: label="Daily Post Impressions", data=[{date, impressions}], mark=line, x=date, y=impressions
  Chart 3: label="Daily Followers Gained", data=[{date, followers}], mark=line, x=date, y=followers

Example B — multiple orgs, multiple metrics → one LINE chart per metric, each with color=org:
  Chart 1: label="Daily Page Views by Org", data=[{date, org, page_views}, ...], mark=line,
           x=date, y=page_views, color=org (each org is a separate line)
  Chart 2: label="Daily Post Impressions by Org", data=[{date, org, impressions}, ...], mark=line,
           x=date, y=impressions, color=org
  → This way each metric chart shows all orgs as colored lines

When data has both multiple orgs AND multiple metrics: generate one chart per metric with color=org. Do NOT exceed 4 chart recommendations total.

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
- Return ONE chart per metric when there are multiple metrics (up to 4 charts)
- Optionally add 1 follow-up prompt as the last recommendation when a drill-down is natural
- Single metric → 1 chart only
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
