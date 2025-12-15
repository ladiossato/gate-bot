"""
Response Engine - Elite Coach

Receive message → detect completion → call agent → save history → return response
"""

import logging
import re
from typing import Dict, Any

from core.security import process_input, process_output
from core.agent import gate_agent
from memory.state import load_state, save_state
from memory.history import append_message, get_recent_messages

logger = logging.getLogger(__name__)


class ResponseEngine:
    """
    Elite Coach response engine.

    1. Security check
    2. Load/init user state
    3. Detect completion signals
    4. Get history
    5. Call agent with coaching state
    6. Extract name if present
    7. Save history
    8. Return response
    """

    def process_message(
        self,
        user_id: str,
        message: str,
        username: str = None
    ) -> Dict[str, Any]:
        """
        Process a user message and return response.

        Args:
            user_id: Unique user identifier
            message: The user's message
            username: Optional username from platform

        Returns:
            Dict with 'response' and 'phase'
        """
        # 1. Security check
        recent = get_recent_messages(user_id, count=5)
        security_result = process_input(
            user_id,
            message,
            [{"role": "user", "content": m["content"]} for m in recent]
        )

        if not security_result['allowed']:
            return {
                'response': security_result['reason'],
                'phase': 'blocked'
            }

        message = security_result['text']

        # 2. Load or initialize state
        state = load_state(user_id)
        if "user" not in state:
            state["user"] = {}
        if "coaching" not in state:
            state["coaching"] = {
                "current_step": None,
                "step_number": 0,
                "awaiting_completion": False,
                "completed_steps": [],
                "true_constraint": None,
                "goal": None
            }

        # Save Telegram username (the @handle) for logging
        if username:
            state["username"] = username

        # 3. Detect completion signals
        is_completion = self._detect_completion(message)
        if is_completion and state["coaching"].get("awaiting_completion"):
            # Mark step as completed
            current_step = state["coaching"].get("current_step")
            if current_step:
                state["coaching"]["completed_steps"].append(current_step)
                state["coaching"]["step_number"] += 1
            state["coaching"]["awaiting_completion"] = False
            state["coaching"]["current_step"] = None

        # 4. Save user message to history
        append_message(user_id, "user", message)

        # 5. Get conversation history for agent
        history = self._get_history(user_id)

        # 6. Build user state for agent context
        user_state = {
            "name": state["user"].get("name"),
            "commitment": state["user"].get("commitment"),
            "deadline": state["user"].get("deadline"),
            "coaching": state.get("coaching", {})
        }

        # 7. Get response from agent
        response = gate_agent.respond(history, user_state)

        # 8. Extract name if user provided it
        extracted_name = self._extract_name(message)
        if extracted_name:
            state["user"]["name"] = extracted_name

        # 9. Detect if Gate gave a step (for tracking)
        step_given = self._detect_step_assignment(response)
        if step_given:
            state["coaching"]["current_step"] = step_given
            state["coaching"]["awaiting_completion"] = True

        # 10. Save assistant response to history
        append_message(user_id, "assistant", response)

        # 11. Save updated state
        save_state(user_id, state)

        # 12. Security filter on output
        response = process_output(response)

        return {
            'response': response,
            'phase': 'coaching'
        }

    def _get_history(self, user_id: str) -> list:
        """Get conversation history formatted for agent."""
        recent = get_recent_messages(user_id, count=20)
        return [{"role": m["role"], "content": m["content"]} for m in recent]

    def _detect_completion(self, message: str) -> bool:
        """Detect if user is reporting step completion."""
        msg_lower = message.lower().strip()

        completion_signals = [
            "done", "did it", "finished", "completed", "i did",
            "just did", "got it done", "it's done", "okay done",
            "alright done", "yes done", "yep done", "did that",
            "okay i did", "alright i did", "yes i did", "yep i did",
            "i did it", "i've done", "ive done", "just finished",
            "okay i did it", "alright i did it", "done it"
        ]

        return any(signal in msg_lower for signal in completion_signals)

    def _detect_step_assignment(self, response: str) -> str | None:
        """Detect if Gate assigned a step in the response."""
        resp_lower = response.lower()

        # Look for gate patterns indicating a step was given
        gate_patterns = [
            "when you've done this, tell me",
            "when done, tell me",
            "tell me when done",
            "tell me when you've done",
            "let me know when",
            "when you're done"
        ]

        if any(pattern in resp_lower for pattern in gate_patterns):
            # Extract the step - it's usually the sentence before the gate
            sentences = response.split('.')
            for i, sent in enumerate(sentences):
                if any(pattern in sent.lower() for pattern in gate_patterns):
                    # Return the previous sentence as the step
                    if i > 0:
                        return sentences[i-1].strip()
                    break

            # If no previous sentence, try to extract from response
            # Look for action-oriented first sentence
            if sentences:
                return sentences[0].strip()

        return None

    def _extract_name(self, message: str) -> str | None:
        """Extract name from message if user is introducing themselves."""
        message_lower = message.lower().strip()

        # Patterns: "i'm X", "my name is X", "call me X", "it's X", "X here"
        patterns = [
            r"(?:i'm|im|i am)\s+([a-z]+)",
            r"(?:my name is|name's|names)\s+([a-z]+)",
            r"(?:call me|they call me)\s+([a-z]+)",
            r"(?:it's|its)\s+([a-z]+)",
            r"^([a-z]+)\s+here$",
            r"^([a-z]+)$"  # Just a name by itself (response to "what's your name")
        ]

        for pattern in patterns:
            match = re.search(pattern, message_lower)
            if match:
                name = match.group(1)
                # Filter out common non-names
                non_names = ["me", "i", "my", "the", "a", "an", "ok", "okay", "yes", "no", "hey", "hi", "hello", "good", "fine", "great", "done", "did", "just", "yep", "yeah"]
                if name not in non_names and len(name) > 1:
                    return name.capitalize()

        return None


# Global engine instance
engine = ResponseEngine()
