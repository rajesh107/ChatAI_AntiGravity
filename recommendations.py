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
                            "enum": ["vega-lite", "plotly"]
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
                                "mark": {"type": "string"},
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
                                        }
                                    },
                                    "required": ["x", "y"]
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

_SYSTEM_PROMPT = (
    "You are an assistant that decides whether a chatbot response is chartable and generates structured recommendations.\n\n"
    "You will receive:\n"
    "  - user_question: what the user asked\n"
    "  - agent_response: the formatted text answer from the chatbot\n"
    "  - sql_results: raw SQL tool outputs (may contain numeric rows)\n"
    "  - chat_history: prior conversation turns\n\n"
    "Decision rule:\n"
    "  - If the response contains numeric data across categories/time (e.g. sessions by country, spend by campaign, "
    "impressions over time) → kind='chart'\n"
    "  - If the response is a single number, a yes/no, or plain text with no breakdown → kind='prompt' "
    "(suggest a useful follow-up question)\n\n"
    "For kind='chart':\n"
    "  - Extract the actual data values from agent_response or sql_results into spec.data.values as objects\n"
    "  - Always use 'plotly' as library unless user explicitly asked for vega-lite\n"
    "  - Choose appropriate mark: 'bar' for categories, 'line' for time series, 'scatter' for correlations\n"
    "  - spec.data.values MUST contain the real data rows (not empty)\n"
    "  - spec.encoding.x and y MUST both have field, type, title\n\n"
    "For kind='prompt':\n"
    "  - Suggest a specific, actionable follow-up question relevant to the current response\n\n"
    "Generate exactly ONE recommendation."
)


def get_recommendations(
    user_question: str,
    agent_response: str,
    sql_results: list,
    chat_history: list
) -> list:
    """
    Returns a list with ONE recommendation dict:
      kind='chart' → {kind, label, library, spec: {data: {values}, mark, encoding: {x, y}}}
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
