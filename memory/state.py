"""
State Management - Simplified

Simple user state: name, commitment, deadline.
No phases. No progression. No pattern flags.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict

from config import DATA_DIR

logger = logging.getLogger(__name__)


def get_user_dir(user_id: str) -> Path:
    """Get or create user data directory."""
    user_dir = DATA_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def load_state(user_id: str) -> Dict:
    """
    Load user state from state.json.
    Returns default state if not found.
    """
    state_file = get_user_dir(user_id) / "state.json"

    if state_file.exists():
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading state for {user_id}: {e}")

    # Default state - simple
    return {
        "user_id": user_id,
        "username": None,  # Telegram @username
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "user": {
            "name": None,
            "commitment": None,
            "deadline": None
        },
        "coaching": {
            "current_step": None,
            "step_number": 0,
            "awaiting_completion": False,
            "completed_steps": [],
            "true_constraint": None,
            "goal": None
        }
    }


def save_state(user_id: str, state: Dict) -> bool:
    """Save user state to state.json."""
    state_file = get_user_dir(user_id) / "state.json"
    state["updated_at"] = datetime.now().isoformat()

    try:
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        return True
    except IOError as e:
        logger.error(f"Error saving state for {user_id}: {e}")
        return False


def clear_user_data(user_id: str) -> bool:
    """Clear all user data (for /clear command)."""
    user_dir = get_user_dir(user_id)

    try:
        for file in user_dir.iterdir():
            file.unlink()
        return True
    except Exception as e:
        logger.error(f"Error clearing data for {user_id}: {e}")
        return False
