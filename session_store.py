"""
Session persistence for the Brain.
Saves and loads conversation sessions to survive page refreshes.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

SESSIONS_DIR = Path(__file__).parent / "SESSIONS"


def _ensure_sessions_dir():
    """Ensure the sessions directory exists."""
    SESSIONS_DIR.mkdir(exist_ok=True)


def save_session(session_id: str, history: list, metadata: dict = None) -> None:
    """
    Persist session to disk.

    Args:
        session_id: Unique session identifier
        history: Conversation history
        metadata: Optional additional metadata
    """
    _ensure_sessions_dir()

    session_file = SESSIONS_DIR / f"{session_id}.json"
    data = {
        "session_id": session_id,
        "history": history,
        "metadata": metadata or {},
        "updated_at": datetime.now().isoformat()
    }

    with open(session_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_session(session_id: str) -> Optional[tuple[list, dict]]:
    """
    Load session from disk.

    Args:
        session_id: Session identifier to load

    Returns:
        Tuple of (history, metadata) or None if not found
    """
    session_file = SESSIONS_DIR / f"{session_id}.json"

    if not session_file.exists():
        return None

    try:
        with open(session_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get("history", []), data.get("metadata", {})
    except (json.JSONDecodeError, IOError):
        return None


def delete_session(session_id: str) -> bool:
    """
    Delete a session file.

    Args:
        session_id: Session to delete

    Returns:
        True if deleted, False if not found
    """
    session_file = SESSIONS_DIR / f"{session_id}.json"

    if session_file.exists():
        session_file.unlink()
        return True
    return False


def list_sessions(max_age_hours: int = None) -> list[dict]:
    """
    List all saved sessions.

    Args:
        max_age_hours: Only return sessions newer than this (optional)

    Returns:
        List of session info dicts
    """
    _ensure_sessions_dir()

    sessions = []
    cutoff = None
    if max_age_hours:
        cutoff = datetime.now() - timedelta(hours=max_age_hours)

    for session_file in SESSIONS_DIR.glob("*.json"):
        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            updated_at = data.get("updated_at")
            if updated_at:
                updated = datetime.fromisoformat(updated_at)
                if cutoff and updated < cutoff:
                    continue

            sessions.append({
                "session_id": data.get("session_id", session_file.stem),
                "updated_at": updated_at,
                "message_count": len(data.get("history", [])),
                "metadata": data.get("metadata", {})
            })
        except (json.JSONDecodeError, IOError):
            continue

    # Sort by updated_at descending
    sessions.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return sessions


def cleanup_old_sessions(max_age_hours: int = 24) -> int:
    """
    Remove sessions older than max_age_hours.

    Args:
        max_age_hours: Maximum age in hours

    Returns:
        Number of sessions deleted
    """
    _ensure_sessions_dir()

    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    deleted = 0

    for session_file in SESSIONS_DIR.glob("*.json"):
        try:
            # Check file modification time first (fast)
            mtime = datetime.fromtimestamp(session_file.stat().st_mtime)
            if mtime < cutoff:
                session_file.unlink()
                deleted += 1
                continue

            # Check internal timestamp (more accurate)
            with open(session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            updated_at = data.get("updated_at")
            if updated_at:
                updated = datetime.fromisoformat(updated_at)
                if updated < cutoff:
                    session_file.unlink()
                    deleted += 1
        except (json.JSONDecodeError, IOError, OSError):
            continue

    return deleted


def get_or_create_session(session_id: str = None) -> tuple[str, list, dict]:
    """
    Get existing session or create a new one.

    Args:
        session_id: Optional existing session ID

    Returns:
        Tuple of (session_id, history, metadata)
    """
    import uuid

    if session_id:
        result = load_session(session_id)
        if result:
            history, metadata = result
            return session_id, history, metadata

    # Create new session
    new_id = f"session_{uuid.uuid4().hex[:12]}"
    return new_id, [], {"created_at": datetime.now().isoformat()}
