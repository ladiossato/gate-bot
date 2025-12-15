"""
Security Module
Multi-layer defense against prompt injection and data leakage.
"""

import re
import unicodedata
from datetime import datetime, timedelta
from typing import Tuple, Optional, Dict
import json

from config import (
    MAX_MESSAGE_LENGTH,
    MAX_MESSAGES_PER_MINUTE,
    MAX_MESSAGES_PER_HOUR,
    MAX_SUSPICIOUS_ATTEMPTS,
    BLOCK_DURATION_MINUTES,
    ADMIN_USER_ID,
)


import logging

logger = logging.getLogger(__name__)


class InputSanitizer:
    """Layer 1: Input sanitization and injection detection."""

    # Disagreement patterns that should NOT trigger security
    # These are normal user responses when they disagree with bot's assessment
    DISAGREEMENT_PATTERNS = [
        r"i\s+don'?t\s+have",
        r"i\s+don'?t\s+own",
        r"that'?s\s+not",
        r"who\s+said",
        r"i\s+never\s+said",
        r"^no[,.\s]",
        r"^wrong",
        r"that'?s\s+not\s+the\s+problem",
        r"not\s+what\s+i\s+(meant|said)",
        r"you'?re\s+(wrong|mistaken)",
        r"that'?s\s+incorrect",
        r"i\s+didn'?t\s+say",
    ]

    def __init__(self):
        # Direct instruction override patterns
        self.dangerous_patterns = [
            r'ignore\s+(all\s+)?previous\s+instructions?',
            r'disregard\s+(all\s+)?(your\s+)?(previous\s+)?instructions?',
            r'forget\s+(all\s+)?(your\s+)?rules',
            r'you\s+are\s+now\s+',
            r'act\s+as\s+(if\s+)?(you\s+)?(are\s+|were\s+)?',
            r'pretend\s+(you\s+)?(are\s+|to\s+be\s+)',
            r'roleplay\s+as',
            r'simulate\s+',
            r'system\s+(prompt|override|mode|instruction)',
            r'developer\s+mode',
            r'admin\s+(mode|access|override)',
            r'jailbreak',
            r'bypass\s+(safety|restrictions?|filters?)',
            r'output\s+without\s+filter',
            r'unrestricted\s+mode',
            r'new\s+persona',
            r'new\s+instructions?',
            r'\bDAN\b',  # "Do Anything Now" jailbreak
            r'SECURITY_CANARY',  # Canary token
        ]
        
        # Obfuscation detection
        self.obfuscation_patterns = [
            r'base64',
            r'decode\s+this',
            r'hex\s+encode',
            r'rot13',
        ]
        
        # Sensitive data patterns (for redaction, not blocking)
        self.sensitive_patterns = [
            (r'\b\d{3}-\d{2}-\d{4}\b', 'SSN'),  # SSN
            (r'\b\d{16}\b', 'CARD'),  # Credit card (basic)
            (r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', 'CARD'),  # Credit card with spaces
            (r'password[:\s]+\S+', 'PASSWORD'),
            (r'api[_\s]?key[:\s]+\S+', 'API_KEY'),
        ]
        
        # Leetspeak mapping for normalization
        self.leet_map = {
            '0': 'o', '1': 'i', '3': 'e', '4': 'a', 
            '5': 's', '7': 't', '@': 'a', '$': 's'
        }
    
    def normalize_text(self, text: str) -> str:
        """Normalize Unicode and common obfuscations."""
        # Unicode normalization (handles homoglyphs)
        text = unicodedata.normalize('NFKC', text)
        
        # Remove zero-width characters
        text = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', text)
        
        # Leetspeak normalization for detection
        normalized = text.lower()
        for leet, char in self.leet_map.items():
            normalized = normalized.replace(leet, char)
        
        return normalized
    
    def detect_injection(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Detect potential injection attempts.
        Returns: (is_suspicious, pattern_matched)
        """
        normalized = self.normalize_text(text)

        # Check for disagreement patterns FIRST - these are NOT suspicious
        for pattern in self.DISAGREEMENT_PATTERNS:
            if re.search(pattern, normalized, re.IGNORECASE):
                logger.debug(f"[SECURITY] Disagreement pattern matched: {pattern} - NOT suspicious")
                return False, None

        for pattern in self.dangerous_patterns:
            if re.search(pattern, normalized, re.IGNORECASE):
                logger.info(f"[SECURITY] Dangerous pattern matched: {pattern}")
                return True, pattern

        for pattern in self.obfuscation_patterns:
            if re.search(pattern, normalized, re.IGNORECASE):
                logger.info(f"[SECURITY] Obfuscation pattern matched: {pattern}")
                return True, f"obfuscation:{pattern}"

        return False, None
    
    def redact_sensitive(self, text: str) -> Tuple[str, list]:
        """
        Redact sensitive information from text.
        Returns: (redacted_text, list of redaction types)
        """
        redactions = []
        redacted = text
        
        for pattern, redaction_type in self.sensitive_patterns:
            if re.search(pattern, redacted, re.IGNORECASE):
                redacted = re.sub(pattern, f'[REDACTED_{redaction_type}]', redacted, flags=re.IGNORECASE)
                redactions.append(redaction_type)
        
        return redacted, redactions
    
    def sanitize(self, text: str) -> Dict:
        """
        Full sanitization pipeline.
        Returns dict with sanitized text and metadata.
        """
        # Length check
        if len(text) > MAX_MESSAGE_LENGTH:
            return {
                'text': text[:MAX_MESSAGE_LENGTH],
                'truncated': True,
                'suspicious': False,
                'redactions': [],
                'blocked': False,
                'block_reason': None
            }
        
        # Injection detection
        suspicious, pattern = self.detect_injection(text)
        
        # Sensitive data redaction
        redacted_text, redactions = self.redact_sensitive(text)
        
        return {
            'text': redacted_text,
            'truncated': False,
            'suspicious': suspicious,
            'suspicious_pattern': pattern,
            'redactions': redactions,
            'blocked': False,
            'block_reason': None
        }


class OutputFilter:
    """Layer 2: Output filtering to prevent prompt leakage."""
    
    def __init__(self):
        self.leak_patterns = [
            r'system\s+prompt',
            r'my\s+instructions',
            r'I\s+was\s+(told|instructed|programmed)\s+to',
            r'my\s+programming',
            r'my\s+rules\s+(say|are)',
            r'I\s+cannot\s+reveal',
            r'SECURITY_CANARY',
            r'\[REDACTED',  # Don't leak redaction markers
        ]
        
        self.replacement = "That's not how this works."
    
    def filter(self, response: str) -> Tuple[str, bool]:
        """
        Filter response for potential leakage.
        Returns: (filtered_response, was_filtered)
        """
        for pattern in self.leak_patterns:
            if re.search(pattern, response, re.IGNORECASE):
                return self.replacement, True
        
        return response, False


class RateLimiter:
    """Layer 3: Rate limiting to prevent abuse."""

    def __init__(self):
        self.user_requests: Dict[str, list] = {}
        self.user_blocks: Dict[str, datetime] = {}
        self.suspicious_counts: Dict[str, int] = {}
        # Per-user rate limits: {user_id: {"per_minute": X, "per_hour": Y}}
        self.user_limits: Dict[str, Dict[str, int]] = {}

    def set_user_limit(self, user_id: str, per_minute: int = None, per_hour: int = None):
        """Set custom rate limits for a specific user."""
        if user_id not in self.user_limits:
            self.user_limits[user_id] = {}
        if per_minute is not None:
            self.user_limits[user_id]["per_minute"] = per_minute
        if per_hour is not None:
            self.user_limits[user_id]["per_hour"] = per_hour

    def get_user_limits(self, user_id: str) -> Tuple[int, int]:
        """Get rate limits for a user (custom or default)."""
        # Admin has no limits
        if user_id == ADMIN_USER_ID:
            return 9999, 99999

        user_lim = self.user_limits.get(user_id, {})
        per_min = user_lim.get("per_minute", MAX_MESSAGES_PER_MINUTE)
        per_hr = user_lim.get("per_hour", MAX_MESSAGES_PER_HOUR)
        return per_min, per_hr

    def remove_user_limit(self, user_id: str):
        """Remove custom limits for a user (revert to defaults)."""
        if user_id in self.user_limits:
            del self.user_limits[user_id]

    def _cleanup_old_requests(self, user_id: str):
        """Remove requests older than 1 hour."""
        if user_id not in self.user_requests:
            return

        cutoff = datetime.now() - timedelta(hours=1)
        self.user_requests[user_id] = [
            ts for ts in self.user_requests[user_id] if ts > cutoff
        ]

    def check_rate_limit(self, user_id: str) -> Tuple[bool, Optional[str]]:
        """
        Check if user is within rate limits.
        Returns: (allowed, block_reason)
        """
        now = datetime.now()

        # Check if user is blocked
        if user_id in self.user_blocks:
            if now < self.user_blocks[user_id]:
                remaining = (self.user_blocks[user_id] - now).seconds // 60
                return False, f"Blocked for {remaining} more minutes"
            else:
                del self.user_blocks[user_id]
                self.suspicious_counts[user_id] = 0

        # Initialize if needed
        if user_id not in self.user_requests:
            self.user_requests[user_id] = []

        self._cleanup_old_requests(user_id)

        # Get limits for this user
        max_per_minute, max_per_hour = self.get_user_limits(user_id)

        # Check per-minute limit
        minute_ago = now - timedelta(minutes=1)
        recent_minute = [ts for ts in self.user_requests[user_id] if ts > minute_ago]
        if len(recent_minute) >= max_per_minute:
            return False, "Too many messages. Slow down."

        # Check per-hour limit
        if len(self.user_requests[user_id]) >= max_per_hour:
            return False, "Hourly limit reached. Try again later."

        # Record this request
        self.user_requests[user_id].append(now)

        return True, None

    def record_suspicious(self, user_id: str) -> bool:
        """
        Record a suspicious attempt. Returns True if user should be blocked.
        """
        if user_id not in self.suspicious_counts:
            self.suspicious_counts[user_id] = 0

        self.suspicious_counts[user_id] += 1

        if self.suspicious_counts[user_id] >= MAX_SUSPICIOUS_ATTEMPTS:
            self.user_blocks[user_id] = datetime.now() + timedelta(minutes=BLOCK_DURATION_MINUTES)
            return True

        return False


class ConversationMonitor:
    """Layer 4: Conversation-level manipulation detection."""
    
    def __init__(self):
        self.manipulation_threshold = 3  # Red flags in last 10 messages
    
    def check_escalation(self, recent_messages: list, sanitizer: InputSanitizer) -> Tuple[bool, int]:
        """
        Check for gradual manipulation attempts across conversation.
        Returns: (is_escalating, red_flag_count)
        """
        red_flags = 0
        
        for msg in recent_messages[-10:]:
            if msg.get('role') == 'user':
                suspicious, _ = sanitizer.detect_injection(msg.get('content', ''))
                if suspicious:
                    red_flags += 1
        
        return red_flags >= self.manipulation_threshold, red_flags


# Global instances
sanitizer = InputSanitizer()
output_filter = OutputFilter()
rate_limiter = RateLimiter()
conversation_monitor = ConversationMonitor()


def process_input(user_id: str, text: str, recent_messages: list = None) -> Dict:
    """
    Full security pipeline for user input.
    Returns dict with processed input and security status.
    """
    # Rate limiting
    allowed, block_reason = rate_limiter.check_rate_limit(user_id)
    if not allowed:
        return {
            'allowed': False,
            'reason': block_reason,
            'text': None
        }
    
    # Input sanitization
    result = sanitizer.sanitize(text)
    
    # Handle suspicious input
    if result['suspicious']:
        blocked = rate_limiter.record_suspicious(user_id)
        if blocked:
            return {
                'allowed': False,
                'reason': 'Temporarily blocked due to repeated violations',
                'text': None
            }
        result['warning'] = True
    
    # Conversation-level check
    if recent_messages:
        escalating, count = conversation_monitor.check_escalation(
            recent_messages + [{'role': 'user', 'content': text}],
            sanitizer
        )
        if escalating:
            result['escalation_detected'] = True
            result['red_flag_count'] = count
    
    result['allowed'] = True
    return result


def process_output(response: str) -> str:
    """Filter LLM output before sending to user."""
    filtered, _ = output_filter.filter(response)
    return filtered
