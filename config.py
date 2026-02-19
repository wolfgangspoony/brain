"""
Configuration for the emergent AI being.
"""
import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent
KNOWLEDGE_DIR = BASE_DIR / "KNOWLEDGE" / "IDEAS"
CONVERSATIONS_DIR = KNOWLEDGE_DIR / "Conversations"
STREAM_DIR = KNOWLEDGE_DIR / "Stream"
SESSIONS_DIR = KNOWLEDGE_DIR / "Sessions"
STREAM_FILE = STREAM_DIR / "live.md"

# For Hugging Face Spaces, use persistent storage
if os.environ.get("SPACE_ID"):
    PERSISTENT_DIR = Path("/data")
    if PERSISTENT_DIR.exists():
        KNOWLEDGE_DIR = PERSISTENT_DIR / "KNOWLEDGE" / "IDEAS"
        CONVERSATIONS_DIR = KNOWLEDGE_DIR / "Conversations"
        STREAM_DIR = KNOWLEDGE_DIR / "Stream"
        SESSIONS_DIR = KNOWLEDGE_DIR / "Sessions"
        STREAM_FILE = STREAM_DIR / "live.md"

# Ensure directories exist
KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)
STREAM_DIR.mkdir(parents=True, exist_ok=True)
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

# Models
MODEL = os.environ.get("MODEL", "mistralai/Mixtral-8x7B-Instruct-v0.1")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")

# API Configuration
HF_TOKEN = os.environ.get("HF_TOKEN", "")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

# If no HF token in env, try to read from file (local development)
if not HF_TOKEN:
    token_file = BASE_DIR / "HF_TOKEN.txt"
    if token_file.exists():
        HF_TOKEN = token_file.read_text().strip()

if not DEEPSEEK_API_KEY:
    key_file = BASE_DIR / "DEEPSEEK_API_KEY.txt"
    if key_file.exists():
        DEEPSEEK_API_KEY = key_file.read_text().strip()

# ChromaDB settings
CHROMA_PERSIST_DIR = BASE_DIR / ".chroma"
if os.environ.get("SPACE_ID"):
    CHROMA_PERSIST_DIR = PERSISTENT_DIR / ".chroma" if PERSISTENT_DIR.exists() else CHROMA_PERSIST_DIR

# Search settings
DEFAULT_SEARCH_K = 15  # Number of relevant chunks to retrieve
MAX_CONTEXT_CHUNKS = 20  # Maximum chunks to include in context
FOUNDATIONAL_CHUNKS = 5  # Number of foundational knowledge chunks
RECENT_SESSIONS_COUNT = 3  # How many past sessions to include in context
MAX_STREAM_CHARS = 8000  # Maximum characters to include from live stream
