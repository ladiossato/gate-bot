"""
LLM Client Module
Handles API calls to OpenAI.
"""

import json
import logging
from typing import Optional, Dict, List, Any

from openai import OpenAI

from config import (
    OPENAI_API_KEY,
    PRIMARY_MODEL,
    EXTRACTION_MODEL,
    MAX_INPUT_TOKENS,
)

logger = logging.getLogger(__name__)


class LLMClient:
    """
    OpenAI GPT client for generating responses.
    """

    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)

    def _build_system_content(
        self,
        core_framework: str,
        security_rules: str,
        instance_persona: str,
        instance_definition: dict,
        user_context: dict,
    ) -> str:
        """
        Build system content as a single string.
        """
        # Static content - frameworks and persona
        static_content = f"""
{core_framework}

---

{security_rules}

---

## THIS INSTANCE

```json
{json.dumps(instance_definition, indent=2)}
```

---

## PERSONA

{instance_persona}
"""

        # Dynamic content - user context
        if user_context:
            context_content = f"""
---

## USER CONTEXT

**Phase**: {user_context.get('phase', 'unknown')}
**Current Step**: {user_context.get('current_step', 'none')}
**Completed Steps**: {user_context.get('completed_steps', [])}
**Days Since Last Message**: {user_context.get('days_idle', 0)}
**Pattern Flags**: {user_context.get('pattern_flags', {})}

**User Facts**:
{json.dumps(user_context.get('facts', {}), indent=2)}
"""
            return static_content + context_content

        return static_content

    def _build_messages(self, recent_messages: List[Dict]) -> List[Dict]:
        """
        Build message array for API call.
        """
        messages = []

        for msg in recent_messages:
            messages.append({
                "role": msg['role'],
                "content": msg['content']
            })

        return messages

    def generate_response(
        self,
        user_message: str,
        core_framework: str,
        security_rules: str,
        instance_persona: str,
        instance_definition: dict,
        user_context: dict,
        recent_messages: List[Dict] = None,
        model: str = None
    ) -> str:
        """
        Generate a response from the LLM.

        Args:
            user_message: Current user message
            core_framework: Shared prediction error framework
            security_rules: Shared security rules
            instance_persona: Instance-specific persona
            instance_definition: Instance config (steps, endpoint, etc.)
            user_context: Current user state and facts
            recent_messages: Recent conversation history
            model: Model to use (defaults to PRIMARY_MODEL)

        Returns:
            Generated response text
        """
        model = model or PRIMARY_MODEL

        # Build system content
        system_content = self._build_system_content(
            core_framework=core_framework,
            security_rules=security_rules,
            instance_persona=instance_persona,
            instance_definition=instance_definition,
            user_context=user_context,
        )

        # Build messages with system prompt
        messages = [{"role": "system", "content": system_content}]
        messages.extend(self._build_messages(recent_messages or []))
        messages.append({"role": "user", "content": user_message})

        try:
            response = self.client.chat.completions.create(
                model=model,
                max_tokens=1024,
                messages=messages
            )

            # Log usage
            if hasattr(response, 'usage') and response.usage:
                logger.info(
                    f"Tokens - Input: {response.usage.prompt_tokens}, "
                    f"Output: {response.usage.completion_tokens}"
                )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"LLM generation error: {e}")
            raise

    def extract_structured(
        self,
        text: str,
        extraction_prompt: str,
        schema_description: str
    ) -> Optional[Dict]:
        """
        Extract structured data from text using LLM.
        Uses faster model for efficiency.

        Args:
            text: Text to extract from
            extraction_prompt: Instructions for extraction
            schema_description: Description of expected output schema

        Returns:
            Extracted data as dict, or None if extraction failed
        """
        full_prompt = f"""
{extraction_prompt}

Text to analyze:
"{text}"

Expected output schema:
{schema_description}

Respond with valid JSON only. No markdown, no explanation.
"""

        try:
            response = self.client.chat.completions.create(
                model=EXTRACTION_MODEL,
                max_tokens=512,
                messages=[{"role": "user", "content": full_prompt}]
            )

            response_text = response.choices[0].message.content.strip()

            # Clean potential markdown formatting
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            return json.loads(response_text)

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error in extraction: {e}")
            return None
        except Exception as e:
            logger.error(f"Extraction error: {e}")
            return None

    def classify_message(self, message: str, context: dict) -> Dict:
        """
        Classify the type of user message for routing.

        Returns dict with:
            - type: completion|question|resistance|information|emotional|off_topic
            - confidence: 0.0-1.0
            - extracted_data: any relevant extracted info
        """
        logger.debug(f"[CLASSIFY] Classifying message: '{message[:50]}...' with context phase={context.get('phase')}")

        classification_prompt = f"""
Classify this user message in the context of a goal-focused coaching conversation.

Current context:
- Phase: {context.get('phase', 'unknown')}
- Current step: {context.get('current_step', 'none')}
- User's goal: {context.get('goal', 'unknown')}

User message: "{message}"

Classify into ONE of these types:
- completion: User is confirming they completed a step (signals: "done", "did it", "finished", "yes")
- question: User is asking a question (signals: "?", "how", "what", "why", "should I")
- resistance: User is expressing doubt or avoidance (signals: "but", "can't", "won't work", "what if")
- information: User is sharing facts about themselves (signals: "I am", "I have", "my", "I work")
- emotional: User is expressing feelings (signals: "feel", "frustrated", "scared", "excited")
- off_topic: User is discussing something unrelated to the goal
- onboarding_data: User is providing information relevant to onboarding (goal, current state, desired outcome)

Return JSON:
{{
    "type": "<type>",
    "confidence": <0.0-1.0>,
    "extracted_data": {{<any relevant extracted info or null>}}
}}
"""

        result = self.extract_structured(
            message,
            classification_prompt,
            '{"type": "string", "confidence": "float", "extracted_data": "object|null"}'
        )

        result = result or {"type": "unknown", "confidence": 0.0, "extracted_data": None}
        logger.info(f"[CLASSIFY] Result: type={result.get('type')}, confidence={result.get('confidence')}")
        return result


# Global client instance
llm_client = LLMClient()
