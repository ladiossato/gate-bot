"""
Scheduled Messages Module
Handles dynamic re-engagement message scheduling based on user activity patterns.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import random

from config import DATA_DIR, REENGAGEMENT_WINDOWS

logger = logging.getLogger(__name__)


def get_user_dir(user_id: str) -> Path:
    """Get or create user data directory."""
    user_dir = DATA_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def load_activity(user_id: str) -> Dict:
    """Load user activity data for availability inference."""
    activity_file = get_user_dir(user_id) / "activity.json"
    
    if activity_file.exists():
        try:
            with open(activity_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading activity for {user_id}: {e}")
    
    return {
        "user_id": user_id,
        "message_timestamps": [],
        "response_latencies": [],
        "inferred_windows": {},
        "last_analyzed": None
    }


def save_activity(user_id: str, activity: Dict) -> bool:
    """Save user activity data."""
    activity_file = get_user_dir(user_id) / "activity.json"
    
    try:
        with open(activity_file, 'w', encoding='utf-8') as f:
            json.dump(activity, f, indent=2, ensure_ascii=False)
        return True
    except IOError as e:
        logger.error(f"Error saving activity for {user_id}: {e}")
        return False


def record_user_activity(user_id: str, response_latency: float = None):
    """
    Record a user message for activity pattern inference.
    
    Args:
        user_id: User identifier
        response_latency: Seconds between bot message and user response (if applicable)
    """
    activity = load_activity(user_id)
    
    now = datetime.now()
    activity["message_timestamps"].append(now.isoformat())
    
    if response_latency is not None:
        activity["response_latencies"].append(response_latency)
    
    # Keep only last 100 timestamps
    activity["message_timestamps"] = activity["message_timestamps"][-100:]
    activity["response_latencies"] = activity["response_latencies"][-100:]
    
    save_activity(user_id, activity)


def analyze_availability_windows(user_id: str) -> Dict:
    """
    Analyze user message patterns to infer availability windows.
    Returns dict of window_name -> {start, end, confidence}
    """
    activity = load_activity(user_id)
    timestamps = activity.get("message_timestamps", [])
    
    if len(timestamps) < 5:
        # Not enough data, return default windows
        return {
            "morning": {"start": "08:00", "end": "10:00", "confidence": 0.3},
            "evening": {"start": "19:00", "end": "22:00", "confidence": 0.3}
        }
    
    # Parse timestamps and bucket by hour and day type
    weekday_hours = {}
    weekend_hours = {}
    
    for ts_str in timestamps:
        try:
            ts = datetime.fromisoformat(ts_str)
            hour = ts.hour
            is_weekend = ts.weekday() >= 5
            
            bucket = weekend_hours if is_weekend else weekday_hours
            bucket[hour] = bucket.get(hour, 0) + 1
        except ValueError:
            continue
    
    windows = {}
    
    # Find peak weekday hours
    if weekday_hours:
        sorted_hours = sorted(weekday_hours.items(), key=lambda x: x[1], reverse=True)
        if sorted_hours:
            peak_hour = sorted_hours[0][0]
            total = sum(weekday_hours.values())
            confidence = sorted_hours[0][1] / total if total > 0 else 0.3
            
            # Determine window type based on hour
            if 5 <= peak_hour <= 11:
                windows["weekday_morning"] = {
                    "start": f"{max(5, peak_hour - 1):02d}:00",
                    "end": f"{min(12, peak_hour + 1):02d}:00",
                    "confidence": min(0.9, confidence + 0.2)
                }
            elif 17 <= peak_hour <= 23:
                windows["weekday_evening"] = {
                    "start": f"{max(17, peak_hour - 1):02d}:00",
                    "end": f"{min(23, peak_hour + 1):02d}:00",
                    "confidence": min(0.9, confidence + 0.2)
                }
            else:
                windows["weekday_afternoon"] = {
                    "start": f"{max(12, peak_hour - 1):02d}:00",
                    "end": f"{min(17, peak_hour + 1):02d}:00",
                    "confidence": min(0.9, confidence + 0.2)
                }
    
    # Find peak weekend hours
    if weekend_hours:
        sorted_hours = sorted(weekend_hours.items(), key=lambda x: x[1], reverse=True)
        if sorted_hours:
            peak_hour = sorted_hours[0][0]
            total = sum(weekend_hours.values())
            confidence = sorted_hours[0][1] / total if total > 0 else 0.3
            
            windows["weekend"] = {
                "start": f"{max(8, peak_hour - 1):02d}:00",
                "end": f"{min(22, peak_hour + 1):02d}:00",
                "confidence": min(0.9, confidence + 0.2)
            }
    
    # Update stored windows
    activity["inferred_windows"] = windows
    activity["last_analyzed"] = datetime.now().isoformat()
    save_activity(user_id, activity)
    
    return windows


def get_best_send_time(user_id: str, min_hours_from_now: float = 1) -> datetime:
    """
    Calculate the best time to send a re-engagement message.
    
    Args:
        user_id: User identifier
        min_hours_from_now: Minimum hours in the future
    
    Returns:
        Optimal datetime for sending message
    """
    windows = analyze_availability_windows(user_id)
    now = datetime.now()
    min_time = now + timedelta(hours=min_hours_from_now)
    
    # Determine if we should use weekday or weekend window
    target_day = min_time.weekday()
    is_weekend = target_day >= 5
    
    # Select appropriate window
    if is_weekend and "weekend" in windows:
        window = windows["weekend"]
    elif not is_weekend:
        # Prefer morning for re-engagement
        if "weekday_morning" in windows:
            window = windows["weekday_morning"]
        elif "weekday_evening" in windows:
            window = windows["weekday_evening"]
        else:
            window = list(windows.values())[0] if windows else {"start": "09:00", "end": "10:00"}
    else:
        window = list(windows.values())[0] if windows else {"start": "09:00", "end": "10:00"}
    
    # Parse window times
    start_hour, start_min = map(int, window["start"].split(":"))
    end_hour, end_min = map(int, window["end"].split(":"))
    
    # Create target datetime
    target = min_time.replace(hour=start_hour, minute=start_min, second=0, microsecond=0)
    
    # If target is in the past, move to next day
    if target < min_time:
        target += timedelta(days=1)
    
    # Add some randomness within the window (±30 min)
    variance_minutes = random.randint(-30, 30)
    target += timedelta(minutes=variance_minutes)
    
    # Ensure within window bounds
    window_start = target.replace(hour=start_hour, minute=start_min)
    window_end = target.replace(hour=end_hour, minute=end_min)
    
    if target < window_start:
        target = window_start
    elif target > window_end:
        target = window_end
    
    return target


def load_scheduled(user_id: str) -> Dict:
    """Load scheduled messages for user."""
    scheduled_file = get_user_dir(user_id) / "scheduled.json"
    
    if scheduled_file.exists():
        try:
            with open(scheduled_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading scheduled for {user_id}: {e}")
    
    return {"pending": [], "sent": []}


def save_scheduled(user_id: str, scheduled: Dict) -> bool:
    """Save scheduled messages."""
    scheduled_file = get_user_dir(user_id) / "scheduled.json"
    
    try:
        with open(scheduled_file, 'w', encoding='utf-8') as f:
            json.dump(scheduled, f, indent=2, ensure_ascii=False)
        return True
    except IOError as e:
        logger.error(f"Error saving scheduled for {user_id}: {e}")
        return False


def schedule_reengagement(
    user_id: str,
    trigger_type: str = "soft_ping",
    hours_from_now: float = None
) -> Dict:
    """
    Schedule a re-engagement message.
    
    Args:
        user_id: User identifier
        trigger_type: soft_ping|pattern_callout|direct_question
        hours_from_now: Override for timing (uses inferred windows if None)
    
    Returns:
        The scheduled message dict
    """
    scheduled = load_scheduled(user_id)
    
    # Cancel any existing pending messages
    scheduled["pending"] = []
    
    # Determine timing
    if hours_from_now:
        send_at = datetime.now() + timedelta(hours=hours_from_now)
    else:
        # Use availability windows with appropriate minimum delay
        min_hours = {
            "soft_ping": 24,
            "pattern_callout": 48,
            "direct_question": 72
        }.get(trigger_type, 24)
        
        send_at = get_best_send_time(user_id, min_hours_from_now=min_hours)
    
    message_entry = {
        "id": len(scheduled.get("sent", [])) + len(scheduled.get("pending", [])) + 1,
        "type": trigger_type,
        "send_at": send_at.isoformat(),
        "created_at": datetime.now().isoformat(),
        "status": "pending",
        "cancel_conditions": ["user_message", "step_completion"]
    }
    
    scheduled["pending"].append(message_entry)
    save_scheduled(user_id, scheduled)
    
    logger.info(f"Scheduled {trigger_type} for user {user_id} at {send_at}")
    
    return message_entry


def cancel_pending(user_id: str, reason: str = "user_message") -> int:
    """
    Cancel all pending scheduled messages.
    
    Args:
        user_id: User identifier
        reason: Why cancelled (user_message, step_completion, manual)
    
    Returns:
        Number of messages cancelled
    """
    scheduled = load_scheduled(user_id)
    
    cancelled_count = len(scheduled.get("pending", []))
    
    # Move pending to sent with cancelled status
    for msg in scheduled.get("pending", []):
        msg["status"] = "cancelled"
        msg["cancelled_at"] = datetime.now().isoformat()
        msg["cancel_reason"] = reason
        scheduled["sent"].append(msg)
    
    scheduled["pending"] = []
    save_scheduled(user_id, scheduled)
    
    if cancelled_count > 0:
        logger.info(f"Cancelled {cancelled_count} pending messages for {user_id}")
    
    return cancelled_count


def get_due_messages() -> List[Tuple[str, Dict]]:
    """
    Get all messages that are due to be sent across all users.
    
    Returns:
        List of (user_id, message_dict) tuples
    """
    due = []
    now = datetime.now()
    
    # Iterate through all user directories
    if DATA_DIR.exists():
        for user_dir in DATA_DIR.iterdir():
            if user_dir.is_dir():
                user_id = user_dir.name
                scheduled = load_scheduled(user_id)
                
                for msg in scheduled.get("pending", []):
                    send_at = datetime.fromisoformat(msg["send_at"])
                    if send_at <= now:
                        due.append((user_id, msg))
    
    return due


def mark_sent(user_id: str, message_id: int, actual_message: str) -> bool:
    """
    Mark a scheduled message as sent.
    
    Args:
        user_id: User identifier
        message_id: ID of the scheduled message
        actual_message: The message that was actually sent
    
    Returns:
        Success status
    """
    scheduled = load_scheduled(user_id)
    
    for i, msg in enumerate(scheduled.get("pending", [])):
        if msg.get("id") == message_id:
            msg["status"] = "sent"
            msg["sent_at"] = datetime.now().isoformat()
            msg["actual_message"] = actual_message
            
            scheduled["sent"].append(msg)
            scheduled["pending"].pop(i)
            
            save_scheduled(user_id, scheduled)
            return True
    
    return False


# Re-engagement message generation prompts (used by the engine)
REENGAGEMENT_PROMPTS = {
    "soft_ping": """
Generate a very short re-engagement message (1-5 words).
Rules:
- No question marks
- No motivation or encouragement
- Just start the conversation casually
- Like you're mid-thought
Examples: "Hey", "Still here", "So", "You went quiet"
Generate one message:
""",
    
    "pattern_callout": """
Generate a short re-engagement message that notes the silence (5-10 words).
Rules:
- Acknowledge they went quiet
- No accusation, just observation
- No question marks
Examples: "You went quiet after that", "Thought so", "The pattern again"
Generate one message:
""",
    
    "direct_question": """
Generate a direct re-engagement question (3-7 words).
Rules:
- One direct question
- About whether they're continuing
- No softening language
Examples: "Are you still doing this?", "Still in?", "Done or continuing?"
Generate one message:
"""
}
