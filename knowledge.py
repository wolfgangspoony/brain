"""
Brain - Clean DeepSeek Integration
"""
import os
import json
import asyncio
import uuid
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple
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
_memory_lock = asyncio.Lock()
_chroma_client = None
_http_client = None

# Constants
MAX_MESSAGE_LENGTH = 10000
MAX_HISTORY_TURNS = 3
MAX_SEARCH_RESULTS = 3
MAX_RESULT_LENGTH = 600
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


def get_http_client():
    """Get or create shared httpx client."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=60.0)
    return _http_client


# === VECTOR SEARCH ===

def get_chroma_client():
    """Get or create ChromaDB client."""
    global _chroma_client
    if _chroma_client is None and CHROMA_DIR.exists():
        _chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return _chroma_client


def close_chroma_client():
    """Close ChromaDB client on shutdown."""
    global _chroma_client
    _chroma_client = None


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
            client = get_chroma_client()
            if client:
                chroma_collection = client.get_or_create_collection("knowledge")
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
            close_chroma_client()
            # Clear potentially corrupted chroma dir
            try:
                import shutil
                shutil.rmtree(CHROMA_DIR)
            except Exception:
                pass
    
    # Build new index
    print("Loading documents from KNOWLEDGE...")
    try:
        documents = SimpleDirectoryReader(
            str(KNOWLEDGE_DIR),
            recursive=True,
            required_exts=[".md", ".txt"],
            filename_as_id=True,
        ).load_data()
        print(f"Loaded {len(documents)} documents.")
    except Exception as e:
        print(f"Error loading documents: {e}")
        return None
    
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    chroma_collection = client.get_or_create_collection("knowledge")
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
        self._lock = asyncio.Lock()
    
    async def search(self, query: str) -> List[str]:
        """Search notes and return relevant text chunks (thread-safe)."""
        if self.index is None:
            return []
        
        async with self._lock:
            if self.query_engine is None:
                self.query_engine = self.index.as_query_engine(similarity_top_k=self.top_k)
            
            try:
                # Run sync query in thread pool to not block async loop
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, self.query_engine.query, query)
                
                results = []
                if hasattr(response, 'source_nodes'):
                    for node in response.source_nodes:
                        results.append(node.node.text)
                return results
            except Exception as e:
                print(f"Search error: {e}")
                return []


# === MEMORY ===

async def load_memory():
    """Load persistent memory from disk with caching."""
    global _memory_cache
    
    if _memory_cache is not None:
        return _memory_cache
    
    if MEMORY_FILE.exists():
        try:
            async with _memory_lock:
                loop = asyncio.get_event_loop()
                content = await loop.run_in_executor(
                    None, MEMORY_FILE.read_text, "utf-8"
                )
                _memory_cache = json.loads(content)
            return _memory_cache
        except Exception:
            pass
    
    _memory_cache = {"sessions": []}
    return _memory_cache


async def save_memory(memory):
    """Save memory to disk with async safety and atomic writes."""
    try:
        async with _memory_lock:
            loop = asyncio.get_event_loop()
            content = json.dumps(memory, indent=2, ensure_ascii=False)
            
            # Atomic write: write to temp then rename
            def write_atomic():
                MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
                temp_file = MEMORY_FILE.with_suffix('.tmp')
                temp_file.write_text(content, encoding="utf-8")
                temp_file.replace(MEMORY_FILE)
            
            await loop.run_in_executor(None, write_atomic)
    except Exception as e:
        print(f"Warning: Could not save memory: {e}")


async def record_exchange(memory, user_msg: str, agent_response: str, searches: List[str]):
    """Record a conversation exchange to persistent memory."""
    exchange = {
        "timestamp": datetime.now().isoformat(),
        "user": user_msg[:MAX_MESSAGE_LENGTH],
        "agent": agent_response[:MAX_MESSAGE_LENGTH * 2],
        "searches": searches,
    }
    
    if "sessions" not in memory:
        memory["sessions"] = []
    
    memory["sessions"].append(exchange)
    
    # Keep last 100 sessions
    if len(memory["sessions"]) > 100:
        memory["sessions"] = memory["sessions"][-100:]
    
    await save_memory(memory)


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
    
    client = get_http_client()
    last_error = None
    
    for attempt in range(retries):
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            last_error = e
            if e.response.status_code == 429:  # Rate limit
                wait_time = 2 ** attempt
                print(f"Rate limited, waiting {wait_time}s...")
                await asyncio.sleep(wait_time)
                continue
            elif e.response.status_code >= 500:
                await asyncio.sleep(1)
                continue
            raise
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
    
    # Build message history
    history = get_recent_history(memory, n=MAX_HISTORY_TURNS)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    for ex in history:
        messages.append({
            "role": "user", 
            "content": truncate_for_tokens(ex["user"], 2000)
        })
        messages.append({
            "role": "assistant", 
            "content": truncate_for_tokens(ex["agent"], 4000)
        })
    
    messages.append({"role": "user", "content": message})
    
    # First call
    searches = []
    try:
        response_text = await call_deepseek_chat(messages, api_key)
    except Exception as e:
        return f"Error calling API: {str(e)}", []
    
    # Check for search
    if response_text.strip().upper().startswith("SEARCH:"):
        search_query = response_text.strip()[7:].strip()
        if len(search_query) > 200:
            search_query = search_query[:200]
        searches.append(search_query)
        
        try:
            search_results = await search_tool.search(search_query)
        except Exception as e:
            print(f"Search failed: {e}")
            search_results = []
        
        # Build search context
        if search_results:
            search_context = "=== SEARCH RESULTS ===\n\n"
            for i, result in enumerate(search_results[:MAX_SEARCH_RESULTS], 1):
                truncated = result[:MAX_RESULT_LENGTH]
                if len(result) > MAX_RESULT_LENGTH:
                    truncated += "..."
                search_context += f"[{i}] {truncated}\n\n"
        else:
            search_context = "=== SEARCH RESULTS ===\nNo relevant results found.\n"
        
        messages.append({"role": "assistant", "content": response_text})
        messages.append({"role": "user", "content": search_context})
        
        # Second call
        try:
            response_text = await call_deepseek_chat(messages, api_key)
        except Exception as e:
            response_text = f"Search completed but error: {str(e)}"
    
    # Record to memory
    await record_exchange(memory, message, response_text, searches)
    
    return response_text, searches


# === INITIALIZATION ===

async def init_async():
    """Async initialization."""
    global _search_index, _memory_cache
    
    get_api_key()
    
    if _memory_cache is None:
        _memory_cache = await load_memory()
    
    if _search_index is None:
        # Run index loading in thread pool (it's blocking)
        loop = asyncio.get_event_loop()
        _search_index = await loop.run_in_executor(None, get_or_build_index)
    
    return _search_index, _memory_cache


def init():
    """Sync wrapper for init - use init_async() in async context instead."""
    global _search_index, _memory_cache
    
    get_api_key()
    
    if _memory_cache is None:
        # This is a hack for sync init - should use init_async ideally
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Can't run async in running loop, return empty and let async init fix it
                _memory_cache = {"sessions": []}
            else:
                _memory_cache = loop.run_until_complete(load_memory())
        except RuntimeError:
            _memory_cache = {"sessions": []}
    
    if _search_index is None:
        _search_index = get_or_build_index()
    
    return _search_index, _memory_cache


print("Brain module loaded.")
