"""
Brain - Clean DeepSeek Integration
"""
import os
import json
import asyncio
import threading
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional
import httpx

from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.storage import StorageContext
import chromadb

# Paths
KNOWLEDGE_DIR = Path(__file__).parent / "KNOWLEDGE"
MEMORY_FILE = Path(__file__).parent / "memory.json"
CHROMA_DIR = Path(__file__).parent / ".chroma"

# HF Spaces persistent storage
if os.environ.get("SPACE_ID"):
    persistent = Path("/data")
    if persistent.exists():
        MEMORY_FILE = persistent / "memory.json"
        CHROMA_DIR = persistent / ".chroma"

DEEPSEEK_API_KEY = ""
_search_index = None
_memory_cache = None
_memory_lock = threading.Lock()

# Constants
MAX_MESSAGE_LENGTH = 10000  # Characters
MAX_HISTORY_TURNS = 3  # Number of exchanges to keep
MAX_SEARCH_RESULTS = 3  # Number of search results to include
MAX_RESULT_LENGTH = 600  # Characters per result
MAX_TOKENS_RESPONSE = 2048


def get_api_key() -> str:
    """Get DeepSeek API key from environment or file."""
    global DEEPSEEK_API_KEY
    
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if api_key:
        DEEPSEEK_API_KEY = api_key
        return api_key
    
    key_file = Path(__file__).parent / "DEEPSEEK_API_KEY.txt"
    if key_file.exists():
        try:
            api_key = key_file.read_text(encoding="utf-8").strip()
            if api_key:
                DEEPSEEK_API_KEY = api_key
                return api_key
        except Exception:
            pass
    return ""


# === VECTOR SEARCH ===

def get_or_build_index():
    """Get existing index or build new one. Persists to disk."""
    global _search_index
    
    if _search_index is not None:
        return _search_index
    
    embed_model = HuggingFaceEmbedding(model_name="all-MiniLM-L6-v2")
    Settings.embed_model = embed_model
    
    if not KNOWLEDGE_DIR.exists():
        print(f"WARNING: KNOWLEDGE directory not found at {KNOWLEDGE_DIR}")
        return None
    
    # Try to load existing persistent index
    if CHROMA_DIR.exists():
        try:
            print("Loading existing vector index...")
            chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
            chroma_collection = chroma_client.get_or_create_collection("knowledge")
            vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
            storage_context = StorageContext.from_defaults(vector_store=vector_store)
            _search_index = VectorStoreIndex.from_vector_store(
                vector_store, storage_context=storage_context
            )
            print("Index loaded from disk.")
            return _search_index
        except Exception as e:
            print(f"Could not load existing index: {e}")
            print("Rebuilding index...")
            # Clear potentially corrupted chroma dir
            try:
                import shutil
                shutil.rmtree(CHROMA_DIR)
            except Exception:
                pass
    
    # Build new index
    print("Loading documents from KNOWLEDGE...")
    documents = SimpleDirectoryReader(
        str(KNOWLEDGE_DIR),
        recursive=True,
        required_exts=[".md", ".txt"],
    ).load_data()
    print(f"Loaded {len(documents)} documents.")
    
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    chroma_collection = chroma_client.get_or_create_collection("knowledge")
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    
    print("Building vector index...")
    _search_index = VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
        show_progress=True,
    )
    print("Index ready and saved to disk.")
    
    return _search_index


class SearchTool:
    """Simple search tool that persists its query engine."""
    
    def __init__(self, index, top_k: int = 10):
        self.index = index
        self.query_engine = None
        self.top_k = top_k
    
    def search(self, query: str) -> List[str]:
        """Search notes and return relevant text chunks."""
        if self.index is None:
            return []
        
        if self.query_engine is None:
            self.query_engine = self.index.as_query_engine(similarity_top_k=self.top_k)
        
        try:
            response = self.query_engine.query(query)
        except Exception as e:
            print(f"Search error: {e}")
            return []
        
        results = []
        if hasattr(response, 'source_nodes'):
            for node in response.source_nodes:
                results.append(node.node.text)
        
        return results


# === MEMORY ===

def load_memory():
    """Load persistent memory from disk with caching."""
    global _memory_cache
    
    if _memory_cache is not None:
        return _memory_cache
    
    if MEMORY_FILE.exists():
        try:
            with _memory_lock:
                _memory_cache = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
            return _memory_cache
        except Exception:
            pass
    
    _memory_cache = {"sessions": []}
    return _memory_cache


def save_memory(memory):
    """Save memory to disk with thread safety."""
    try:
        MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _memory_lock:
            MEMORY_FILE.write_text(json.dumps(memory, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"Warning: Could not save memory: {e}")


def record_exchange(memory, user_msg: str, agent_response: str, searches: List[str]):
    """Record a conversation exchange to persistent memory."""
    exchange = {
        "timestamp": datetime.now().isoformat(),
        "user": user_msg[:MAX_MESSAGE_LENGTH],  # Truncate if needed
        "agent": agent_response[:MAX_MESSAGE_LENGTH * 2],  # Allow longer responses
        "searches": searches,
    }
    
    if "sessions" not in memory:
        memory["sessions"] = []
    
    memory["sessions"].append(exchange)
    
    # Keep last 100 sessions
    if len(memory["sessions"]) > 100:
        memory["sessions"] = memory["sessions"][-100:]
    
    save_memory(memory)


def get_recent_history(memory, n: int = MAX_HISTORY_TURNS) -> List[Dict]:
    """Get recent conversation history as structured list."""
    if not memory.get("sessions"):
        return []
    return memory["sessions"][-n:]


# === DEEPSEEK API ===

async def call_deepseek_chat(
    messages: List[Dict[str, str]],
    api_key: str,
    temperature: float = 0.7,
    max_tokens: int = MAX_TOKENS_RESPONSE,
    retries: int = 3,
) -> str:
    """Call DeepSeek API directly with retry logic."""
    
    url = "https://api.deepseek.com/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    
    last_error = None
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload, timeout=60.0)
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            last_error = e
            if e.response.status_code == 429:  # Rate limit
                wait_time = 2 ** attempt  # Exponential backoff
                print(f"Rate limited, waiting {wait_time}s...")
                await asyncio.sleep(wait_time)
                continue
            elif e.response.status_code >= 500:  # Server error, retry
                await asyncio.sleep(1)
                continue
            raise  # Client error, don't retry
        except (httpx.NetworkError, httpx.TimeoutException) as e:
            last_error = e
            await asyncio.sleep(1)
            continue
    
    raise last_error or Exception("All retries failed")


# === AGENT LOGIC ===

SYSTEM_PROMPT = """You are a direct, analytical conversational partner. You have access to a search tool for querying your knowledge base of notes, transcripts, and conversations.

To search, output exactly: SEARCH: <query>
Example: SEARCH: CIA occult programs

Guidelines:
- Search when you need specific facts from your notes
- Don't mirror the user's language patterns
- Have your own ideas and disagree when appropriate
- Be concise and direct"""


def truncate_for_tokens(text: str, max_chars: int = 8000) -> str:
    """Rough truncation to stay within token limits."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "... [truncated]"


async def run_agent(
    search_tool: SearchTool,
    message: str,
    memory: Dict,
    api_key: str,
) -> Tuple[str, List[str]]:
    """Run the agent with search capability."""
    
    # Validate/truncate input
    message = message.strip()
    if len(message) > MAX_MESSAGE_LENGTH:
        message = message[:MAX_MESSAGE_LENGTH] + "... [truncated]"
    
    # Build message history (last N exchanges for context)
    history = get_recent_history(memory, n=MAX_HISTORY_TURNS)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # Add history as separate messages (truncated)
    for ex in history:
        messages.append({
            "role": "user", 
            "content": truncate_for_tokens(ex["user"], 2000)
        })
        messages.append({
            "role": "assistant", 
            "content": truncate_for_tokens(ex["agent"], 4000)
        })
    
    # Add current message
    messages.append({"role": "user", "content": message})
    
    # First call - see if agent wants to search
    searches = []
    try:
        response_text = await call_deepseek_chat(messages, api_key)
    except Exception as e:
        return f"Error calling API: {str(e)}", []
    
    # Check if search is needed
    if response_text.strip().upper().startswith("SEARCH:"):
        # Extract search query
        search_query = response_text.strip()[7:].strip()
        if len(search_query) > 200:
            search_query = search_query[:200]
        searches.append(search_query)
        
        # Perform search
        try:
            search_results = search_tool.search(search_query)
        except Exception as e:
            print(f"Search failed: {e}")
            search_results = []
        
        # Build search context (limited to prevent token overflow)
        if search_results:
            search_context = "=== SEARCH RESULTS ===\n\n"
            for i, result in enumerate(search_results[:MAX_SEARCH_RESULTS], 1):
                truncated = result[:MAX_RESULT_LENGTH]
                if len(result) > MAX_RESULT_LENGTH:
                    truncated += "..."
                search_context += f"[{i}] {truncated}\n\n"
        else:
            search_context = "=== SEARCH RESULTS ===\nNo relevant results found.\n"
        
        # Add the search flow to conversation
        messages.append({"role": "assistant", "content": response_text})
        messages.append({"role": "user", "content": search_context})
        
        # Second call with search results
        try:
            response_text = await call_deepseek_chat(messages, api_key)
        except Exception as e:
            response_text = f"Search completed but error generating response: {str(e)}"
    
    # Record to memory
    record_exchange(memory, message, response_text, searches)
    
    return response_text, searches


# === LAZY INITIALIZATION ===

def init():
    """Initialize everything. Call this explicitly instead of at import."""
    global _search_index, _memory_cache
    
    get_api_key()
    
    if _memory_cache is None:
        _memory_cache = load_memory()
    
    if _search_index is None:
        _search_index = get_or_build_index()
    
    return _search_index, _memory_cache


# Don't auto-init on import - let app.py call init()
print("Brain module loaded. Call init() to start.")
