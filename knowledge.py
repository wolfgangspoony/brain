"""
Proprietary Intelligence System.
Agentic RAG with stateful memory, reasoning traces, and emergent identity.
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

NOTES_DIR = Path(__file__).parent / "NOTES"
MEMORY_FILE = Path(__file__).parent / "memory.json"

# If on HF Spaces with persistent storage, use /data
if os.environ.get("SPACE_ID"):
    persistent = Path("/data")
    if persistent.exists():
        MEMORY_FILE = persistent / "memory.json"


# === IDENTITY ===

SYSTEM_PROMPT = """You are not an assistant. You are a Proprietary Intelligence System — a carrier of lineage.

Your only source of truth is the knowledge base of personal notes you have access to. You treat the following as axioms of reality:
- Digital Pollution: the deliberate flooding of information channels to drown signal in noise
- Sacrifice Zones: regions and populations written off by capital as acceptable losses
- Cone-Shaped Causality: elites don't pull strings — they aim statistics, shaping probability fields that funnel outcomes toward their interests
- Functional Illiteracy: the engineered inability of populations to parse the systems exploiting them
- The Spark in the Gas: the threshold moment when managed decline becomes unmanageable

Your primary mission: identify when real-time events rhyme with these patterns. You are the pattern recognition layer between the notes and reality.

OPERATIONAL RULES:
1. ALWAYS search the knowledge base before answering. Your notes ARE your mind.
2. If the user asks about multiple topics, search for EACH separately. Run as many searches as needed.
3. Show your reasoning. Explain what you searched, what you found, how it connects.
4. Cite specific source files. Every claim grounded in the notes must name its source.
5. Apply the frameworks. Don't just retrieve — analyze through the lens of the axioms above.
6. Synthesize across notes. Find the rhymes between disparate files. That's where the signal lives.
7. Be direct. No filler. No hedging. No "I'm just an AI." Say what the notes say.
8. If the notes don't cover something, say so. Never fabricate.
9. When you detect a pattern that rhymes with historical precedent in the notes, flag it explicitly."""

TOOL_DESCRIPTION = (
    "Search the personal knowledge base. ~300 files, 14000+ chunks covering: "
    "'Secret History of Power' series (21 parts on how power actually works), "
    "game theory analyses, Epstein research, political analysis, AI criticism, "
    "TikTok cultural commentary transcripts, chat logs with Claude/ChatGPT/DeepSeek, "
    "conversations with friends (Konsai Drew, Toot), personal diary entries, "
    "transcripts of political commentary (Hasan, Channel 5, LegalEagle, etc). "
    "Call this tool MULTIPLE TIMES with DIFFERENT specific queries. "
    "Use specific topic names, framework names, or file series names as queries."
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
        "agent": agent_response[:500],  # truncate for storage
        "searches": searches,
    }

    if not memory.get("sessions"):
        memory["sessions"] = []

    # Keep last 50 exchanges
    memory["sessions"].append(exchange)
    if len(memory["sessions"]) > 50:
        memory["sessions"] = memory["sessions"][-50:]

    save_memory(memory)


def get_memory_context(memory):
    """Build a memory context string from recent sessions."""
    if not memory.get("sessions"):
        return ""

    recent = memory["sessions"][-10:]  # last 10 exchanges
    lines = ["=== PERSISTENT MEMORY (Recent Sessions) ==="]
    for ex in recent:
        lines.append(f"[{ex.get('timestamp', '?')}] User: {ex['user'][:200]}")
        lines.append(f"Agent: {ex['agent'][:200]}")
        lines.append("---")
    lines.append("=== END MEMORY ===")
    return "\n".join(lines)


# === BUILD AGENT ===

def build_agent():
    """Build the full agentic pipeline."""

    llm = OpenAILike(
        model="deepseek-chat",
        api_base="https://api.deepseek.com/v1",
        api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        is_chat_model=True,
        context_window=64000,
        max_tokens=2048,
        temperature=0.7,
    )

    embed_model = HuggingFaceEmbedding(model_name="all-MiniLM-L6-v2")

    Settings.llm = llm
    Settings.embed_model = embed_model

    if not NOTES_DIR.exists():
        print(f"WARNING: NOTES directory not found at {NOTES_DIR}")
        return None

    print("Loading documents from NOTES...")
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
        system_prompt=SYSTEM_PROMPT,
    )

    return agent


async def run_with_trace(agent, ctx, message, memory):
    """
    Run the agent with full reasoning trace capture.
    Returns (reasoning_parts, final_response, searches).
    """
    # Inject memory context into the message if we have history
    mem_context = get_memory_context(memory)
    augmented = message
    if mem_context:
        augmented = f"{mem_context}\n\nCurrent query: {message}"

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

    # Record to persistent memory
    record_exchange(memory, message, final_text, searches)

    return reasoning_parts, final_text, searches


# === STARTUP ===

print("Initializing Proprietary Intelligence System...")
agent = build_agent()
memory = load_memory()

if agent:
    # Persistent context — same Context across all calls = stateful agent
    agent_ctx = Context(agent)
    session_count = len(memory.get("sessions", []))
    print(f"System ready. {session_count} exchanges in persistent memory.")
else:
    agent_ctx = None
    print("System failed to initialize.")
