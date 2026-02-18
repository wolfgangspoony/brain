"""
Ingest markdown content into ChromaDB for RAG retrieval.
Processes notes and saved conversations as foundation content.
Preserves dynamic memories (reflections, beliefs, self_concept) on recompile.
"""

import re
from pathlib import Path
import chromadb
from chromadb.utils import embedding_functions

from config import (
    EMBEDDING_MODEL,
    CHROMA_DIR_NAME,
    COLLECTION_NAME,
    DYNAMIC_MEMORY_TYPES
)

# Directories
NOTES_DIR = Path(__file__).parent / "NOTES"
CONVERSATIONS_DIR = Path(__file__).parent / "CONVERSATIONS"
CHROMA_DIR = Path(__file__).parent / CHROMA_DIR_NAME

# Chunking config
CHUNK_SIZE = 1500
CHUNK_OVERLAP = 200


def clean_text(text: str) -> str:
    """Clean markdown text for embedding."""
    # Remove YAML frontmatter
    text = re.sub(r'^---\n.*?\n---\n', '', text, flags=re.DOTALL)
    # Remove markdown links but keep text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # Remove wiki-style links
    text = re.sub(r'\[\[([^\]]+)\]\]', r'\1', text)
    # Clean up extra whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def extract_metadata(content: str, filepath: Path, base_dir: Path) -> dict:
    """Extract metadata from file, including modification time."""
    from datetime import datetime

    try:
        relative = str(filepath.relative_to(base_dir))
    except ValueError:
        relative = filepath.name

    # Get file modification time
    try:
        mtime = filepath.stat().st_mtime
        created_at = datetime.fromtimestamp(mtime).isoformat()
    except Exception:
        created_at = None

    metadata = {
        "source": relative,
        "filename": filepath.stem,
    }

    if created_at:
        metadata["created_at"] = created_at

    # Parse YAML frontmatter
    match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if match:
        frontmatter = match.group(1)
        for line in frontmatter.split('\n'):
            if ':' in line and not line.strip().startswith('-'):
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip().strip('"\'')
                if key in ['title', 'date', 'type']:
                    metadata[key] = value
                    # If frontmatter has date, use it as created_at
                    if key == 'date' and value:
                        metadata["created_at"] = value

    return metadata


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks."""
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        # Try to break at paragraph or sentence
        if end < len(text):
            para_break = text.rfind('\n\n', start, end)
            if para_break > start + chunk_size // 2:
                end = para_break
            else:
                for punct in ['. ', '? ', '! ']:
                    sent_break = text.rfind(punct, start, end)
                    if sent_break > start + chunk_size // 2:
                        end = sent_break + 1
                        break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        start = end - overlap if end < len(text) else len(text)

    return chunks


def collect_from_dir(directory: Path, source_type: str) -> list[tuple[str, dict]]:
    """Collect all markdown files from a directory."""
    if not directory.exists():
        return []

    documents = []

    for filepath in directory.rglob("*.md"):
        try:
            content = filepath.read_text(encoding='utf-8')
            metadata = extract_metadata(content, filepath, directory)
            metadata["type"] = source_type
            clean_content = clean_text(content)

            # Skip very short or index files
            if len(clean_content) < 100 or filepath.stem.startswith("00 -"):
                continue

            chunks = chunk_text(clean_content)

            for i, chunk in enumerate(chunks):
                chunk_metadata = metadata.copy()
                chunk_metadata["chunk_index"] = i
                chunk_metadata["total_chunks"] = len(chunks)
                documents.append((chunk, chunk_metadata))

        except Exception as e:
            print(f"Error processing {filepath}: {e}")

    return documents


def ingest(preserve_dynamic=True):
    """
    Main ingestion - process notes and conversations.

    Args:
        preserve_dynamic: If True, preserve reflections/beliefs/self_concept
    """
    print(f"Collecting from {NOTES_DIR}...")
    documents = collect_from_dir(NOTES_DIR, "foundation")
    print(f"  {len(documents)} chunks from notes")

    print(f"Collecting from {CONVERSATIONS_DIR}...")
    convos = collect_from_dir(CONVERSATIONS_DIR, "conversation")
    print(f"  {len(convos)} chunks from conversations")

    documents.extend(convos)
    print(f"Total: {len(documents)} chunks to ingest")

    # Initialize ChromaDB
    CHROMA_DIR.mkdir(exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL
    )

    # Preserve dynamic memories if requested
    dynamic_memories = []
    try:
        old_collection = client.get_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_fn
        )

        if preserve_dynamic:
            # Get all dynamic memories
            all_data = old_collection.get(include=["documents", "metadatas"])
            for doc, meta, doc_id in zip(
                all_data["documents"],
                all_data["metadatas"],
                all_data["ids"]
            ):
                if meta.get("memory_type") in DYNAMIC_MEMORY_TYPES:
                    dynamic_memories.append((doc, meta, doc_id))

            if dynamic_memories:
                print(f"Preserving {len(dynamic_memories)} dynamic memories")

        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"}
    )

    # Add foundation documents in batches
    batch_size = 100
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i + batch_size]
        texts = [doc[0] for doc in batch]
        metadatas = [doc[1] for doc in batch]
        # Add memory_type to metadata
        for meta in metadatas:
            meta["memory_type"] = meta.get("type", "foundation")
        ids = [f"foundation_{i + j}" for j in range(len(batch))]

        collection.add(documents=texts, metadatas=metadatas, ids=ids)
        print(f"  Added {min(i + batch_size, len(documents))}/{len(documents)}")

    # Restore dynamic memories
    if dynamic_memories:
        for doc, meta, doc_id in dynamic_memories:
            collection.add(
                documents=[doc],
                metadatas=[meta],
                ids=[doc_id]
            )
        print(f"Restored {len(dynamic_memories)} dynamic memories")

    total = collection.count()
    print(f"Done. {total} total memories.")


if __name__ == "__main__":
    ingest()
