"""
Prediction Bot Configuration
Loads from .env file or environment variables.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()

# ============================================================================
# API KEYS
# ============================================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")  # For Whisper transcription

# ============================================================================
# LLM CONFIGURATION
# ============================================================================

# Primary model for coaching responses
PRIMARY_MODEL = "claude-sonnet-4-20250514"

# Fast model for extraction tasks
EXTRACTION_MODEL = "claude-sonnet-4-20250514"

# Cache TTL for prompt caching (1 hour recommended for multi-user)
CACHE_TTL = "1h"

# ============================================================================
# PATHS
# ============================================================================

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data" / "users"
INSTANCES_DIR = BASE_DIR / "instances"
FRAMEWORKS_DIR = BASE_DIR / "frameworks"

# ============================================================================
# ADMIN
# ============================================================================

ADMIN_USER_ID = "6904183057"

# ============================================================================
# SECURITY LIMITS
# ============================================================================

MAX_MESSAGE_LENGTH = 1000           # Characters per message
MAX_MESSAGES_PER_MINUTE = 10        # Default for regular users
MAX_MESSAGES_PER_HOUR = 100         # Default for regular users
MAX_SUSPICIOUS_ATTEMPTS = 3         # Before temporary block
BLOCK_DURATION_MINUTES = 30
MAX_INPUT_TOKENS = 2500             # Context budget cap

# ============================================================================
# MEMORY SETTINGS
# ============================================================================

RECENT_MESSAGES_COUNT = 5           # Always loaded
MAX_FACTS_TOKENS = 500              # Approximate token budget for facts
SESSION_TIMEOUT_HOURS = 2           # Silence threshold for session end

# ============================================================================
# SCHEDULED MESSAGES
# ============================================================================

REENGAGEMENT_WINDOWS = {
    "soft_ping_hours": (24, 48),    # First re-engagement
    "pattern_callout_hours": (48, 72),
    "direct_question_hours": 72     # After this
}

# ============================================================================
# VOICE SETTINGS
# ============================================================================

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
DEFAULT_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "jRI54nLfVot0kbYqbGF5")
