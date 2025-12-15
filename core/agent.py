"""
Gate Agent - Pure Stance

System prompt + history → response
No frameworks. No methods. Just seeing.
"""

import logging
from pathlib import Path
from typing import List, Dict

from core.llm import llm_client

logger = logging.getLogger(__name__)

VOICE_PROMPT_PATH = Path(__file__).parent.parent / "instances" / "base" / "gate_voice.md"


class GateAgent:

    def __init__(self):
        self.system_prompt = self._load_voice_prompt()
        logger.info(f"[AGENT] Loaded voice prompt: {len(self.system_prompt)} chars")

    def _load_voice_prompt(self) -> str:
        try:
            return VOICE_PROMPT_PATH.read_text(encoding="utf-8")
        except FileNotFoundError:
            logger.error(f"Voice prompt not found at {VOICE_PROMPT_PATH}")
            return "you are gate. you see what people are actually doing underneath what they say. you ask questions that expose the gap. you don't pretend along with them."

    def reload(self):
        self.system_prompt = self._load_voice_prompt()

    def respond(self, history: List[Dict], user_state: Dict = None) -> str:
        user_state = user_state or {}

        # Minimal context
        context_parts = []
        if user_state.get("name"):
            context_parts.append(f"their name: {user_state['name']}")
        if user_state.get("commitment"):
            context_parts.append(f"they said they'd do: {user_state['commitment']}")

        context = "\n".join(context_parts) if context_parts else ""

        # Build system prompt
        if context:
            full_system = f"{self.system_prompt}\n\n---\n\nwhat you know about them:\n{context}"
        else:
            full_system = self.system_prompt

        try:
            response = llm_client.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=150,
                system=full_system,
                messages=history
            )

            result = response.content[0].text.strip()
            result = self._clean(result)

            logger.info(f"[AGENT] Response: '{result[:80]}...'")
            return result

        except Exception as e:
            logger.error(f"[AGENT] Error: {e}")
            return "what's actually going on"

    def _clean(self, text: str) -> str:
        if not text:
            return "what's actually going on"

        text = text.strip().strip('"\'')

        # Remove any continuation patterns
        for pattern in ["\nuser:", "\ngate:", "\nhuman:", "\nassistant:"]:
            if pattern in text.lower():
                text = text[:text.lower().index(pattern)]

        # Lowercase first char
        if text and text[0].isupper() and text[0] != "I":
            text = text[0].lower() + text[1:]

        return text.strip()


gate_agent = GateAgent()
