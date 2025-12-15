"""
Gate Agent - Elite Coach Architecture

System prompt + frameworks + history + user context → response
"""

import logging
from pathlib import Path
from typing import List, Dict

from core.llm import llm_client

logger = logging.getLogger(__name__)

VOICE_PROMPT_PATH = Path(__file__).parent.parent / "instances" / "base" / "gate_voice.md"
KNOWLEDGE_PATH = Path(__file__).parent.parent / "knowledge"


class GateAgent:
    """
    Elite Coach agent.

    Loads voice prompt + framework knowledge.
    Uses incremental revelation structure.
    """

    def __init__(self):
        self.system_prompt = self._load_voice_prompt()
        self.knowledge = self._load_knowledge()
        logger.info(f"[AGENT] Loaded voice prompt: {len(self.system_prompt)} chars")
        logger.info(f"[AGENT] Loaded knowledge: {len(self.knowledge)} chars")

    def _load_voice_prompt(self) -> str:
        """Load the voice prompt from file."""
        try:
            return VOICE_PROMPT_PATH.read_text(encoding="utf-8")
        except FileNotFoundError:
            logger.error(f"Voice prompt not found at {VOICE_PROMPT_PATH}")
            return "you are gate. direct, short responses. help people execute."

    def _load_knowledge(self) -> str:
        """Load all framework documents from knowledge folder."""
        if not KNOWLEDGE_PATH.exists():
            logger.warning(f"Knowledge folder not found at {KNOWLEDGE_PATH}")
            return ""

        knowledge_parts = []
        for file in sorted(KNOWLEDGE_PATH.glob("*.md")):
            try:
                content = file.read_text(encoding="utf-8")
                knowledge_parts.append(f"### {file.stem}\n\n{content}")
                logger.info(f"[AGENT] Loaded knowledge: {file.name} ({len(content)} chars)")
            except Exception as e:
                logger.error(f"[AGENT] Failed to load {file.name}: {e}")

        if knowledge_parts:
            return "## FRAMEWORKS (Your Operating Logic)\n\n" + "\n\n---\n\n".join(knowledge_parts)
        return ""

    def reload(self):
        """Reload prompt and knowledge (for development)."""
        self.system_prompt = self._load_voice_prompt()
        self.knowledge = self._load_knowledge()

    def respond(self, history: List[Dict], user_state: Dict = None) -> str:
        """
        Generate response with single LLM call.

        Args:
            history: List of {"role": "user"|"assistant", "content": str}
            user_state: State dict with name, commitment, coaching progress

        Returns:
            Response string
        """
        user_state = user_state or {}

        # Build context from state
        context_parts = []

        if user_state.get("name"):
            context_parts.append(f"their name is {user_state['name']}")

        coaching = user_state.get("coaching", {})
        if coaching.get("current_step"):
            context_parts.append(f"current step they're working on: {coaching['current_step']}")
        if coaching.get("awaiting_completion"):
            context_parts.append("you are waiting for them to complete the step before giving the next one")
        if coaching.get("completed_steps"):
            context_parts.append(f"steps they've completed: {len(coaching['completed_steps'])}")
        if coaching.get("true_constraint"):
            context_parts.append(f"the true constraint you identified: {coaching['true_constraint']}")

        context = "\n".join(context_parts) if context_parts else "first conversation - ask what they're trying to do"

        # Build full system prompt
        parts = [self.system_prompt]
        if self.knowledge:
            parts.append(self.knowledge)
        parts.append(f"## What you know about this person\n\n{context}")

        full_system = "\n\n---\n\n".join(parts)

        try:
            response = llm_client.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=300,  # Allow longer for step instructions
                system=full_system,
                messages=history
            )

            result = response.content[0].text.strip()
            result = self._enforce_voice(result)

            logger.info(f"[AGENT] Response: '{result[:100]}...'")
            return result

        except Exception as e:
            logger.error(f"[AGENT] Error: {e}")
            return "what are you trying to do?"

    def _enforce_voice(self, text: str) -> str:
        """Light cleanup to match voice."""
        if not text:
            return "what are you trying to do?"

        text = text.strip().strip('"\'')

        # Remove continuation patterns
        for pattern in ["\nuser:", "\ngate:", "\nhuman:", "\nassistant:"]:
            if pattern in text.lower():
                text = text[:text.lower().index(pattern)]

        text = text.strip()

        # Lowercase first char (unless I or name)
        if text and text[0].isupper() and text[0] != "I":
            first_word = text.split()[0] if text.split() else ""
            if first_word.lower() not in ["i", "i'm", "i'll", "i've"]:
                if not any(c.isupper() for c in first_word[1:]):  # Not a name
                    text = text[0].lower() + text[1:]

        return text


# Global instance
gate_agent = GateAgent()
