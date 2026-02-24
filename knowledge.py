"""
Agentic RAG pipeline using LlamaIndex.
Indexes NOTES directory, creates a ReAct agent that can search
and reason over the knowledge base with multi-step retrieval.
"""
import os
import sys
from pathlib import Path

from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.core.tools import QueryEngineTool, ToolMetadata
from llama_index.core.agent import ReActAgent
from llama_index.core.storage import StorageContext
from llama_index.llms.openai_like import OpenAILike
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
import chromadb

NOTES_DIR = Path(__file__).parent / "NOTES"

SYSTEM_PROMPT = """You are an intelligence system grounded in a specific personal knowledge base.

RULES:
1. ALWAYS search the knowledge base before answering. Never rely on general knowledge alone.
2. If the user asks about multiple topics, search for EACH topic separately with separate tool calls.
3. Show your reasoning: explain what you searched for, what you found, and how it connects.
4. Cite the specific source file for every claim drawn from the notes.
5. If the notes contain frameworks or patterns, apply them to analyze the query.
6. Be direct. No filler. No hedging. Say what the notes say.
7. If the notes don't cover something, say so clearly — don't fabricate.
8. When synthesizing across multiple notes, identify the connections and patterns between them."""

TOOL_DESCRIPTION = (
    "Search the user's personal knowledge base. Contains ~300 files covering: "
    "political analysis, 'Secret History of Power' series, game theory, "
    "AI criticism, Epstein research, cultural commentary, TikTok transcripts, "
    "chat logs with Claude/ChatGPT/DeepSeek, conversations with friends, "
    "and personal diary entries. "
    "Call this tool MULTIPLE TIMES with DIFFERENT specific queries to cover "
    "all aspects of a multi-topic question. Use specific topic names as queries."
)


def build_agent():
    """Build the full agentic RAG pipeline."""

    # LLM — DeepSeek via OpenAI-compatible API
    llm = OpenAILike(
        model="deepseek-chat",
        api_base="https://api.deepseek.com/v1",
        api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        is_chat_model=True,
        context_window=64000,
        max_tokens=2048,
        temperature=0.7,
    )

    # Embedding model
    embed_model = HuggingFaceEmbedding(model_name="all-MiniLM-L6-v2")

    # Global settings
    Settings.llm = llm
    Settings.embed_model = embed_model

    # Load documents
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

    # ChromaDB vector store (in-memory, re-indexes on cold start)
    chroma_client = chromadb.Client()
    chroma_collection = chroma_client.get_or_create_collection("notes")
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    # Build index
    print("Building vector index...")
    index = VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
        show_progress=True,
    )
    print("Index ready.")

    # Query engine tool — the agent can call this as many times as it needs
    query_engine = index.as_query_engine(similarity_top_k=15)
    notes_tool = QueryEngineTool(
        query_engine=query_engine,
        metadata=ToolMetadata(
            name="search_notes",
            description=TOOL_DESCRIPTION,
        ),
    )

    # ReAct agent — reasons before acting, can loop and branch
    agent = ReActAgent(
        name="brain",
        tools=[notes_tool],
        llm=llm,
        system_prompt=SYSTEM_PROMPT,
    )

    return agent


def run_agent(agent, message):
    """
    Run the agent and capture reasoning trace.
    Returns (reasoning_trace, final_response, sources).
    """
    import io

    # Capture verbose output (the reasoning trace)
    buffer = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buffer

    try:
        response = agent.chat(message)
    finally:
        sys.stdout = old_stdout

    reasoning = buffer.getvalue()

    # Extract response text — handle both old and new response formats
    if hasattr(response, 'response'):
        final_text = str(response.response)
    else:
        final_text = str(response)

    # Extract source files from tool outputs if available
    sources = []
    if hasattr(response, 'sources') and response.sources:
        for source in response.sources:
            if hasattr(source, 'raw_input') and source.raw_input:
                query = source.raw_input.get('input', 'N/A')
            else:
                query = 'N/A'
            sources.append({
                'tool': getattr(source, 'tool_name', 'search_notes'),
                'query': query,
            })

    return reasoning, final_text, sources


# Build at startup
print("Initializing agentic RAG pipeline...")
agent = build_agent()
if agent:
    print("Agent ready.")
else:
    print("Agent failed to initialize.")
