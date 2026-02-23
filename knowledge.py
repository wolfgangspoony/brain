"""
RAG pipeline: index the NOTES directory and retrieve relevant chunks at query time.
"""
import re
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

NOTES_DIR = Path(__file__).parent / "NOTES"


class Knowledge:
    def __init__(self):
        self.model = None
        self.collection = None
        self._indexed = False

    def index(self):
        """Load all notes, chunk them, embed them, store in ChromaDB."""
        if self._indexed:
            return

        print("Loading embedding model...")
        self.model = SentenceTransformer("all-MiniLM-L6-v2")

        client = chromadb.Client()
        self.collection = client.get_or_create_collection(
            name="notes",
            metadata={"hnsw:space": "cosine"},
        )

        if not NOTES_DIR.exists():
            print(f"NOTES directory not found at {NOTES_DIR}")
            self._indexed = True
            return

        documents = []
        metadatas = []
        ids = []

        file_count = 0
        for path in NOTES_DIR.rglob("*"):
            if path.suffix.lower() not in (".md", ".txt"):
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                if not content.strip():
                    continue
                rel = str(path.relative_to(NOTES_DIR))
                for i, chunk in enumerate(self._chunk(content, rel)):
                    documents.append(chunk)
                    metadatas.append({"source": rel})
                    ids.append(f"{rel}::{i}")
                file_count += 1
            except Exception as e:
                print(f"Skipping {path}: {e}")

        if documents:
            print(f"Embedding {len(documents)} chunks from {file_count} files...")
            embeddings = self.model.encode(documents, show_progress_bar=True).tolist()

            batch = 100
            for i in range(0, len(documents), batch):
                end = min(i + batch, len(documents))
                self.collection.add(
                    documents=documents[i:end],
                    embeddings=embeddings[i:end],
                    metadatas=metadatas[i:end],
                    ids=ids[i:end],
                )
            print(f"Indexed {len(documents)} chunks. Ready.")

        self._indexed = True

    def search(self, query, k=5):
        """Find the k most relevant chunks for a query."""
        if not self._indexed:
            self.index()
        if self.collection is None or self.collection.count() == 0:
            return []

        emb = self.model.encode([query]).tolist()
        results = self.collection.query(
            query_embeddings=emb,
            n_results=min(k, self.collection.count()),
        )

        hits = []
        if results and results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                hits.append({
                    "content": doc,
                    "source": results["metadatas"][0][i]["source"],
                })
        return hits

    @staticmethod
    def _chunk(text, source, max_size=800):
        """Split text into paragraph-based chunks with source context."""
        stem = Path(source).stem
        header = f"[Source: {stem}]\n\n"
        paragraphs = re.split(r"\n\n+", text)
        chunks = []
        current = header

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            if len(current) + len(para) > max_size and current != header:
                chunks.append(current.strip())
                current = header + para + "\n\n"
            else:
                current += para + "\n\n"

        if current.strip() and current != header:
            chunks.append(current.strip())

        return chunks if chunks else [header + text[:max_size]]


# Global instance
kb = Knowledge()
