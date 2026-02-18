"""
Configuration for the Brain.
"""

# Embedding model - bge-large-en-v1.5 is better for nuanced content than MiniLM
# Trade-off: slower and more memory, but much better retrieval quality
EMBEDDING_MODEL = "BAAI/bge-large-en-v1.5"

# ChromaDB settings
CHROMA_DIR_NAME = "chroma_db"
COLLECTION_NAME = "brain_memories"

# Retrieval settings
RETRIEVAL_CANDIDATES = 15  # Fetch more, then re-rank
RETRIEVAL_FINAL = 5        # Return top N after re-ranking

# Memory types that should NOT be wiped on recompile
DYNAMIC_MEMORY_TYPES = {"reflection", "belief", "self_concept"}

# Context window settings
MAX_CONTEXT_TOKENS = 32000  # DeepSeek's approximate context window
RESERVED_RESPONSE_TOKENS = 2048  # Reserve for response
MAX_HISTORY_TOKENS = MAX_CONTEXT_TOKENS - RESERVED_RESPONSE_TOKENS
HISTORY_TRUNCATION_THRESHOLD = 0.7  # Start truncating at 70% of max
