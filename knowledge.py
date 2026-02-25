"""
Brain.
"""
import os
import json
from pathlib import Path
from datetime import datetime

from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.core.tools import QueryEngineTool, ToolMetadata
from llama_index.core.agent.workflow import ReActAgent, AgentStream, ToolCallResult
from llama_index.core.workflow import Context
from llama_index.core.storage import StorageContext
from llama_index.llms.openai_like import OpenAILike
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
import chromadb

NOTES_DIR = Path(__file__).parent / "KNOWLEDGE"
MEMORY_FILE = Path(__file__).parent / "memory.json"

# If on HF Spaces with persistent storage, use /data
if os.environ.get("SPACE_ID"):
    persistent = Path("/data")
    if persistent.exists():
        MEMORY_FILE = persistent / "memory.json"


TOOL_DESCRIPTION = (
    "Search the notes. Contains political analysis, power structures research, "
    "cultural commentary, personal conversations, diary entries."
)


# === PERSISTENT MEMORY ===

def load_memory():
    """Load persistent memory from disk."""
    if MEMORY_FILE.exists():
        try:
            return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"sessions": [], "insights": []}


def save_memory(memory):
    """Save memory to disk."""
    try:
        MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        MEMORY_FILE.write_text(json.dumps(memory, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"Warning: Could not save memory: {e}")


def record_exchange(memory, user_msg, agent_response, searches):
    """Record a conversation exchange to persistent memory."""
    exchange = {
        "timestamp": datetime.now().isoformat(),
        "user": user_msg,
        "agent": agent_response,
        "searches": searches,
    }

    if not memory.get("sessions"):
        memory["sessions"] = []

    memory["sessions"].append(exchange)
    if len(memory["sessions"]) > 50:
        memory["sessions"] = memory["sessions"][-50:]

    save_memory(memory)


def get_memory_context(memory):
    """Build a memory context string from recent sessions."""
    if not memory.get("sessions"):
        return ""

    recent = memory["sessions"][-5:]
    lines = ["Earlier in this conversation:"]
    for ex in recent:
        lines.append(f"User: {ex['user']}")
        lines.append(f"Response: {ex['agent']}")
        lines.append("")
    return "\n".join(lines)


# === BUILD AGENT ===

def get_api_key():
    """Get DeepSeek API key from environment or file."""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if api_key:
        return api_key
    
    # Try to read from file
    key_file = Path(__file__).parent / "DEEPSEEK_API_KEY.txt"
    if key_file.exists():
        try:
            api_key = key_file.read_text(encoding="utf-8").strip()
            if api_key:
                return api_key
        except Exception:
            pass
    return ""


def build_agent():
    """Build the full agentic pipeline."""
    
    api_key = get_api_key()
    if not api_key:
        print("ERROR: DEEPSEEK_API_KEY not found in environment or DEEPSEEK_API_KEY.txt")
        return None

    llm = OpenAILike(
        model="deepseek-chat",
        api_base="https://api.deepseek.com/v1",
        api_key=api_key,
        is_chat_model=True,
        context_window=64000,
        max_tokens=2048,
        temperature=0.7,
    )

    embed_model = HuggingFaceEmbedding(model_name="all-MiniLM-L6-v2")

    Settings.llm = llm
    Settings.embed_model = embed_model

    if not NOTES_DIR.exists():
        print(f"WARNING: KNOWLEDGE directory not found at {NOTES_DIR}")
        return None

    print("Loading documents from KNOWLEDGE...")
    documents = SimpleDirectoryReader(
        str(NOTES_DIR),
        recursive=True,
        required_exts=[".md", ".txt"],
    ).load_data()
    print(f"Loaded {len(documents)} documents.")

    chroma_client = chromadb.Client()
    chroma_collection = chroma_client.get_or_create_collection("notes")
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    print("Building vector index...")
    index = VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
        show_progress=True,
    )
    print("Index ready.")

    query_engine = index.as_query_engine(similarity_top_k=15)
    notes_tool = QueryEngineTool(
        query_engine=query_engine,
        metadata=ToolMetadata(
            name="search_notes",
            description=TOOL_DESCRIPTION,
        ),
    )

    agent = ReActAgent(
        name="brain",
        tools=[notes_tool],
        llm=llm,
    )

    return agent


async def run_with_trace(agent, ctx, message, memory):
    """Run the agent and capture response."""
    mem_context = get_memory_context(memory)
    augmented = message
    if mem_context:
        augmented = f"{mem_context}\n\n{message}"

    handler = agent.run(augmented, ctx=ctx)

    reasoning_parts = []
    searches = []
    final_text = ""

    async for ev in handler.stream_events():
        if isinstance(ev, AgentStream):
            final_text += ev.delta
        elif isinstance(ev, ToolCallResult):
            searches.append(ev.tool_name)
            reasoning_parts.append({
                "type": "tool_call",
                "tool": ev.tool_name,
                "result_preview": str(ev.tool_output.content)[:300] if ev.tool_output else "N/A",
            })

    response = await handler
    if not final_text:
        final_text = str(response)

    record_exchange(memory, message, final_text, searches)

    return reasoning_parts, final_text, searches


# === STARTUP ===

print("Starting up...")
agent = build_agent()
memory = load_memory()

if agent:
    agent_ctx = Context(agent)
    session_count = len(memory.get("sessions", []))
    print(f"Ready. {session_count} prior exchanges loaded.")
else:
    agent_ctx = None
    print("Failed to start.")
