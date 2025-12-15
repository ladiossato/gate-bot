"""
Conversation History Module
Handles full conversation storage and recent message retrieval.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from config import DATA_DIR, RECENT_MESSAGES_COUNT

logger = logging.getLogger(__name__)


def get_user_dir(user_id: str) -> Path:
    """Get or create user data directory."""
    user_dir = DATA_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def load_history(user_id: str) -> List[Dict]:
    """Load full conversation history from history.json."""
    history_file = get_user_dir(user_id) / "history.json"
    
    if history_file.exists():
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading history for {user_id}: {e}")
    
    return []


def save_history(user_id: str, history: List[Dict]) -> bool:
    """Save conversation history to history.json."""
    history_file = get_user_dir(user_id) / "history.json"
    
    try:
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
        return True
    except IOError as e:
        logger.error(f"Error saving history for {user_id}: {e}")
        return False


def append_message(
    user_id: str,
    role: str,
    content: str,
    metadata: Optional[Dict] = None
) -> Dict:
    """
    Append a message to conversation history.
    
    Args:
        user_id: User identifier
        role: 'user' or 'assistant'
        content: Message content
        metadata: Optional metadata (e.g., voice=True, scheduled=True)
    
    Returns:
        The appended message dict
    """
    history = load_history(user_id)
    
    message = {
        "id": len(history) + 1,
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat(),
        "metadata": metadata or {}
    }
    
    history.append(message)
    save_history(user_id, history)
    
    # Also append to human-readable text file
    append_to_text_log(user_id, role, content, metadata)
    
    return message


def append_to_text_log(
    user_id: str,
    role: str,
    content: str,
    metadata: Optional[Dict] = None
):
    """Append to human-readable text log with user context."""
    from memory.state import load_state
    import pytz

    log_file = get_user_dir(user_id) / "history.txt"

    # Get user state for timezone and username
    state = load_state(user_id)
    username = state.get("username", "unknown")
    user_tz_str = state.get("timezone")

    # Get timezone-adjusted time
    now = datetime.now()
    if user_tz_str:
        try:
            user_tz = pytz.timezone(user_tz_str)
            now = datetime.now(pytz.UTC).astimezone(user_tz)
            tz_abbrev = now.strftime("%Z")
        except Exception:
            tz_abbrev = "UTC"
    else:
        tz_abbrev = "UTC"

    timestamp = now.strftime("%Y-%m-%d %H:%M")
    prefix = "USER" if role == "user" else "BOT"

    # Add metadata indicators
    indicators = []
    if metadata:
        if metadata.get("voice"):
            indicators.append("[voice]")
        if metadata.get("scheduled"):
            indicators.append("[scheduled]")

    indicator_str = " ".join(indicators) + " " if indicators else ""

    # Format: [user_id: X | @username | timestamp TZ]
    header = f"[user_id: {user_id} | @{username} | {timestamp} {tz_abbrev}]"

    try:
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"{header}\n{prefix}: {indicator_str}{content}\n\n")
    except IOError as e:
        logger.error(f"Error appending to text log for {user_id}: {e}")


def get_recent_messages(user_id: str, count: int = None) -> List[Dict]:
    """
    Get recent messages for LLM context.
    
    Args:
        user_id: User identifier
        count: Number of messages (defaults to RECENT_MESSAGES_COUNT)
    
    Returns:
        List of recent messages in chronological order
    """
    count = count or RECENT_MESSAGES_COUNT
    history = load_history(user_id)
    
    # Return last N messages
    return history[-count:] if len(history) >= count else history


def get_messages_for_api(user_id: str, count: int = None) -> List[Dict]:
    """
    Get messages formatted for API call (role + content only).
    """
    recent = get_recent_messages(user_id, count)
    
    return [
        {"role": msg["role"], "content": msg["content"]}
        for msg in recent
    ]


def get_last_message(user_id: str, role: str = None) -> Optional[Dict]:
    """
    Get the last message, optionally filtered by role.
    """
    history = load_history(user_id)
    
    if not history:
        return None
    
    if role:
        for msg in reversed(history):
            if msg["role"] == role:
                return msg
        return None
    
    return history[-1]


def get_message_count(user_id: str) -> int:
    """Get total message count."""
    history = load_history(user_id)
    return len(history)


def get_messages_since_last_completion(user_id: str) -> List[Dict]:
    """
    Get all messages since the last completion confirmation.
    Used for detecting chat-without-action pattern.
    """
    history = load_history(user_id)
    
    # Find last completion (look for bot acknowledgment patterns)
    completion_indicators = ["got it", "done", "good", "next"]
    
    messages_since = []
    for msg in reversed(history):
        if msg["role"] == "assistant":
            content_lower = msg["content"].lower()
            # Check if this was an acknowledgment of completion
            if any(ind in content_lower for ind in completion_indicators):
                break
        messages_since.insert(0, msg)
    
    return messages_since


def count_user_messages_without_completion(user_id: str) -> int:
    """
    Count user messages since last step completion.
    Used for chat-without-action detection.
    """
    messages = get_messages_since_last_completion(user_id)
    return sum(1 for m in messages if m["role"] == "user")


def search_history(user_id: str, query: str, limit: int = 10) -> List[Dict]:
    """
    Simple keyword search in conversation history.
    """
    history = load_history(user_id)
    query_lower = query.lower()
    
    matches = []
    for msg in reversed(history):
        if query_lower in msg["content"].lower():
            matches.append(msg)
            if len(matches) >= limit:
                break
    
    return matches


def clear_history(user_id: str) -> bool:
    """Clear all conversation history."""
    history_file = get_user_dir(user_id) / "history.json"
    text_file = get_user_dir(user_id) / "history.txt"
    
    try:
        if history_file.exists():
            history_file.unlink()
        if text_file.exists():
            text_file.unlink()
        return True
    except IOError as e:
        logger.error(f"Error clearing history for {user_id}: {e}")
        return False
