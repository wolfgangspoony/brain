"""
Decision logging infrastructure for the Brain.
Logs retrieval decisions, belief formation, tool calls, and other key events.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

LOGS_DIR = Path(__file__).parent / "LOGS"


def _ensure_logs_dir():
    """Ensure the logs directory exists."""
    LOGS_DIR.mkdir(exist_ok=True)


def log_decision(category: str, data: dict) -> str:
    """
    Log a decision with timestamp and category.

    Args:
        category: Type of decision (e.g., "retrieval", "belief_formation", "tool_call")
        data: Dict containing decision details

    Returns:
        The timestamp of the logged entry
    """
    _ensure_logs_dir()

    timestamp = datetime.now().isoformat()
    log_entry = {
        "timestamp": timestamp,
        "category": category,
        **data
    }

    # Append to daily log file (JSONL format)
    log_file = LOGS_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(log_entry, ensure_ascii=False, default=str) + '\n')

    return timestamp


def log_retrieval(
    query: str,
    candidates_count: int,
    final_count: int,
    top_results: list[dict],
    scores: list[dict] = None
):
    """
    Log a memory retrieval decision.

    Args:
        query: The search query
        candidates_count: Number of candidates fetched
        final_count: Number of results returned
        top_results: The final selected memories (truncated for logging)
        scores: Optional scoring breakdown
    """
    log_decision("retrieval", {
        "query": query[:500],
        "candidates_fetched": candidates_count,
        "results_returned": final_count,
        "top_results": [
            {
                "source": r.get("source", "unknown")[:100],
                "type": r.get("type", "unknown"),
                "semantic_score": r.get("semantic_score"),
                "recency_score": r.get("recency_score"),
                "combined_score": r.get("combined_score"),
                "preview": r.get("preview", "")[:200]
            }
            for r in (top_results or [])[:5]
        ],
        "scores": scores
    })


def log_tool_call(
    tool_name: str,
    arguments: dict,
    result: str,
    success: bool = True
):
    """
    Log a tool call decision.

    Args:
        tool_name: Name of the tool called
        arguments: The arguments passed to the tool
        result: The result of the tool call
        success: Whether the call succeeded
    """
    # Truncate large values for logging
    safe_args = {}
    for k, v in arguments.items():
        if isinstance(v, str) and len(v) > 500:
            safe_args[k] = v[:500] + "..."
        else:
            safe_args[k] = v

    log_decision("tool_call", {
        "tool": tool_name,
        "arguments": safe_args,
        "result": result[:500] if isinstance(result, str) else str(result)[:500],
        "success": success
    })


def log_belief_formation(
    topic: str,
    position: str,
    confidence: str,
    reasoning: str,
    contradictions: list[dict],
    superseded_id: str = None
):
    """
    Log a belief formation event.

    Args:
        topic: The belief topic
        position: The position taken
        confidence: Confidence level
        reasoning: Why this belief was formed
        contradictions: List of potential contradictions detected
        superseded_id: ID of previous belief if this is an update
    """
    log_decision("belief_formation", {
        "topic": topic,
        "position": position[:500],
        "confidence": confidence,
        "reasoning": reasoning[:500] if reasoning else None,
        "contradictions_detected": len(contradictions),
        "contradiction_topics": [c.get("belief", {}).get("topic") for c in contradictions[:5]],
        "superseded_previous": superseded_id
    })


def log_belief_contradiction_check(
    topic: str,
    position: str,
    semantic_matches: int,
    keyword_matches: int,
    total_contradictions: int
):
    """
    Log a belief contradiction check.

    Args:
        topic: Topic being checked
        position: Position being checked
        semantic_matches: Number of semantic similarity matches
        keyword_matches: Number of keyword overlap matches
        total_contradictions: Total contradictions found
    """
    log_decision("contradiction_check", {
        "topic": topic,
        "position_preview": position[:200],
        "semantic_matches": semantic_matches,
        "keyword_matches": keyword_matches,
        "total_contradictions": total_contradictions
    })


def log_memory_operation(
    operation: str,
    memory_type: str,
    memory_id: str = None,
    details: dict = None
):
    """
    Log a memory operation (add, supersede, delete).

    Args:
        operation: Type of operation (add, supersede, delete, consolidate)
        memory_type: Type of memory affected
        memory_id: ID of the memory
        details: Additional details
    """
    log_decision("memory_operation", {
        "operation": operation,
        "memory_type": memory_type,
        "memory_id": memory_id,
        **(details or {})
    })


def log_api_call(
    endpoint: str,
    model: str,
    tokens_in: int = None,
    tokens_out: int = None,
    success: bool = True,
    error: str = None,
    latency_ms: int = None
):
    """
    Log an API call.

    Args:
        endpoint: API endpoint or operation type
        model: Model used
        tokens_in: Input tokens (if available)
        tokens_out: Output tokens (if available)
        success: Whether the call succeeded
        error: Error message if failed
        latency_ms: Response time in milliseconds
    """
    log_decision("api_call", {
        "endpoint": endpoint,
        "model": model,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "success": success,
        "error": error[:500] if error else None,
        "latency_ms": latency_ms
    })


def log_reflection(
    trigger: str,
    should_reflect: bool,
    reason: str,
    reflection_preview: str = None
):
    """
    Log a reflection decision.

    Args:
        trigger: What triggered the reflection check
        should_reflect: Whether reflection was deemed worthwhile
        reason: Why or why not
        reflection_preview: Preview of the reflection if generated
    """
    log_decision("reflection", {
        "trigger": trigger,
        "should_reflect": should_reflect,
        "reason": reason,
        "reflection_preview": reflection_preview[:300] if reflection_preview else None
    })


def get_recent_logs(days: int = 1, category: str = None) -> list[dict]:
    """
    Get recent log entries.

    Args:
        days: Number of days to look back
        category: Optional category filter

    Returns:
        List of log entries
    """
    from datetime import timedelta

    entries = []
    start_date = datetime.now() - timedelta(days=days)

    for log_file in LOGS_DIR.glob("*.jsonl"):
        try:
            file_date = datetime.strptime(log_file.stem, "%Y-%m-%d")
            if file_date < start_date:
                continue
        except ValueError:
            continue

        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    if category is None or entry.get("category") == category:
                        entries.append(entry)
                except json.JSONDecodeError:
                    continue

    return sorted(entries, key=lambda x: x.get("timestamp", ""), reverse=True)


def get_log_stats(days: int = 7) -> dict:
    """
    Get statistics from recent logs.

    Args:
        days: Number of days to analyze

    Returns:
        Dict with various statistics
    """
    entries = get_recent_logs(days=days)

    stats = {
        "total_entries": len(entries),
        "by_category": {},
        "beliefs_formed": 0,
        "tools_called": {},
        "api_calls": {"success": 0, "failed": 0},
        "retrievals": 0
    }

    for entry in entries:
        cat = entry.get("category", "unknown")
        stats["by_category"][cat] = stats["by_category"].get(cat, 0) + 1

        if cat == "belief_formation":
            stats["beliefs_formed"] += 1
        elif cat == "tool_call":
            tool = entry.get("tool", "unknown")
            stats["tools_called"][tool] = stats["tools_called"].get(tool, 0) + 1
        elif cat == "api_call":
            if entry.get("success"):
                stats["api_calls"]["success"] += 1
            else:
                stats["api_calls"]["failed"] += 1
        elif cat == "retrieval":
            stats["retrievals"] += 1

    return stats
