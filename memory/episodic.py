"""
Episodic Memory Module
Stores and retrieves significant moments (breakthroughs, commitments, completions).
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from config import DATA_DIR

logger = logging.getLogger(__name__)


def get_user_dir(user_id: str) -> Path:
    """Get or create user data directory."""
    user_dir = DATA_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def load_episodic(user_id: str) -> List[Dict]:
    """Load episodic memories from episodic.json."""
    episodic_file = get_user_dir(user_id) / "episodic.json"
    
    if episodic_file.exists():
        try:
            with open(episodic_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading episodic for {user_id}: {e}")
    
    return []


def save_episodic(user_id: str, episodes: List[Dict]) -> bool:
    """Save episodic memories to episodic.json."""
    episodic_file = get_user_dir(user_id) / "episodic.json"
    
    try:
        with open(episodic_file, 'w', encoding='utf-8') as f:
            json.dump(episodes, f, indent=2, ensure_ascii=False)
        return True
    except IOError as e:
        logger.error(f"Error saving episodic for {user_id}: {e}")
        return False


def add_episode(
    user_id: str,
    episode_type: str,
    summary: str,
    significance: str = None,
    context: Dict = None,
    user_message: str = None
) -> Dict:
    """
    Add an episodic memory.
    
    Args:
        user_id: User identifier
        episode_type: breakthrough|commitment|completion|resistance
        summary: Brief summary of the moment
        significance: Why this matters
        context: Additional context (step, phase, etc.)
        user_message: The user's message that triggered this
    
    Returns:
        The created episode dict
    """
    episodes = load_episodic(user_id)
    
    episode = {
        "id": len(episodes) + 1,
        "type": episode_type,
        "summary": summary,
        "significance": significance,
        "context": context or {},
        "user_message": user_message[:200] if user_message else None,
        "created_at": datetime.now().isoformat()
    }
    
    episodes.append(episode)
    save_episodic(user_id, episodes)
    
    logger.info(f"Added episodic memory for {user_id}: {episode_type}")
    
    return episode


def get_episodes_by_type(user_id: str, episode_type: str) -> List[Dict]:
    """Get all episodes of a specific type."""
    episodes = load_episodic(user_id)
    return [e for e in episodes if e.get("type") == episode_type]


def get_recent_episodes(user_id: str, count: int = 5) -> List[Dict]:
    """Get most recent episodes."""
    episodes = load_episodic(user_id)
    return episodes[-count:] if len(episodes) >= count else episodes


def get_completions(user_id: str) -> List[Dict]:
    """Get all completion episodes."""
    return get_episodes_by_type(user_id, "completion")


def get_breakthroughs(user_id: str) -> List[Dict]:
    """Get all breakthrough episodes."""
    return get_episodes_by_type(user_id, "breakthrough")


def get_commitments(user_id: str) -> List[Dict]:
    """Get all commitment episodes."""
    return get_episodes_by_type(user_id, "commitment")


def search_episodes(user_id: str, query: str) -> List[Dict]:
    """Search episodes by content."""
    episodes = load_episodic(user_id)
    query_lower = query.lower()
    
    matches = []
    for ep in episodes:
        searchable = f"{ep.get('summary', '')} {ep.get('significance', '')} {ep.get('user_message', '')}"
        if query_lower in searchable.lower():
            matches.append(ep)
    
    return matches


def get_episode_summary(user_id: str) -> str:
    """
    Get a text summary of episodic memories for LLM context.
    Only includes most significant episodes to stay within token budget.
    """
    episodes = load_episodic(user_id)
    
    if not episodes:
        return "No significant moments recorded."
    
    # Prioritize: breakthroughs > completions > commitments
    breakthroughs = [e for e in episodes if e["type"] == "breakthrough"][-2:]
    completions = [e for e in episodes if e["type"] == "completion"][-3:]
    
    parts = []
    
    if breakthroughs:
        parts.append("Breakthroughs:")
        for b in breakthroughs:
            parts.append(f"  - {b['summary']}")
    
    if completions:
        parts.append("Completions:")
        for c in completions:
            parts.append(f"  - {c['summary']}")
    
    return "\n".join(parts)


def should_retrieve_episodic(user_message: str, context: Dict) -> bool:
    """
    Determine if episodic memory should be retrieved for this interaction.
    
    Triggers:
    - User references past ("before", "last time", "remember when")
    - Pattern repetition detected
    - Major phase transition
    """
    past_references = ["before", "last time", "remember", "earlier", "we talked about"]
    message_lower = user_message.lower()
    
    # Check for explicit past references
    if any(ref in message_lower for ref in past_references):
        return True
    
    # Check for pattern repetition
    pattern_flags = context.get("pattern_flags", {})
    high_patterns = [k for k, v in pattern_flags.items() if isinstance(v, float) and v > 0.5]
    if high_patterns:
        return True
    
    return False
