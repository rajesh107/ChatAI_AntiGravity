import os
import sys
import operator
import pandas as pd # Required for merging logic

# Force UTF-8 output on Windows to prevent emoji UnicodeEncodeError
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")
import pickle
import zlib
from datetime import datetime, timedelta, date 
from typing import TypedDict, List, Annotated
from dotenv import load_dotenv
from urllib.parse import quote_plus

# Redis Imports
from redis import Redis
from langgraph.checkpoint.redis import RedisSaver

# SQLAlchemy
from sqlalchemy import create_engine, inspect
from sqlalchemy.pool import StaticPool

# LangChain / LangGraph
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_anthropic import ChatAnthropic
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain.agents.agent import RunnableMultiActionAgent
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools import Tool
from langgraph.graph import StateGraph, END

# Local Imports
from etl_cleaner import clean_and_load_data, TABLE_CONFIGS
from system_msg import (
    instagram_system_msg, facebook_system_msg, google_system_msg,
    linkedin_system_msg, shopify_system_msg, google_analytics_system_msg,
    linkedin_pages_system_msg,
    SUPERVISOR_HEADER, SUPERVISOR_GROUP_CONFIGS, SUPERVISOR_FOOTER, SHARED_AGENT_RULES
)

load_dotenv()

# --- Anthropic (Claude) Configuration ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise RuntimeError(
        "ANTHROPIC_API_KEY environment variable is required. "
        "Add it to your .env (ANTHROPIC_API_KEY=sk-ant-...) and restart."
    )

# --- Connector Database Configuration ---
conn_user = os.getenv("Connector_USER", "root")
conn_password = os.getenv("Connector_PASSWORD", "")
conn_host = os.getenv("Connector_HOST", "localhost")
conn_port = os.getenv("Connector_PORT", "3306")
encoded_conn_user = quote_plus(conn_user)
encoded_conn_password = quote_plus(conn_password)

REDIS_URL = os.getenv("REDIS_URL")
if not REDIS_URL:
    raise RuntimeError("REDIS_URL environment variable is required")
TARGET_REDIS_URL = REDIS_URL

def _make_redis_client():
    """Creates a Redis client with connection health settings to handle remote resets (10054)."""
    return Redis.from_url(
        TARGET_REDIS_URL,
        decode_responses=False,
        socket_keepalive=True,
        socket_connect_timeout=10,
        socket_timeout=30,
        retry_on_timeout=True,
        health_check_interval=30,
    )

def _get_redis_client():
    """Returns a live Redis client, reconnecting if the previous connection was dropped."""
    global redis_client_global
    try:
        if redis_client_global:
            redis_client_global.ping()
            return redis_client_global
    except Exception:
        pass
    try:
        redis_client_global = _make_redis_client()
        redis_client_global.ping()
        print("✅ [REDIS] Reconnected.")
    except Exception as e:
        print(f"❌ [REDIS] Reconnect failed: {e}")
        redis_client_global = None
    return redis_client_global

# Initialize Global Redis Client
try:
    redis_client_global = _make_redis_client()
    redis_client_global.ping()
    print("✅ [INIT] Global Redis Connection Established.")
except Exception as e:
    print(f"❌ [INIT] Global Redis Connection Failed: {e}")
    redis_client_global = None

# Cache Duration: 24 Hours (in seconds)
DATA_CACHE_TTL = 86400

# Graph cache TTL: 1 hour — ensures fresh DB data after each Fivetran sync
GRAPH_CACHE_TTL = 3600

# Model id used for every agent.
MODEL_ID = "claude-opus-4-8"

def _get_model_max_output_tokens(model_id: str, fallback: int = 16000) -> int:
    """Fetch the model's real max output-token limit from the Anthropic Models API
    so we never hard-code a cap. Answers are then bounded only by what the model
    can actually produce. Falls back if the API is unreachable."""
    try:
        import httpx
        resp = httpx.get(
            f"https://api.anthropic.com/v1/models/{model_id}",
            headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01"},
            timeout=10,
        )
        resp.raise_for_status()
        n = int(resp.json()["max_tokens"])
        print(f"   [MODEL] {model_id} max output = {n} tokens (from Models API)")
        return n
    except Exception as e:
        print(f"   [MODEL] max-output lookup failed ({e}); using fallback {fallback}")
        return fallback

# Resolved once at startup — the model's true output ceiling, not a magic number.
MODEL_MAX_OUTPUT_TOKENS = _get_model_max_output_tokens(MODEL_ID)

# --- Global Cache ---
# Stores {user_id: (compiled_app, build_timestamp)}
GRAPH_CACHE = {}
ENGINE_CACHE = {}

# --- Table Definitions ---
TABLE_GROUPS = {
    "google_ads": [
        "campaign_conversion_goal_history",
        "campaign_history",
        "campaign_stats"
    ],
    "shopify": [
        "order",
        "order_line",
        "order_line_refund",
        "product"
    ],
    "linkedin": [
        "ad_analytics_by_creative",
        "campaign_history",
        "creative_history",
        "post_history"
    ],
    "facebook": [
        "ad_conversion",
        "ad_history",
        "basic_ad",
        "basic_campaign",
        "basic_campaign_actions",
        "daily_page_metrics_total",
        "campaign_history"
    ],
    "instagram": [
        "media_history",
        "media_insights",
        "user_history",
        "user_insights",
        "user_lifetime_insights"
    ],
    "google_analytics": [
        "geo",
        "campaign",
        "categorylabel",
        "adslot",
        "demochannel",
        "pages",
        "tech_device_category_report",
        "tech_device_model_report",
        "tech_platform_device_category_report"
    ],
    "linkedin_pages": [
        "organization",
        "time_bound_follower_statistic",
        "time_bound_share_statistic",
        "time_bound_page_statistic"
    ]
}


def get_connector_mysql_uri(database_name):
    return f"mysql+pymysql://{encoded_conn_user}:{encoded_conn_password}@{conn_host}:{conn_port}/{database_name}"


def create_merged_engine(user_id: str, db_name_list: List[str], group_key: str):
    """
    Creates an In-Memory SQLite engine.
    Logic:
    1. Check Redis for cached data (Key: data_cache:{user_id}:{group_key}).
    2. IF CACHED: Load directly from Redis (skip MySQL).
    3. IF NOT CACHED: Fetch from MySQL, Clean, Save to Redis (TTL 24h), then Load.
    """
    
    # 1. Create In-Memory SQLite Engine
    sqlite_engine = create_engine(
        "sqlite:///:memory:", 
        connect_args={'check_same_thread': False}, 
        poolclass=StaticPool
    )

    # Redis Cache Key
    cache_key = f"data_cache:{user_id}:{group_key}"
    
    data_payload = None
    
    # 2. Try Fetching from Redis
    r = _get_redis_client()
    if r:
        try:
            cached_bytes = r.get(cache_key)
            if cached_bytes:
                print(f"   ⚡ [CACHE HIT] Loading '{group_key}' data from Redis for {user_id}...")
                data_payload = pickle.loads(zlib.decompress(cached_bytes))
            else:
                print(f"   🐢 [CACHE MISS] '{group_key}' not in Redis. Fetching from MySQL...")
        except Exception as e:
            print(f"   ⚠️ [CACHE ERR] Redis lookup failed: {e}")

    # 3. If Payload is Empty (Cache Miss), Fetch from MySQL
    if not data_payload:
        data_payload = {} # Structure: { 'table_name': {'df': dataframe, 'dtype': dtype_mapping} }
        required_tables = TABLE_GROUPS.get(group_key, [])

        for db_name in db_name_list:
            mysql_uri = get_connector_mysql_uri(db_name)
            try:
                mysql_engine = create_engine(mysql_uri)
                inspector = inspect(mysql_engine)
                existing_tables = set(inspector.get_table_names())
                
                for table in required_tables:
                    if table in existing_tables:
                        try:
                            # Read raw data
                            df = pd.read_sql(f"SELECT * FROM `{table}`", con=mysql_engine)
                            if not df.empty:
                                df['_source_db'] = db_name
                                
                                # Clean data BUT DO NOT WRITE YET (return_only=True)
                                cleaned_df, dtype_map = clean_and_load_data(df, table, return_only=True)
                                
                                # If table exists in payload (merging multiple DBs), append
                                if table in data_payload:
                                    existing_df = data_payload[table]['df']
                                    merged_df = pd.concat([existing_df, cleaned_df], ignore_index=True)
                                    data_payload[table]['df'] = merged_df
                                else:
                                    data_payload[table] = {
                                        'df': cleaned_df,
                                        'dtype': dtype_map
                                    }
                                
                                print(f"         📥 [FETCHED] {table} from {db_name}")
                        except Exception as e:
                            print(f"         ⚠️ [ERR] Fetching {table}: {e}")
                
                mysql_engine.dispose()
            except Exception as e:
                print(f"      ❌ [FAIL] MySQL Connect Error {db_name}: {e}")

        # 4. Save to Redis (if we have data)
        r = _get_redis_client()
        if r and data_payload:
            try:
                # COMPRESS HERE
                pickled_data = pickle.dumps(data_payload)
                compressed_data = zlib.compress(pickled_data)

                r.setex(
                    name=cache_key,
                    time=DATA_CACHE_TTL,
                    value=compressed_data
                )
                
                original_size = len(pickled_data) / 1024
                compressed_size = len(compressed_data) / 1024
                print(f"   💾 [CACHE SAVE] Saved '{group_key}' to Redis.")
                print(f"      📊 Size: {original_size:.2f}KB -> {compressed_size:.2f}KB (Saved {100-(compressed_size/original_size*100):.1f}%)")
                
            except Exception as e:
                print(f"   ⚠️ [CACHE SAVE FAIL] Could not save to Redis: {e}")
                
    # 5. Load Data into SQLite Engine (From Payload)
    if data_payload:
        print(f"   🚀 [LOADING] Writing {len(data_payload)} tables to In-Memory SQL Engine...")
        for table, content in data_payload.items():
            try:
                content['df'].to_sql(
                    name=table,
                    con=sqlite_engine,
                    if_exists='replace', # Payload already merged DBs, so we just write once
                    index=False,
                    dtype=content['dtype'],
                    chunksize=1000
                )
            except Exception as e:
                 print(f"      ❌ [WRITE ERR] {table}: {e}")
    else:
        print(f"      ⚠️ [EMPTY] No data found for group '{group_key}'")

    return sqlite_engine

def _content_to_text(content) -> str:
    """Normalize LLM message content to a plain string.

    ChatOpenAI returns `content` as a str, but ChatAnthropic returns a list of
    content blocks (e.g. [{'type': 'text', 'text': '...'}]). Flatten those to text.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(block.get("text", ""))
            else:
                parts.append(str(block))
        return "".join(parts)
    return str(content)


# --- AUTO-CONTINUING LLM ---
class CompletingChatAnthropic(ChatAnthropic):
    """ChatAnthropic that finishes answers cut off by the output-token cap.

    Anthropic sets stop_reason == "max_tokens" when the model hits `max_tokens`
    mid-answer (a truncated response). For a plain-text answer we re-prompt the
    model to continue and stitch the parts together until it stops on its own
    (end_turn / stop_sequence), so callers always get the complete response.

    Only runs on `_generate` (non-streaming), so the LLM must be built with
    streaming=False. Truncations that happen while emitting a tool call are left
    alone — continuing those would corrupt the tool-call JSON.
    """

    max_continuations: int = 4

    @staticmethod
    def _stop_reason(chat_result):
        # At _generate time, stop_reason lives in ChatResult.llm_output — the
        # message's response_metadata isn't populated until langchain-core merges
        # it in after this method returns.
        return (chat_result.llm_output or {}).get("stop_reason")

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        result = super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
        gen = result.generations[0]
        msg = gen.message

        # Don't touch tool-call turns — only complete plain-text answers.
        if getattr(msg, "tool_calls", None):
            return result
        if self._stop_reason(result) != "max_tokens":
            return result

        merged_text = _content_to_text(msg.content)
        convo = list(messages)
        last_msg = msg
        last_result = result

        for _ in range(self.max_continuations):
            convo = convo + [
                AIMessage(content=last_msg.content),
                HumanMessage(content=(
                    "Your previous response was cut off because it hit the length "
                    "limit. Continue from exactly where you stopped. Do not repeat "
                    "anything you already wrote, and do not add a preamble."
                )),
            ]
            cont = super()._generate(convo, stop=stop, run_manager=run_manager, **kwargs)
            cont_msg = cont.generations[0].message
            # A tool call should never appear here, but if it does, stop stitching.
            if getattr(cont_msg, "tool_calls", None):
                break
            merged_text += _content_to_text(cont_msg.content)
            last_msg = cont_msg
            last_result = cont
            if self._stop_reason(cont) != "max_tokens":
                break
        else:
            print("   ⚠️ [LLM] Hit max_continuations; answer may still be truncated.")

        # Return one assistant message carrying the fully stitched answer, and
        # surface the final (non-truncated) llm_output so stop_reason reads correctly.
        gen.message = AIMessage(
            content=merged_text,
            response_metadata={**(last_result.llm_output or {})},
            usage_metadata=getattr(last_msg, "usage_metadata", None),
        )
        # gen.text derives from gen.message automatically (read-only property).
        result.llm_output = last_result.llm_output
        return result


# --- CUSTOM REDUCER FUNCTION ---
def trim_conversation_history(current_messages: List[BaseMessage], new_messages: List[BaseMessage]) -> List[BaseMessage]:
    if not current_messages:
        current_messages = []
    all_messages = current_messages + new_messages
    if len(all_messages) > 10:
        return all_messages[-10:]
    return all_messages

def get_compiled_graph(user_id: str, active_db_map: dict):
    # active_db_map is now Dict[str, List[str]]
    # Key: 'facebook', Value: ['fb_ajinkya_1', 'fb_ajinkya_2']

    now_ts = datetime.now().timestamp()
    if user_id in GRAPH_CACHE:
        cached_app, cached_ts = GRAPH_CACHE[user_id]
        if now_ts - cached_ts < GRAPH_CACHE_TTL:
            return cached_app
        del GRAPH_CACHE[user_id]
        print(f"   ♻️ [CACHE EXPIRED] Graph cache expired for {user_id}, rebuilding...")

    print(f"\n⚙️ [BUILD] Building Agent Graph for User: {user_id}")

    # Allow the model's full output capacity so a single answer is never
    # artificially capped. CompletingChatAnthropic still watches stop_reason and
    # continues past the cap if ever hit, so the complete response is returned.
    # streaming=False because the continuation logic runs in _generate.
    llm = CompletingChatAnthropic(
        model=MODEL_ID,
        max_tokens=MODEL_MAX_OUTPUT_TOKENS,
        streaming=False,
        api_key=ANTHROPIC_API_KEY,
    )

    # --- 1. Helper to build sub-agents ---
    def create_agent_tool(group_key, system_msg, agent_name, tool_description):
        if group_key not in active_db_map:
            return None

        # Get List of DBs
        db_list = active_db_map[group_key]
        
        # CREATE THE ENGINE (Merged or Single)
        try:
            # We treat everything as a "Merge" operation to unify the logic.
            engine = create_merged_engine(user_id, db_list, group_key)
            
            # Verify tables in the new SQLite Engine
            inspector = inspect(engine)
            available_tables = inspector.get_table_names()
            
            if not available_tables:
                print(f"      ⚠️ [SKIP] {agent_name} has no tables after merge.")
                return None

            print(f"      ✅ [READY] {agent_name} has tables: {available_tables}")

            # Initialize LangChain SQL Tool
            db_instance = SQLDatabase(engine=engine)
            toolkit = SQLDatabaseToolkit(db=db_instance, llm=llm)
            tools = toolkit.get_tools()

            # cache_control on the system block caches the (tools + large system
            # prompt) prefix so repeat turns read it at ~0.1x cost instead of full price.
            prompt = ChatPromptTemplate.from_messages([
                ("system", [{
                    "type": "text",
                    "text": system_msg,
                    "cache_control": {"type": "ephemeral"},
                }]),
                MessagesPlaceholder(variable_name="messages"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ])
            
            # stream_runnable=False forces AgentExecutor to call the LLM via
            # _generate (not _stream), so CompletingChatAnthropic's continuation
            # logic runs and truncated answers are completed end-to-end.
            agent = RunnableMultiActionAgent(
                runnable=create_tool_calling_agent(llm, tools, prompt),
                stream_runnable=False,
            )
            agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

            def run_agent(query: str):
                _now = datetime.now()
                response = agent_executor.invoke({
                    "messages": [HumanMessage(content=query)],
                    "current_date_str": _now.strftime("%Y-%m-%d"),
                    "current_year_str": _now.strftime("%Y"),
                    "SHARED_AGENT_RULES": SHARED_AGENT_RULES,
                    "recent_start_date_str": (_now - timedelta(days=30)).strftime("%Y-%m-%d")
                })
                return _content_to_text(response['output'])

            return Tool(name=agent_name, func=run_agent, description=tool_description)
        
        except Exception as e:
            print(f"      ❌ [FAIL] Tool Creation Failed {agent_name}: {e}")
            return None

    # --- 2. Register Tools ---
    tools_for_supervisor = []
    active_descriptions = []
    active_rules = []

    def add_tool_if_exists(key, sys_msg, name):
        # We only check if the KEY exists in the map
        if key in active_db_map:
            tool = create_agent_tool(
                key, sys_msg, name, 
                SUPERVISOR_GROUP_CONFIGS[key]["description"]
            )
            if tool:
                tools_for_supervisor.append(tool)
                active_descriptions.append(SUPERVISOR_GROUP_CONFIGS[key]["description"])
                active_rules.append(SUPERVISOR_GROUP_CONFIGS[key]["rules"])

    # Register keys (Map matches main.py TYPE_TO_AGENT_KEY values)
    add_tool_if_exists("google_ads", google_system_msg, "GoogleAdsAgent")
    add_tool_if_exists("shopify", shopify_system_msg, "ShopifyAgent")
    add_tool_if_exists("linkedin", linkedin_system_msg, "LinkedInAgent")
    add_tool_if_exists("facebook", facebook_system_msg, "FacebookAdsAgent")
    add_tool_if_exists("instagram", instagram_system_msg, "InstagramAgent")
    add_tool_if_exists("google_analytics", google_analytics_system_msg, "GoogleAnalyticsAgent")
    add_tool_if_exists("linkedin_pages", linkedin_pages_system_msg, "LinkedInPagesAgent")

    if not tools_for_supervisor:
        raise ValueError(f"No active platforms found for User '{user_id}'.")

    # --- 3. Supervisor Setup ---
    final_supervisor_prompt = (
        SUPERVISOR_HEADER + 
        "\n".join(active_descriptions) + 
        "\n\nSPECIFIC DELEGATION RULES:" + 
        "\n".join(active_rules) + 
        SUPERVISOR_FOOTER
    )

    supervisor_prompt = ChatPromptTemplate.from_messages([
        ("system", [{
            "type": "text",
            "text": final_supervisor_prompt,
            "cache_control": {"type": "ephemeral"},
        }]),
        MessagesPlaceholder(variable_name="messages"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    
    # stream_runnable=False so the supervisor's final answer also goes through
    # _generate and gets completed if it hits the token cap.
    supervisor_agent = RunnableMultiActionAgent(
        runnable=create_tool_calling_agent(llm, tools_for_supervisor, supervisor_prompt),
        stream_runnable=False,
    )
    supervisor_executor = AgentExecutor(agent=supervisor_agent, tools=tools_for_supervisor, verbose=True)

    class AgentState(TypedDict):
        messages: Annotated[List[BaseMessage], operator.add]
    
    def supervisor_node(state):
        # 1. Get precise time to force a context shift (The LLM sees "Time has moved forward")
        current_time_str = datetime.now().strftime("%H:%M:%S")
        
        # 2. Create a "Ghost" Instruction
        # This message is appended to the input but NOT saved to the graph state.
        # It forces the LLM to disregard the previous turn's answer.
    #     enforcement_instruction = HumanMessage(
    #         content=f"""[SYSTEM PROTOCOL ENFORCEMENT - TIME: {current_time_str}]
    # 1. IGNORE the answer in the message history above.
    # 2. The user requires FRESH Real-Time data.
    # 3. You MUST call the relevant tool again. 
    # 4. DO NOT answer from memory."""
    #     )
    
    # 3. Combine existing history with the enforcement instruction
    # We create a new list so we don't pollute the actual persistent state
        messages_for_llm = state["messages"]
        _now = datetime.now()

        result = supervisor_executor.invoke({
            "messages": messages_for_llm,
            "current_date_str": _now.strftime("%Y-%m-%d"),
            "current_year_str": _now.strftime("%Y"),
        })
    
        return {"messages": [HumanMessage(content=_content_to_text(result["output"]), name="Supervisor")]}

    workflow = StateGraph(AgentState)
    workflow.add_node("supervisor", supervisor_node)
    workflow.set_entry_point("supervisor")
    workflow.add_edge("supervisor", END)

     # --- REDIS CHECKPOINTER ---
    try:
        # Re-use global client if available, or create new
        r_check = _get_redis_client()
        if r_check:
            checkpointer = RedisSaver(redis_client=r_check)
        else:
            checkpointer = None
            
        checkpointer.setup()
        print("   ✅ [REDIS] Checkpointer initialized.")
    except Exception as e:
        print(f"   ⚠️ [REDIS] Checkpointer Failed: {e}")
        checkpointer = None

    app = workflow.compile(checkpointer=checkpointer)
    GRAPH_CACHE[user_id] = (app, datetime.now().timestamp())
    return app




