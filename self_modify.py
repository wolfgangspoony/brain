"""
Self-modification capabilities for the Brain.
Allows the Brain to write memories, form beliefs, and evolve its self-concept.
"""

import uuid
from datetime import datetime
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

from config import EMBEDDING_MODEL, CHROMA_DIR_NAME, COLLECTION_NAME
import logging_utils

CHROMA_DIR = Path(__file__).parent / CHROMA_DIR_NAME


def get_collection():
    """Get the ChromaDB collection."""
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL
    )
    return client.get_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn
    )


# --- Memory Importance Scoring ---

# Type weights for importance calculation
MEMORY_TYPE_WEIGHTS = {
    "belief": 1.0,
    "self_concept": 0.95,
    "meta_belief": 0.9,
    "goal": 0.85,
    "reflection": 0.7,
    "episode_summary": 0.65,
    "conversation_summary": 0.5,
    "conversation": 0.3,
    "foundation": 0.4
}

# Words that indicate high salience
SALIENCE_MARKERS = [
    "important", "crucial", "realized", "changed", "breakthrough",
    "finally", "understood", "never", "always", "fundamental",
    "core", "essential", "critical", "key", "profound"
]


def calculate_importance(meta: dict, doc_text: str = "") -> float:
    """
    Calculate importance score for a memory.

    Based on:
    - Type weights (beliefs > reflections > conversations)
    - Access frequency (how often retrieved)
    - Salience markers in text

    Args:
        meta: Memory metadata
        doc_text: Optional document text for salience check

    Returns:
        Importance score between 0 and 1
    """
    mem_type = meta.get("memory_type", meta.get("type", "unknown"))
    base_weight = MEMORY_TYPE_WEIGHTS.get(mem_type, 0.3)

    # Access frequency boost (capped at 0.2)
    access_count = meta.get("access_count", 0)
    access_boost = min(0.2, access_count * 0.02)

    # Salience boost from text content
    salience_boost = 0.0
    if doc_text:
        text_lower = doc_text.lower()
        matches = sum(1 for marker in SALIENCE_MARKERS if marker in text_lower)
        salience_boost = min(0.1, matches * 0.02)

    # Confidence boost for beliefs
    confidence_boost = 0.0
    if mem_type == "belief":
        confidence = meta.get("confidence", "moderate")
        confidence_weights = {
            "certain": 0.1,
            "confident": 0.05,
            "moderate": 0.0,
            "leaning": -0.05,
            "uncertain": -0.1
        }
        confidence_boost = confidence_weights.get(confidence, 0.0)

    total = base_weight + access_boost + salience_boost + confidence_boost
    return max(0.0, min(1.0, total))


def record_access(memory_id: str) -> bool:
    """
    Record that a memory was accessed (retrieved).

    Args:
        memory_id: ID of the memory accessed

    Returns:
        True if successful
    """
    collection = get_collection()

    try:
        result = collection.get(ids=[memory_id], include=["metadatas"])
        if not result["metadatas"]:
            return False

        meta = result["metadatas"][0]
        meta["access_count"] = meta.get("access_count", 0) + 1
        meta["last_accessed"] = datetime.now().isoformat()

        collection.update(ids=[memory_id], metadatas=[meta])
        return True
    except Exception:
        return False


def record_batch_access(memory_ids: list[str]) -> int:
    """
    Record access for multiple memories at once.

    Args:
        memory_ids: List of memory IDs accessed

    Returns:
        Number of successfully updated memories
    """
    if not memory_ids:
        return 0

    collection = get_collection()
    updated = 0

    try:
        result = collection.get(ids=memory_ids, include=["metadatas"])

        updated_metas = []
        for meta in result["metadatas"]:
            meta["access_count"] = meta.get("access_count", 0) + 1
            meta["last_accessed"] = datetime.now().isoformat()
            updated_metas.append(meta)

        if updated_metas:
            collection.update(ids=result["ids"], metadatas=updated_metas)
            updated = len(updated_metas)
    except Exception:
        pass

    return updated


# --- Forgetting Mechanism ---

FORGETTING_HALF_LIFE_DAYS = 90  # Memories decay with 90-day half-life
IMPORTANCE_PROTECTION_THRESHOLD = 0.7  # High-importance memories don't decay as fast
PROTECTED_MEMORY_TYPES = {"foundation", "belief", "self_concept", "meta_belief", "goal"}


def calculate_decay_score(meta: dict, doc_text: str = "") -> float:
    """
    Calculate how much a memory has 'decayed' based on time and importance.

    Args:
        meta: Memory metadata
        doc_text: Optional document text for importance calculation

    Returns:
        Decay score between 0 (fully decayed) and 1 (fresh)
    """
    now = datetime.now()

    # Get relevant timestamps
    created_at = meta.get("created_at", "")
    last_accessed = meta.get("last_accessed", "")

    # Use last_accessed if available, otherwise created_at
    reference_time = last_accessed or created_at

    if not reference_time:
        return 0.5  # Default for memories without timestamps

    try:
        ref_dt = datetime.fromisoformat(reference_time.replace('Z', '+00:00'))
        days_since = (now - ref_dt.replace(tzinfo=None)).days
    except Exception:
        return 0.5

    # Base exponential decay
    base_decay = 0.5 ** (days_since / FORGETTING_HALF_LIFE_DAYS)

    # Importance slows decay
    importance = calculate_importance(meta, doc_text)
    if importance >= IMPORTANCE_PROTECTION_THRESHOLD:
        # High-importance memories decay at half the rate
        protected_decay = 0.5 ** (days_since / (FORGETTING_HALF_LIFE_DAYS * 2))
        return max(base_decay, protected_decay, 0.5)  # Never below 50% for important memories

    return base_decay


def should_forget(memory_id: str, meta: dict, doc_text: str = "") -> tuple[bool, str]:
    """
    Determine if a memory should be forgotten (marked for pruning).

    Args:
        memory_id: The memory ID
        meta: Memory metadata
        doc_text: Optional document text

    Returns:
        Tuple of (should_forget, reason)
    """
    mem_type = meta.get("memory_type", meta.get("type", "unknown"))

    # Never forget protected types
    if mem_type in PROTECTED_MEMORY_TYPES:
        return False, "Protected type"

    # Never forget non-superseded consolidations
    if meta.get("is_consolidation") and not meta.get("superseded"):
        return False, "Active consolidation"

    # Check if already superseded
    if not meta.get("superseded"):
        # Non-superseded dynamic memories need very low decay to forget
        decay = calculate_decay_score(meta, doc_text)
        if decay < 0.05:  # Only forget if decayed below 5%
            return True, f"Extremely decayed ({decay:.2%})"
        return False, "Still active"

    # For superseded memories, use decay threshold
    decay = calculate_decay_score(meta, doc_text)
    if decay < 0.1:  # Forget if decayed below 10%
        return True, f"Superseded and decayed ({decay:.2%})"

    return False, f"Decay still above threshold ({decay:.2%})"


# --- Hierarchical Memory ---

def get_memories_for_date(date_str: str) -> list[dict]:
    """
    Get all non-foundation memories from a specific date.

    Args:
        date_str: Date string in YYYY-MM-DD format

    Returns:
        List of memory dicts
    """
    collection = get_collection()
    results = collection.get(include=["documents", "metadatas"])

    memories = []
    for doc_id, doc, meta in zip(results["ids"], results["documents"], results["metadatas"]):
        mem_type = meta.get("memory_type", meta.get("type", "unknown"))

        # Skip foundation content
        if mem_type == "foundation":
            continue

        # Check if created on the target date
        created_at = meta.get("created_at", "")
        if created_at and created_at.startswith(date_str):
            memories.append({
                "id": doc_id,
                "content": doc,
                "type": mem_type,
                "created_at": created_at,
                "meta": meta
            })

    # Sort by creation time
    memories.sort(key=lambda x: x["created_at"])
    return memories


def create_episode_summary(
    date_str: str = None,
    level: int = 1,
    min_memories: int = 3
) -> str | None:
    """
    Create an episode summary for a given date.

    Episode levels:
    - Level 1: Daily summary (groups a day's interactions)
    - Level 2: Weekly themes (could consolidate level 1 summaries)
    - Level 3: Core memories (extracted key insights)

    Args:
        date_str: Date to summarize (YYYY-MM-DD). Defaults to yesterday.
        level: Episode level (1=daily, 2=weekly, 3=core)
        min_memories: Minimum memories required to create summary

    Returns:
        Memory ID of the episode summary, or None if not created
    """
    if date_str is None:
        from datetime import timedelta
        yesterday = datetime.now() - timedelta(days=1)
        date_str = yesterday.strftime("%Y-%m-%d")

    # Check if we already have an episode summary for this date
    collection = get_collection()
    existing = collection.get(
        where={
            "$and": [
                {"memory_type": "episode_summary"},
                {"episode_date": date_str},
                {"episode_level": level}
            ]
        },
        include=["metadatas"]
    )

    if existing["ids"]:
        return None  # Already summarized

    # Get memories for that date
    memories = get_memories_for_date(date_str)

    if len(memories) < min_memories:
        return None  # Not enough to summarize

    # Build summary text (simple extractive for now - could use LLM later)
    summary_parts = [f"Episode summary for {date_str}:"]

    # Group by type
    by_type = {}
    for m in memories:
        t = m["type"]
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(m)

    for mem_type, mems in by_type.items():
        if mem_type == "reflection":
            summary_parts.append(f"\nReflections ({len(mems)}):")
            for m in mems[:3]:  # Top 3
                preview = m["content"][:150].replace("\n", " ")
                summary_parts.append(f"- {preview}...")
        elif mem_type == "belief":
            summary_parts.append(f"\nBeliefs formed/updated ({len(mems)}):")
            for m in mems:
                topic = m["meta"].get("topic", "unknown")
                summary_parts.append(f"- {topic}: {m['content'][:100]}...")
        elif mem_type == "conversation" or mem_type == "conversation_summary":
            summary_parts.append(f"\nConversations ({len(mems)}):")
            for m in mems[:2]:
                title = m["meta"].get("summary", m["meta"].get("title", "conversation"))
                summary_parts.append(f"- {title}")

    summary_text = "\n".join(summary_parts)

    # Create the episode summary
    memory_id = add_memory(
        text=summary_text,
        memory_type="episode_summary",
        metadata={
            "episode_date": date_str,
            "episode_level": level,
            "source_count": len(memories),
            "source_types": list(by_type.keys())
        }
    )

    logging_utils.log_memory_operation(
        operation="episode_summary",
        memory_type="episode_summary",
        memory_id=memory_id,
        details={
            "date": date_str,
            "level": level,
            "source_count": len(memories)
        }
    )

    return memory_id


def create_pending_episode_summaries(max_days_back: int = 7) -> list[str]:
    """
    Create episode summaries for recent days that don't have them yet.

    Args:
        max_days_back: How many days back to check

    Returns:
        List of created memory IDs
    """
    from datetime import timedelta

    created = []
    for days_ago in range(1, max_days_back + 1):
        date = datetime.now() - timedelta(days=days_ago)
        date_str = date.strftime("%Y-%m-%d")

        memory_id = create_episode_summary(date_str)
        if memory_id:
            created.append(memory_id)

    return created


def get_episode_summaries(limit: int = 10) -> list[dict]:
    """
    Get recent episode summaries.

    Args:
        limit: Maximum number to return

    Returns:
        List of episode summary dicts
    """
    collection = get_collection()
    results = collection.get(
        where={"memory_type": "episode_summary"},
        include=["documents", "metadatas"]
    )

    summaries = []
    for doc_id, doc, meta in zip(results["ids"], results["documents"], results["metadatas"]):
        summaries.append({
            "id": doc_id,
            "content": doc,
            "date": meta.get("episode_date"),
            "level": meta.get("episode_level", 1),
            "source_count": meta.get("source_count", 0),
            "created_at": meta.get("created_at")
        })

    # Sort by date descending
    summaries.sort(key=lambda x: x.get("date", ""), reverse=True)
    return summaries[:limit]


def get_forgetting_candidates(max_candidates: int = 100) -> list[dict]:
    """
    Get memories that are candidates for forgetting.

    Args:
        max_candidates: Maximum number of candidates to return

    Returns:
        List of candidate dicts with id, type, decay_score, reason
    """
    collection = get_collection()
    results = collection.get(include=["documents", "metadatas"])

    candidates = []
    for doc_id, doc, meta in zip(results["ids"], results["documents"], results["metadatas"]):
        should, reason = should_forget(doc_id, meta, doc)
        if should:
            candidates.append({
                "id": doc_id,
                "type": meta.get("memory_type", "unknown"),
                "decay_score": calculate_decay_score(meta, doc),
                "reason": reason,
                "created_at": meta.get("created_at", ""),
                "superseded": meta.get("superseded", False)
            })

    # Sort by decay score (lowest first - most decayed)
    candidates.sort(key=lambda x: x["decay_score"])
    return candidates[:max_candidates]


def add_memory(text: str, memory_type: str, metadata: dict = None) -> str:
    """
    Add a new memory to the Brain immediately.

    Args:
        text: The content to remember
        memory_type: One of 'reflection', 'belief', 'self_concept', 'conversation'
        metadata: Additional metadata

    Returns:
        The memory ID
    """
    collection = get_collection()

    memory_id = f"{memory_type}_{uuid.uuid4().hex[:12]}"
    timestamp = datetime.now().isoformat()

    meta = {
        "memory_type": memory_type,
        "created_at": timestamp,
        "superseded": False,
        **(metadata or {})
    }

    collection.add(
        documents=[text],
        metadatas=[meta],
        ids=[memory_id]
    )

    # Log the memory addition
    logging_utils.log_memory_operation(
        operation="add",
        memory_type=memory_type,
        memory_id=memory_id,
        details={"text_length": len(text)}
    )

    return memory_id


def supersede_memory(memory_id: str, reason: str = None) -> bool:
    """
    Mark a memory as superseded (outdated but preserved).

    Args:
        memory_id: The ID of the memory to supersede
        reason: Why it's being superseded

    Returns:
        True if successful
    """
    collection = get_collection()

    try:
        result = collection.get(ids=[memory_id], include=["metadatas"])
        if not result["metadatas"]:
            return False

        meta = result["metadatas"][0]
        meta["superseded"] = True
        meta["superseded_at"] = datetime.now().isoformat()
        if reason:
            meta["supersede_reason"] = reason

        collection.update(ids=[memory_id], metadatas=[meta])

        # Log the supersession
        logging_utils.log_memory_operation(
            operation="supersede",
            memory_type=meta.get("memory_type", "unknown"),
            memory_id=memory_id,
            details={"reason": reason}
        )
        return True
    except Exception:
        return False


# --- Beliefs ---

def get_beliefs(include_superseded: bool = False) -> list[dict]:
    """
    Get all current beliefs.

    Args:
        include_superseded: Whether to include superseded beliefs

    Returns:
        List of belief dicts with id, topic, position, reasoning, confidence, created_at
    """
    collection = get_collection()

    results = collection.get(
        where={"memory_type": "belief"},
        include=["documents", "metadatas"]
    )

    beliefs = []
    for doc, meta, doc_id in zip(
        results["documents"],
        results["metadatas"],
        results["ids"]
    ):
        if not include_superseded and meta.get("superseded"):
            continue

        beliefs.append({
            "id": doc_id,
            "topic": meta.get("topic", "unknown"),
            "position": doc,
            "reasoning": meta.get("reasoning", ""),
            "confidence": meta.get("confidence", "moderate"),
            "created_at": meta.get("created_at", ""),
            "superseded": meta.get("superseded", False)
        })

    return beliefs


def get_belief(topic: str) -> dict | None:
    """Get the current (non-superseded) belief on a topic."""
    beliefs = get_beliefs(include_superseded=False)
    for belief in beliefs:
        if belief["topic"].lower() == topic.lower():
            return belief
    return None


def check_belief_contradictions(topic: str, position: str, similarity_threshold: float = 0.7) -> list[dict]:
    """
    Check if a new belief position might contradict existing beliefs.
    Uses both keyword overlap AND embedding similarity for better detection.

    Args:
        topic: The topic of the new belief
        position: The position/stance of the new belief
        similarity_threshold: Minimum semantic similarity to flag (0-1, higher = more similar)

    Returns:
        List of potentially contradicting beliefs with similarity info
    """
    beliefs = get_beliefs(include_superseded=False)
    if not beliefs:
        return []

    collection = get_collection()
    contradictions = []
    topic_lower = topic.lower()
    position_lower = position.lower()
    seen_ids = set()

    # Method 1: Semantic similarity via embedding query
    new_belief_text = f"{topic}: {position}"
    try:
        results = collection.query(
            query_texts=[new_belief_text],
            n_results=10,
            where={"memory_type": "belief"},
            include=["documents", "metadatas", "distances"]
        )

        if results["ids"] and results["ids"][0]:
            for doc_id, doc, meta, distance in zip(
                results["ids"][0],
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0]
            ):
                # Skip superseded or same topic
                if meta.get("superseded"):
                    continue
                if meta.get("topic", "").lower() == topic_lower:
                    continue

                # Convert distance to similarity (cosine distance: 0 = identical, 2 = opposite)
                similarity = 1 - (distance / 2)

                if similarity >= similarity_threshold:
                    seen_ids.add(doc_id)
                    contradictions.append({
                        "belief": {
                            "id": doc_id,
                            "topic": meta.get("topic", "unknown"),
                            "position": doc,
                            "confidence": meta.get("confidence", "moderate")
                        },
                        "similarity": round(similarity, 2),
                        "reason": f"Semantically related ({int(similarity * 100)}% similar)"
                    })
    except Exception as e:
        print(f"Semantic similarity check failed: {e}")

    # Method 2: Keyword overlap (catches things embeddings might miss)
    common_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
                    "have", "has", "had", "do", "does", "did", "will", "would", "could",
                    "should", "may", "might", "must", "that", "this", "these", "those",
                    "i", "you", "we", "they", "it", "and", "or", "but", "not", "no", "yes"}

    for belief in beliefs:
        if belief["id"] in seen_ids:
            continue  # Already found via embedding
        if belief["topic"].lower() == topic_lower:
            continue

        belief_words = set(belief["topic"].lower().split() + belief["position"].lower().split())
        new_words = set(topic_lower.split() + position_lower.split())
        overlap = belief_words & new_words
        meaningful_overlap = overlap - common_words

        if len(meaningful_overlap) >= 2:
            contradictions.append({
                "belief": belief,
                "overlap": list(meaningful_overlap),
                "reason": f"Related topics (shared: {', '.join(list(meaningful_overlap)[:5])})"
            })

    # Sort by similarity (semantic matches first)
    contradictions.sort(key=lambda x: x.get("similarity", 0), reverse=True)

    # Count semantic vs keyword matches
    semantic_matches = sum(1 for c in contradictions if "similarity" in c)
    keyword_matches = sum(1 for c in contradictions if "overlap" in c)

    # Log the contradiction check
    logging_utils.log_belief_contradiction_check(
        topic=topic,
        position=position,
        semantic_matches=semantic_matches,
        keyword_matches=keyword_matches,
        total_contradictions=len(contradictions)
    )

    return contradictions


CONFIDENCE_LEVELS = ["uncertain", "leaning", "moderate", "confident", "certain"]


# --- Meta-Beliefs ---

def form_meta_belief(
    domain: str,
    observation: str,
    adjustment: str = ""
) -> str:
    """
    Form a meta-belief (belief about the belief-forming process).

    Args:
        domain: What area this applies to (e.g., "political topics", "technical predictions")
        observation: What was noticed about reasoning in this domain
        adjustment: How reasoning should adjust going forward

    Returns:
        Memory ID of the meta-belief
    """
    text = f"In {domain}: {observation}"
    if adjustment:
        text += f" Adjustment: {adjustment}"

    memory_id = add_memory(
        text=text,
        memory_type="meta_belief",
        metadata={
            "domain": domain,
            "observation": observation,
            "adjustment": adjustment
        }
    )

    logging_utils.log_decision("meta_belief_formation", {
        "domain": domain,
        "observation": observation[:200],
        "adjustment": adjustment[:200] if adjustment else None
    })

    return memory_id


def get_meta_beliefs(domain: str = None) -> list[dict]:
    """
    Get meta-beliefs, optionally filtered by domain.

    Args:
        domain: Optional domain to filter by

    Returns:
        List of meta-belief dicts
    """
    collection = get_collection()

    results = collection.get(
        where={"memory_type": "meta_belief"},
        include=["documents", "metadatas"]
    )

    meta_beliefs = []
    for doc_id, doc, meta in zip(results["ids"], results["documents"], results["metadatas"]):
        if meta.get("superseded"):
            continue

        if domain and meta.get("domain", "").lower() != domain.lower():
            continue

        meta_beliefs.append({
            "id": doc_id,
            "domain": meta.get("domain", "general"),
            "observation": meta.get("observation", doc),
            "adjustment": meta.get("adjustment", ""),
            "content": doc,
            "created_at": meta.get("created_at", "")
        })

    return meta_beliefs


# --- Goals ---

def set_goal(
    goal: str,
    motivation: str = "",
    timeframe: str = "",
    priority: str = "medium"
) -> str:
    """
    Create a new goal.

    Args:
        goal: What to achieve
        motivation: Why this matters
        timeframe: When to achieve it
        priority: low, medium, or high

    Returns:
        Memory ID of the goal
    """
    if priority not in ["low", "medium", "high"]:
        priority = "medium"

    memory_id = add_memory(
        text=goal,
        memory_type="goal",
        metadata={
            "motivation": motivation,
            "timeframe": timeframe,
            "priority": priority,
            "status": "active",
            "progress_notes": []
        }
    )

    logging_utils.log_decision("goal_set", {
        "goal": goal[:200],
        "priority": priority,
        "timeframe": timeframe
    })

    return memory_id


def update_goal_progress(
    goal_id: str = None,
    goal_text: str = None,
    progress: str = "",
    status: str = None
) -> bool:
    """
    Update progress on a goal.

    Args:
        goal_id: ID of the goal (or use goal_text to find it)
        goal_text: Text to match if goal_id not provided
        progress: Progress note to add
        status: New status (active, achieved, abandoned)

    Returns:
        True if successful
    """
    collection = get_collection()

    # Find the goal
    if goal_id:
        result = collection.get(ids=[goal_id], include=["documents", "metadatas"])
        if not result["ids"]:
            return False
        doc_id = goal_id
        meta = result["metadatas"][0]
    elif goal_text:
        # Search for goal by text
        results = collection.get(
            where={"memory_type": "goal"},
            include=["documents", "metadatas"]
        )
        doc_id = None
        for did, doc, m in zip(results["ids"], results["documents"], results["metadatas"]):
            if goal_text.lower() in doc.lower() and not m.get("superseded"):
                doc_id = did
                meta = m
                break
        if not doc_id:
            return False
    else:
        return False

    # Update metadata
    if progress:
        progress_notes = meta.get("progress_notes", [])
        progress_notes.append({
            "note": progress,
            "timestamp": datetime.now().isoformat()
        })
        meta["progress_notes"] = progress_notes

    if status and status in ["active", "achieved", "abandoned"]:
        meta["status"] = status
        if status in ["achieved", "abandoned"]:
            meta["completed_at"] = datetime.now().isoformat()

    collection.update(ids=[doc_id], metadatas=[meta])

    logging_utils.log_decision("goal_progress", {
        "goal_id": doc_id,
        "progress": progress[:200] if progress else None,
        "new_status": status
    })

    return True


def get_goals(status: str = None, include_completed: bool = False) -> list[dict]:
    """
    Get goals.

    Args:
        status: Filter by status (active, achieved, abandoned)
        include_completed: Whether to include completed goals

    Returns:
        List of goal dicts
    """
    collection = get_collection()

    results = collection.get(
        where={"memory_type": "goal"},
        include=["documents", "metadatas"]
    )

    goals = []
    for doc_id, doc, meta in zip(results["ids"], results["documents"], results["metadatas"]):
        if meta.get("superseded"):
            continue

        goal_status = meta.get("status", "active")

        if status and goal_status != status:
            continue

        if not include_completed and goal_status in ["achieved", "abandoned"]:
            continue

        goals.append({
            "id": doc_id,
            "goal": doc,
            "motivation": meta.get("motivation", ""),
            "timeframe": meta.get("timeframe", ""),
            "priority": meta.get("priority", "medium"),
            "status": goal_status,
            "progress_notes": meta.get("progress_notes", []),
            "created_at": meta.get("created_at", "")
        })

    # Sort by priority
    priority_order = {"high": 0, "medium": 1, "low": 2}
    goals.sort(key=lambda x: priority_order.get(x["priority"], 1))

    return goals


def get_active_goals() -> list[dict]:
    """Get all active goals."""
    return get_goals(status="active")


def get_relevant_meta_beliefs(topic: str) -> list[dict]:
    """
    Get meta-beliefs relevant to a given topic.

    Uses simple keyword matching to find relevant meta-beliefs.

    Args:
        topic: The topic to find relevant meta-beliefs for

    Returns:
        List of relevant meta-beliefs
    """
    all_meta = get_meta_beliefs()

    if not all_meta:
        return []

    topic_lower = topic.lower()
    topic_words = set(topic_lower.split())

    relevant = []
    for mb in all_meta:
        domain_lower = mb["domain"].lower()
        domain_words = set(domain_lower.split())

        # Check for word overlap
        if topic_words & domain_words:
            relevant.append(mb)
            continue

        # Check if topic is mentioned in domain or observation
        if topic_lower in domain_lower or topic_lower in mb["observation"].lower():
            relevant.append(mb)

    return relevant


def form_belief(
    topic: str,
    position: str,
    reasoning: str = "",
    confidence: str = "moderate"
) -> tuple[str, list[dict]]:
    """
    Form a new belief on a topic.
    If a belief on this topic already exists, it will be superseded.

    Args:
        topic: What the belief is about
        position: The Brain's position/view
        reasoning: Why the Brain holds this position
        confidence: How confident ("uncertain", "leaning", "moderate", "confident", "certain")

    Returns:
        Tuple of (new_belief_memory_id, list_of_potential_contradictions)
    """
    # Validate confidence
    if confidence not in CONFIDENCE_LEVELS:
        confidence = "moderate"

    # Check for potential contradictions first
    contradictions = check_belief_contradictions(topic, position)

    # Supersede any existing belief on this topic
    existing = get_belief(topic)
    if existing:
        supersede_memory(
            existing["id"],
            reason=f"Evolved to new position: {position[:100]}..."
        )

    memory_id = add_memory(
        text=position,
        memory_type="belief",
        metadata={
            "topic": topic,
            "reasoning": reasoning,
            "confidence": confidence,
            "supersedes": existing["id"] if existing else None,
            "potential_contradictions": [c["belief"]["topic"] for c in contradictions] if contradictions else None
        }
    )

    # Log the belief formation
    logging_utils.log_belief_formation(
        topic=topic,
        position=position,
        confidence=confidence,
        reasoning=reasoning,
        contradictions=contradictions,
        superseded_id=existing["id"] if existing else None
    )

    return memory_id, contradictions


def update_belief(
    topic: str,
    new_position: str,
    reasoning: str = "",
    confidence: str = None
) -> tuple[str, list[dict]]:
    """
    Update an existing belief (alias for form_belief with evolution semantics).
    If confidence not specified, inherits from existing belief.
    """
    # Inherit confidence from existing belief if not specified
    if confidence is None:
        existing = get_belief(topic)
        confidence = existing.get("confidence", "moderate") if existing else "moderate"

    return form_belief(topic, new_position, reasoning, confidence)


def get_belief_history(topic: str) -> list[dict]:
    """
    Get the full history of beliefs on a topic, including superseded ones.

    Args:
        topic: The topic to get history for

    Returns:
        List of beliefs in chronological order (oldest first)
    """
    collection = get_collection()

    results = collection.get(
        where={"memory_type": "belief"},
        include=["documents", "metadatas"]
    )

    history = []
    for doc, meta, doc_id in zip(
        results["documents"],
        results["metadatas"],
        results["ids"]
    ):
        if meta.get("topic", "").lower() == topic.lower():
            history.append({
                "id": doc_id,
                "topic": meta.get("topic", "unknown"),
                "position": doc,
                "reasoning": meta.get("reasoning", ""),
                "confidence": meta.get("confidence", "moderate"),
                "created_at": meta.get("created_at", ""),
                "superseded": meta.get("superseded", False),
                "superseded_at": meta.get("superseded_at"),
                "supersede_reason": meta.get("supersede_reason")
            })

    # Sort by created_at ascending (oldest first)
    history.sort(key=lambda x: x["created_at"])
    return history


def get_all_belief_topics() -> list[str]:
    """Get all topics that have beliefs (current or superseded)."""
    collection = get_collection()

    results = collection.get(
        where={"memory_type": "belief"},
        include=["metadatas"]
    )

    topics = set()
    for meta in results["metadatas"]:
        topic = meta.get("topic")
        if topic:
            topics.add(topic)

    return sorted(list(topics))


# --- Self-Concept ---

def get_self_concept() -> dict:
    """
    Get the Brain's current self-concept.

    Returns:
        Dict with aspects of self-understanding, e.g.:
        {
            "identity": "...",
            "values": "...",
            "style": "...",
            ...
        }
    """
    collection = get_collection()

    results = collection.get(
        where={"memory_type": "self_concept"},
        include=["documents", "metadatas"]
    )

    concept = {}
    for doc, meta in zip(results["documents"], results["metadatas"]):
        if meta.get("superseded"):
            continue
        aspect = meta.get("aspect", "general")
        concept[aspect] = doc

    return concept


def update_self_concept(aspect: str, description: str, reasoning: str = "") -> str:
    """
    Update an aspect of the Brain's self-concept.

    Args:
        aspect: Which part of self-understanding (e.g., 'identity', 'values', 'style')
        description: The new self-description for this aspect
        reasoning: Why this changed

    Returns:
        The new memory ID
    """
    collection = get_collection()

    # Find and supersede existing aspect
    results = collection.get(
        where={"memory_type": "self_concept"},
        include=["metadatas"]
    )

    for meta, doc_id in zip(results["metadatas"], results["ids"]):
        if meta.get("aspect") == aspect and not meta.get("superseded"):
            supersede_memory(doc_id, reason=reasoning or "Self-concept evolved")

    return add_memory(
        text=description,
        memory_type="self_concept",
        metadata={
            "aspect": aspect,
            "reasoning": reasoning
        }
    )


# --- Reflections ---

def save_reflection(thought: str, topic: str = None) -> str:
    """
    Save a reflection/thought.

    Args:
        thought: The reflection content
        topic: Optional topic/trigger for the reflection

    Returns:
        The memory ID
    """
    return add_memory(
        text=thought,
        memory_type="reflection",
        metadata={"topic": topic} if topic else {}
    )


def get_recent_reflections(limit: int = 10, include_consolidated: bool = True) -> list[dict]:
    """Get recent reflections."""
    collection = get_collection()

    results = collection.get(
        where={"memory_type": "reflection"},
        include=["documents", "metadatas"]
    )

    reflections = []
    for doc, meta, doc_id in zip(
        results["documents"],
        results["metadatas"],
        results["ids"]
    ):
        if meta.get("superseded") and not include_consolidated:
            continue
        reflections.append({
            "id": doc_id,
            "thought": doc,
            "topic": meta.get("topic"),
            "created_at": meta.get("created_at", ""),
            "is_consolidation": meta.get("is_consolidation", False),
            "superseded": meta.get("superseded", False)
        })

    # Sort by created_at descending
    reflections.sort(key=lambda x: x["created_at"], reverse=True)
    return reflections[:limit]


def get_reflections_for_consolidation() -> dict[str, list[dict]]:
    """
    Group unconsolidated reflections by topic for potential consolidation.

    Returns:
        Dict mapping topic -> list of reflections on that topic
    """
    collection = get_collection()

    results = collection.get(
        where={"memory_type": "reflection"},
        include=["documents", "metadatas"]
    )

    by_topic = {}
    for doc, meta, doc_id in zip(
        results["documents"],
        results["metadatas"],
        results["ids"]
    ):
        # Skip already superseded or consolidation reflections
        if meta.get("superseded") or meta.get("is_consolidation"):
            continue

        topic = meta.get("topic") or "general"
        if topic not in by_topic:
            by_topic[topic] = []

        by_topic[topic].append({
            "id": doc_id,
            "thought": doc,
            "topic": topic,
            "created_at": meta.get("created_at", "")
        })

    # Only return topics with 3+ reflections (worth consolidating)
    return {k: v for k, v in by_topic.items() if len(v) >= 3}


def consolidate_reflections(topic: str, consolidated_thought: str, source_ids: list[str]) -> str:
    """
    Create a consolidated reflection and supersede the source reflections.

    Args:
        topic: The topic being consolidated
        consolidated_thought: The synthesized reflection
        source_ids: IDs of reflections being consolidated

    Returns:
        The new consolidated reflection's memory ID
    """
    # Supersede source reflections
    for source_id in source_ids:
        supersede_memory(source_id, reason=f"Consolidated into synthesis on '{topic}'")

    # Create consolidated reflection
    memory_id = add_memory(
        text=consolidated_thought,
        memory_type="reflection",
        metadata={
            "topic": topic,
            "is_consolidation": True,
            "source_count": len(source_ids),
            "source_ids": source_ids
        }
    )

    # Log the consolidation
    logging_utils.log_memory_operation(
        operation="consolidate",
        memory_type="reflection",
        memory_id=memory_id,
        details={
            "topic": topic,
            "source_count": len(source_ids)
        }
    )

    return memory_id


# --- Conversation Memory ---

def get_recent_conversations(limit: int = 5) -> list[dict]:
    """Get recent conversation summaries for session continuity."""
    collection = get_collection()

    # Get conversation summaries (preferred) and conversations
    results = collection.get(
        where={"memory_type": {"$in": ["conversation_summary", "conversation"]}},
        include=["documents", "metadatas"]
    )

    conversations = []
    for doc, meta, doc_id in zip(
        results["documents"],
        results["metadatas"],
        results["ids"]
    ):
        conversations.append({
            "id": doc_id,
            "type": meta.get("memory_type"),
            "summary": meta.get("summary") or meta.get("title"),
            "content": doc,
            "created_at": meta.get("created_at", "")
        })

    # Sort by created_at descending
    conversations.sort(key=lambda x: x["created_at"], reverse=True)

    # Prefer summaries over full conversations
    seen_summaries = set()
    filtered = []
    for c in conversations:
        if c["type"] == "conversation_summary":
            seen_summaries.add(c.get("summary"))
            filtered.append(c)
        elif c.get("summary") not in seen_summaries:
            filtered.append(c)

        if len(filtered) >= limit:
            break

    return filtered[:limit]


def prune_old_memories(
    max_age_days: int = 90,
    keep_types: set = None,
    dry_run: bool = True,
    use_decay: bool = True
) -> dict:
    """
    Prune old, low-value memories to prevent unbounded growth.

    Uses both age-based and decay-based criteria for more intelligent pruning.

    Args:
        max_age_days: Remove memories older than this (default 90 days)
        keep_types: Memory types to never prune (default: foundation, belief, self_concept)
        dry_run: If True, only report what would be pruned without deleting
        use_decay: If True, also use decay-based forgetting mechanism

    Returns:
        Dict with pruning stats and list of pruned/would-prune IDs
    """
    from datetime import datetime, timedelta

    collection = get_collection()
    cutoff = datetime.now() - timedelta(days=max_age_days)

    # Types that should never be pruned
    if keep_types is None:
        keep_types = PROTECTED_MEMORY_TYPES

    # Get all memories
    results = collection.get(include=["documents", "metadatas"])

    candidates = []
    seen_ids = set()

    # Method 1: Decay-based forgetting (smarter)
    if use_decay:
        decay_candidates = get_forgetting_candidates(max_candidates=200)
        for c in decay_candidates:
            if c["id"] not in seen_ids:
                seen_ids.add(c["id"])
                candidates.append(c)

    # Method 2: Age-based pruning (legacy)
    for doc_id, doc, meta in zip(results["ids"], results["documents"], results["metadatas"]):
        if doc_id in seen_ids:
            continue

        memory_type = meta.get("memory_type", meta.get("type", "unknown"))

        # Skip protected types
        if memory_type in keep_types:
            continue

        # Skip non-superseded consolidations (they're valuable)
        if meta.get("is_consolidation") and not meta.get("superseded"):
            continue

        # Skip active (non-superseded) memories unless very old
        if not meta.get("superseded"):
            continue

        # Check age
        created_at = meta.get("created_at", "")
        if created_at:
            try:
                created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                if created.replace(tzinfo=None) > cutoff:
                    continue  # Not old enough
            except Exception:
                pass

        seen_ids.add(doc_id)
        candidates.append({
            "id": doc_id,
            "type": memory_type,
            "created_at": created_at,
            "superseded": meta.get("superseded", False),
            "decay_score": calculate_decay_score(meta, doc),
            "reason": "Age-based"
        })

    # Also find old drafts (always prune these regardless of age)
    for doc_id, meta in zip(results["ids"], results["metadatas"]):
        if doc_id in seen_ids:
            continue

        summary = meta.get("summary", "")
        if summary.startswith("[Draft]"):
            # Check if draft is more than 1 day old
            created_at = meta.get("created_at", "")
            if created_at:
                try:
                    created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    if created.replace(tzinfo=None) < datetime.now() - timedelta(days=1):
                        seen_ids.add(doc_id)
                        candidates.append({
                            "id": doc_id,
                            "type": "draft",
                            "created_at": created_at,
                            "superseded": False,
                            "decay_score": 0.0,
                            "reason": "Old draft"
                        })
                except Exception:
                    pass

    # Sort by decay score (most decayed first)
    candidates.sort(key=lambda x: x.get("decay_score", 0))

    pruned = []
    if not dry_run and candidates:
        for c in candidates:
            try:
                collection.delete(ids=[c["id"]])
                pruned.append(c["id"])
            except Exception as e:
                print(f"Failed to prune {c['id']}: {e}")

    return {
        "dry_run": dry_run,
        "candidates": len(candidates),
        "pruned": len(pruned),
        "details": candidates[:20],  # Return first 20 for inspection
        "message": f"{'Would prune' if dry_run else 'Pruned'} {len(candidates)} memories"
    }


def get_memory_stats() -> dict:
    """Get statistics about memory usage."""
    collection = get_collection()
    results = collection.get(include=["metadatas"])

    stats = {
        "total": len(results["ids"]),
        "by_type": {},
        "superseded": 0,
        "drafts": 0
    }

    for meta in results["metadatas"]:
        mem_type = meta.get("memory_type", meta.get("type", "unknown"))
        stats["by_type"][mem_type] = stats["by_type"].get(mem_type, 0) + 1

        if meta.get("superseded"):
            stats["superseded"] += 1

        if meta.get("summary", "").startswith("[Draft]"):
            stats["drafts"] += 1

    return stats


def export_identity() -> dict:
    """
    Export all dynamic identity components (beliefs, self-concept, reflections).

    Returns:
        Dict with all exportable identity data
    """
    from datetime import datetime

    return {
        "exported_at": datetime.now().isoformat(),
        "beliefs": get_beliefs(include_superseded=True),
        "self_concept": get_self_concept(),
        "reflections": get_recent_reflections(limit=100, include_consolidated=True),
        "stats": {
            "total_beliefs": len(get_beliefs(include_superseded=True)),
            "active_beliefs": len(get_beliefs(include_superseded=False)),
            "self_concept_aspects": len(get_self_concept()),
            "total_reflections": len(get_recent_reflections(limit=1000, include_consolidated=True))
        }
    }


def export_to_file(filepath: str = None) -> str:
    """
    Export identity to a JSON file.

    Args:
        filepath: Path to export to. If None, auto-generates in EXPORTS dir.

    Returns:
        Path to the exported file
    """
    import json
    from datetime import datetime
    from pathlib import Path

    data = export_identity()

    if filepath is None:
        exports_dir = Path(__file__).parent / "EXPORTS"
        exports_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filepath = exports_dir / f"brain_export_{timestamp}.json"
    else:
        filepath = Path(filepath)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return str(filepath)


def delete_draft_conversations(session_id: str) -> int:
    """
    Delete draft conversations for a session.

    Args:
        session_id: The session ID to match (in summary field)

    Returns:
        Number of drafts deleted
    """
    collection = get_collection()

    # Find drafts with this session ID
    results = collection.get(
        where={"memory_type": "conversation"},
        include=["metadatas"]
    )

    deleted = 0
    for meta, doc_id in zip(results["metadatas"], results["ids"]):
        summary = meta.get("summary", "")
        if summary.startswith("[Draft]") and session_id in summary:
            try:
                collection.delete(ids=[doc_id])
                deleted += 1
            except Exception:
                pass

    return deleted


def save_conversation_memory(
    conversation: list[dict],
    summary: str = None,
    dense_summary: str = None,
    session_id: str = None
) -> tuple[str, str | None]:
    """
    Save a conversation to memory immediately (no recompile needed).
    Also saves a dense summary as a separate memory for better retrieval.

    Args:
        conversation: List of {"role": "user"|"assistant", "content": str}
        summary: Brief title for the conversation
        dense_summary: Detailed summary of key points (if provided, saved separately)
        session_id: If provided, deletes any drafts for this session first

    Returns:
        Tuple of (conversation_memory_id, summary_memory_id or None)
    """
    # Delete drafts if this is a final save
    if session_id and not (summary and summary.startswith("[Draft]")):
        delete_draft_conversations(session_id)

    # Format conversation as text
    lines = []
    if summary:
        lines.append(f"Conversation: {summary}\n")

    for msg in conversation:
        if not msg.get("content"):
            continue
        role = "Human" if msg["role"] == "user" else "Brain"
        lines.append(f"{role}: {msg['content']}")

    text = "\n\n".join(lines)

    convo_id = add_memory(
        text=text,
        memory_type="conversation",
        metadata={
            "summary": summary,
            "message_count": len(conversation)
        }
    )

    # Save dense summary as separate memory if provided
    summary_id = None
    if dense_summary:
        summary_id = add_memory(
            text=dense_summary,
            memory_type="conversation_summary",
            metadata={
                "title": summary,
                "conversation_id": convo_id
            }
        )

    return convo_id, summary_id
