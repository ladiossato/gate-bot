"""
Facts Storage Module
Handles long-term facts about the user extracted from conversation.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List

from config import DATA_DIR

logger = logging.getLogger(__name__)


def get_user_dir(user_id: str) -> Path:
    """Get or create user data directory."""
    user_dir = DATA_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def load_facts(user_id: str) -> Dict:
    """Load user facts from facts.json."""
    facts_file = get_user_dir(user_id) / "facts.json"
    
    if facts_file.exists():
        try:
            with open(facts_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading facts for {user_id}: {e}")
    
    # Default facts structure
    return {
        "user_id": user_id,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "identity": {},
        "goal": None,
        "context": {},
        "resources": {},
        "blockers": [],
        "commitments": [],
        "pinned": []  # User-pinned facts via /save
    }


def save_facts(user_id: str, facts: Dict) -> bool:
    """Save user facts to facts.json."""
    facts_file = get_user_dir(user_id) / "facts.json"
    facts["updated_at"] = datetime.now().isoformat()
    
    try:
        with open(facts_file, 'w', encoding='utf-8') as f:
            json.dump(facts, f, indent=2, ensure_ascii=False)
        return True
    except IOError as e:
        logger.error(f"Error saving facts for {user_id}: {e}")
        return False


def merge_facts(user_id: str, new_facts: Dict) -> Dict:
    """
    Merge new facts with existing facts.
    Handles deduplication for lists.
    """
    current = load_facts(user_id)
    
    for key, value in new_facts.items():
        if not value:
            continue
            
        if key in ['blockers', 'commitments']:
            # Append to lists, avoiding duplicates
            existing = current.get(key, [])
            for item in value:
                if item not in existing:
                    existing.append(item)
            current[key] = existing
        elif key in ['identity', 'context', 'resources']:
            # Merge dicts
            existing = current.get(key, {})
            existing.update(value)
            current[key] = existing
        else:
            # Direct assignment
            current[key] = value
    
    save_facts(user_id, current)
    return current


def set_goal(user_id: str, goal: str) -> Dict:
    """Set the user's primary goal."""
    facts = load_facts(user_id)
    facts["goal"] = goal
    save_facts(user_id, facts)
    return facts


def add_pinned(user_id: str, content: str, source: str = "user") -> Dict:
    """
    Add a pinned fact (user-saved via /save).
    Max 20 pinned items.
    """
    facts = load_facts(user_id)
    
    pinned = facts.get("pinned", [])
    
    # Check limit
    if len(pinned) >= 20:
        return {"error": "Maximum 20 pinned items. Use /forget to remove some."}
    
    pinned_item = {
        "id": len(pinned) + 1,
        "content": content,
        "source": source,
        "pinned_at": datetime.now().isoformat()
    }
    
    pinned.append(pinned_item)
    facts["pinned"] = pinned
    
    save_facts(user_id, facts)
    return pinned_item


def remove_pinned(user_id: str, pin_id: int) -> bool:
    """Remove a pinned fact by ID."""
    facts = load_facts(user_id)
    
    pinned = facts.get("pinned", [])
    original_len = len(pinned)
    
    pinned = [p for p in pinned if p.get("id") != pin_id]
    
    if len(pinned) < original_len:
        # Re-number remaining items
        for i, item in enumerate(pinned, 1):
            item["id"] = i
        
        facts["pinned"] = pinned
        save_facts(user_id, facts)
        return True
    
    return False


def get_pinned(user_id: str) -> List[Dict]:
    """Get all pinned facts."""
    facts = load_facts(user_id)
    return facts.get("pinned", [])


def get_facts_summary(user_id: str) -> str:
    """
    Get a text summary of facts for LLM context.
    """
    facts = load_facts(user_id)
    
    parts = []
    
    if facts.get("goal"):
        parts.append(f"Goal: {facts['goal']}")
    
    if facts.get("identity"):
        identity_items = [f"{k}: {v}" for k, v in facts["identity"].items()]
        if identity_items:
            parts.append(f"Identity: {', '.join(identity_items)}")
    
    if facts.get("context"):
        context_items = [f"{k}: {v}" for k, v in facts["context"].items()]
        if context_items:
            parts.append(f"Context: {', '.join(context_items)}")
    
    if facts.get("blockers"):
        parts.append(f"Blockers: {', '.join(facts['blockers'])}")
    
    if facts.get("pinned"):
        pinned_items = [f"- {p['content']}" for p in facts["pinned"]]
        parts.append(f"Pinned:\n" + "\n".join(pinned_items))
    
    return "\n".join(parts) if parts else "No facts recorded."
