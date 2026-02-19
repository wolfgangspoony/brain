"""
Knowledge management for the emergent being.
Handles loading, searching, adding, and removing knowledge.
"""
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

import config


class Knowledge:
    """The being's knowledge base - its mind."""

    def __init__(self):
        self.embedding_model = None
        self.chroma_client = None
        self.collection = None
        self._initialized = False

    def _ensure_initialized(self):
        """Lazy initialization of heavy resources."""
        if self._initialized:
            return

        # Load embedding model
        self.embedding_model = SentenceTransformer(config.EMBEDDING_MODEL)

        # Initialize ChromaDB
        config.CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(
            path=str(config.CHROMA_PERSIST_DIR),
            settings=Settings(anonymized_telemetry=False)
        )

        # Get or create collection
        self.collection = self.chroma_client.get_or_create_collection(
            name="knowledge",
            metadata={"hnsw:space": "cosine"}
        )

        self._initialized = True

    def load_all(self) -> dict[str, str]:
        """
        Load all markdown files from the knowledge directory.
        Returns dict mapping filepath to content.
        """
        knowledge = {}

        if not config.KNOWLEDGE_DIR.exists():
            return knowledge

        for md_file in config.KNOWLEDGE_DIR.rglob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
                # Use relative path as key
                rel_path = md_file.relative_to(config.KNOWLEDGE_DIR)
                knowledge[str(rel_path)] = content
            except Exception as e:
                print(f"Error reading {md_file}: {e}")

        return knowledge

    def index_all(self, force: bool = False):
        """
        Index all knowledge for semantic search.
        Set force=True to rebuild the index.
        """
        self._ensure_initialized()

        # Check if we need to reindex
        existing_count = self.collection.count()
        knowledge = self.load_all()

        if not force and existing_count > 0:
            print(f"Index already has {existing_count} chunks. Use force=True to rebuild.")
            return

        if force and existing_count > 0:
            # Clear existing index
            self.chroma_client.delete_collection("knowledge")
            self.collection = self.chroma_client.create_collection(
                name="knowledge",
                metadata={"hnsw:space": "cosine"}
            )

        # Index each document
        documents = []
        metadatas = []
        ids = []

        for filepath, content in knowledge.items():
            # Split into chunks (simple paragraph-based splitting)
            chunks = self._chunk_text(content, filepath)
            for i, chunk in enumerate(chunks):
                documents.append(chunk)
                metadatas.append({
                    "filepath": filepath,
                    "chunk_index": i,
                    "indexed_at": datetime.now().isoformat()
                })
                ids.append(f"{filepath}_{i}")

        if documents:
            # Batch add to ChromaDB (it handles embedding internally if we don't provide)
            # But we'll use our own embeddings for consistency
            embeddings = self.embedding_model.encode(documents).tolist()

            # Add in batches to avoid memory issues
            batch_size = 100
            for i in range(0, len(documents), batch_size):
                end = min(i + batch_size, len(documents))
                self.collection.add(
                    documents=documents[i:end],
                    embeddings=embeddings[i:end],
                    metadatas=metadatas[i:end],
                    ids=ids[i:end]
                )

            print(f"Indexed {len(documents)} chunks from {len(knowledge)} files.")

    def _chunk_text(self, text: str, filepath: str, max_chunk_size: int = 1000) -> list[str]:
        """Split text into meaningful chunks."""
        chunks = []

        # Add filename context to first chunk
        filename = Path(filepath).stem
        header = f"[From: {filename}]\n\n"

        # Split by double newlines (paragraphs)
        paragraphs = re.split(r'\n\n+', text)

        current_chunk = header
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current_chunk) + len(para) > max_chunk_size:
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                current_chunk = header + para + "\n\n"
            else:
                current_chunk += para + "\n\n"

        if current_chunk.strip() and current_chunk != header:
            chunks.append(current_chunk.strip())

        return chunks if chunks else [header + text[:max_chunk_size]]

    def search(self, query: str, k: int = None) -> list[dict]:
        """
        Semantic search through knowledge.
        Returns list of {content, filepath, score} dicts.
        """
        self._ensure_initialized()

        if k is None:
            k = config.DEFAULT_SEARCH_K

        if self.collection.count() == 0:
            # Auto-index if empty
            self.index_all()

        if self.collection.count() == 0:
            return []

        # Embed query and search
        query_embedding = self.embedding_model.encode([query]).tolist()

        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=min(k, self.collection.count())
        )

        # Format results
        formatted = []
        if results and results['documents']:
            for i, doc in enumerate(results['documents'][0]):
                formatted.append({
                    'content': doc,
                    'filepath': results['metadatas'][0][i]['filepath'],
                    'score': 1 - results['distances'][0][i] if results['distances'] else 0
                })

        return formatted

    def add(self, content: str, filename: str = None, category: str = None) -> str:
        """
        Add new knowledge.
        Returns the filepath of the saved file.
        """
        self._ensure_initialized()

        # Generate filename if not provided
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"thought_{timestamp}.md"

        # Ensure .md extension
        if not filename.endswith('.md'):
            filename += '.md'

        # Determine save path
        if category:
            save_dir = config.KNOWLEDGE_DIR / category
        else:
            save_dir = config.KNOWLEDGE_DIR

        save_dir.mkdir(parents=True, exist_ok=True)
        filepath = save_dir / filename

        # Add metadata header
        full_content = f"---\ncreated: {datetime.now().isoformat()}\n---\n\n{content}"

        filepath.write_text(full_content, encoding="utf-8")

        # Add to index
        rel_path = filepath.relative_to(config.KNOWLEDGE_DIR)
        chunks = self._chunk_text(content, str(rel_path))

        for i, chunk in enumerate(chunks):
            chunk_id = f"{rel_path}_{i}"
            embedding = self.embedding_model.encode([chunk]).tolist()

            self.collection.add(
                documents=[chunk],
                embeddings=embedding,
                metadatas=[{
                    "filepath": str(rel_path),
                    "chunk_index": i,
                    "indexed_at": datetime.now().isoformat()
                }],
                ids=[chunk_id]
            )

        return str(rel_path)

    def remove(self, filepath: str) -> bool:
        """
        Remove knowledge by filepath.
        Returns True if successful.
        """
        self._ensure_initialized()

        # Find the file
        full_path = config.KNOWLEDGE_DIR / filepath

        if not full_path.exists():
            return False

        # Remove from disk
        full_path.unlink()

        # Remove from index (all chunks with this filepath)
        try:
            self.collection.delete(
                where={"filepath": filepath}
            )
        except Exception:
            # ChromaDB might not have this file indexed
            pass

        return True

    def edit(self, filepath: str, new_content: str) -> bool:
        """
        Edit existing knowledge.
        Returns True if successful.
        """
        # Remove old version
        if not self.remove(filepath):
            return False

        # Add new version
        category = str(Path(filepath).parent) if Path(filepath).parent != Path('.') else None
        filename = Path(filepath).name
        self.add(new_content, filename=filename, category=category)

        return True

    def list_recent(self, n: int = 10) -> list[dict]:
        """
        List most recently modified knowledge files.
        Returns list of {filepath, modified, preview} dicts.
        """
        files = []

        if not config.KNOWLEDGE_DIR.exists():
            return files

        for md_file in config.KNOWLEDGE_DIR.rglob("*.md"):
            try:
                stat = md_file.stat()
                content = md_file.read_text(encoding="utf-8")
                # Get first 200 chars as preview
                preview = content[:200].replace('\n', ' ').strip()
                if len(content) > 200:
                    preview += "..."

                files.append({
                    'filepath': str(md_file.relative_to(config.KNOWLEDGE_DIR)),
                    'modified': datetime.fromtimestamp(stat.st_mtime),
                    'preview': preview
                })
            except Exception:
                continue

        # Sort by modified time, most recent first
        files.sort(key=lambda x: x['modified'], reverse=True)

        return files[:n]

    def get_foundational_context(self, n: int = 5) -> str:
        """
        Get foundational knowledge to include in every context.
        This shapes the being's core identity.
        Excludes Stream and Sessions directories - those are handled separately.
        """
        recent = self.list_recent(n * 2)  # Get more, filter down

        if not recent:
            return ""

        context_parts = []
        for item in recent:
            # Skip stream and session files - they're handled separately
            if item['filepath'].startswith('Stream/') or item['filepath'].startswith('Sessions/'):
                continue
            if len(context_parts) >= n:
                break
            try:
                full_path = config.KNOWLEDGE_DIR / item['filepath']
                content = full_path.read_text(encoding="utf-8")
                # Limit each file to ~500 chars for foundational context
                if len(content) > 500:
                    content = content[:500] + "..."
                context_parts.append(f"[{item['filepath']}]\n{content}")
            except Exception:
                continue

        return "\n\n---\n\n".join(context_parts)

    # ========== Stream Management (Working Memory) ==========

    def append_to_stream(self, role: str, content: str):
        """
        Append a message to the live stream file.
        This is immediate persistence - every word enters the brain.
        """
        timestamp = datetime.now().strftime("%H:%M")

        # Format the entry
        if role == "user":
            entry = f"\n\n**[{timestamp}] Human:** {content}"
        else:
            entry = f"\n\n**[{timestamp}] Being:** {content}"

        # Create stream file with header if it doesn't exist
        if not config.STREAM_FILE.exists():
            header = f"# Live Stream - {datetime.now().strftime('%Y-%m-%d')}\n\n---"
            config.STREAM_FILE.write_text(header, encoding="utf-8")

        # Append to stream
        with open(config.STREAM_FILE, "a", encoding="utf-8") as f:
            f.write(entry)

    def get_stream(self, max_chars: int = None) -> str:
        """
        Get the current live stream content.
        This is working memory - always visible to the being.
        """
        if max_chars is None:
            max_chars = config.MAX_STREAM_CHARS

        if not config.STREAM_FILE.exists():
            return ""

        try:
            content = config.STREAM_FILE.read_text(encoding="utf-8")
            # If too long, take the most recent portion
            if len(content) > max_chars:
                content = "...(earlier conversation truncated)...\n\n" + content[-max_chars:]
            return content
        except Exception:
            return ""

    def archive_stream(self) -> Optional[str]:
        """
        Archive the current stream to Sessions folder.
        Called when a new session starts.
        Returns the archived filepath or None.
        """
        if not config.STREAM_FILE.exists():
            return None

        try:
            content = config.STREAM_FILE.read_text(encoding="utf-8")
            if not content.strip() or content.strip() == f"# Live Stream - {datetime.now().strftime('%Y-%m-%d')}":
                # Empty or just header, delete without archiving
                config.STREAM_FILE.unlink()
                return None

            # Generate archive filename
            # Check for existing sessions today to increment counter
            today = datetime.now().strftime("%Y-%m-%d")
            existing = list(config.SESSIONS_DIR.glob(f"{today}_*.md"))
            counter = len(existing) + 1

            archive_name = f"{today}_{counter:03d}.md"
            archive_path = config.SESSIONS_DIR / archive_name

            # Add archive header
            archived_content = content.replace(
                "# Live Stream",
                f"# Session Archive"
            )
            archived_content = f"---\narchived: {datetime.now().isoformat()}\n---\n\n{archived_content}"

            archive_path.write_text(archived_content, encoding="utf-8")

            # Delete the live stream file
            config.STREAM_FILE.unlink()

            # Index the archived session
            self._ensure_initialized()
            rel_path = archive_path.relative_to(config.KNOWLEDGE_DIR)
            chunks = self._chunk_text(archived_content, str(rel_path))

            for i, chunk in enumerate(chunks):
                chunk_id = f"{rel_path}_{i}"
                embedding = self.embedding_model.encode([chunk]).tolist()

                self.collection.add(
                    documents=[chunk],
                    embeddings=embedding,
                    metadatas=[{
                        "filepath": str(rel_path),
                        "chunk_index": i,
                        "indexed_at": datetime.now().isoformat()
                    }],
                    ids=[chunk_id]
                )

            return str(rel_path)

        except Exception as e:
            print(f"Error archiving stream: {e}")
            return None

    def get_recent_sessions(self, n: int = None) -> str:
        """
        Get the last N archived session files.
        This is short-term memory - recent conversations.
        """
        if n is None:
            n = config.RECENT_SESSIONS_COUNT

        if not config.SESSIONS_DIR.exists():
            return ""

        # Get session files sorted by name (which includes date)
        session_files = sorted(
            config.SESSIONS_DIR.glob("*.md"),
            key=lambda x: x.name,
            reverse=True
        )[:n]

        if not session_files:
            return ""

        sessions_content = []
        for sf in reversed(session_files):  # Oldest first
            try:
                content = sf.read_text(encoding="utf-8")
                # Limit each session to ~2000 chars
                if len(content) > 2000:
                    content = content[:2000] + "\n...(truncated)..."
                sessions_content.append(f"[Previous Session: {sf.stem}]\n{content}")
            except Exception:
                continue

        return "\n\n---\n\n".join(sessions_content)


# Global instance
_knowledge = None

def get_knowledge() -> Knowledge:
    """Get the global Knowledge instance."""
    global _knowledge
    if _knowledge is None:
        _knowledge = Knowledge()
    return _knowledge
