"""
Chat Intent Router - Parse creator messages and route to workflow actions
Detects intents like "revise beat 3", "change audio mode", etc.
Maps to stage invocations with parameters.
"""
from typing import Optional, Dict, Any, Tuple
from enum import Enum
import re


class ChatIntent(str, Enum):
    REVISE_SCRIPT_BEAT = "revise_script_beat"
    REGENERATE_SCRIPT = "regenerate_script"
    REGENERATE_STORYBOARD = "regenerate_storyboard"
    CHANGE_AUDIO_MODE = "change_audio_mode"
    CHECK_COMPLIANCE = "check_compliance"
    QUERY_STATUS = "query_status"
    APPROVE_COMPLIANCE = "approve_compliance"
    CLARIFY = "clarify"


class ChatIntentRouter:
    """
    Simple intent router - detects user intent and maps to actions.
    Minimal implementation - no LLM required for basic intents.
    """

    # Pattern-based intent detection
    INTENT_PATTERNS = {
        ChatIntent.REVISE_SCRIPT_BEAT: [
            r"(?:beat|scene|line)\s+(\d+)",
            r"(?:change|revise|redo|fix)\s+(?:beat|scene)",
            r"(?:make|more|less)\s+(?:dramatic|funny|engaging)",
        ],
        ChatIntent.REGENERATE_SCRIPT: [
            r"regenerate.*script",
            r"redo.*script",
            r"rewrite.*script",
            r"start.*over",
        ],
        ChatIntent.REGENERATE_STORYBOARD: [
            r"regenerate.*storyboard",
            r"redo.*shots",
            r"different.*visual",
        ],
        ChatIntent.CHANGE_AUDIO_MODE: [
            r"(?:use|switch|change).*(?:creator|my).*voice",
            r"(?:use|switch).*ai.*voice",
            r"(?:my|creator).*voice.*(?:recording|audio)",
        ],
        ChatIntent.CHECK_COMPLIANCE: [
            r"check.*compliance",
            r"verify.*assets",
            r"compliance.*check",
        ],
        ChatIntent.QUERY_STATUS: [
            r"what.*(?:stage|status)",
            r"where.*(?:are we|at)",
            r"(?:project|workflow).*status",
            r"what.*completed",
        ],
        ChatIntent.APPROVE_COMPLIANCE: [
            r"approve",
            r"ok\b",
            r"(?:that's|that is).*(?:fine|ok|good)",
            r"proceed",
        ],
    }

    def __init__(self):
        pass

    async def route(
        self,
        message: str,
        project_data: Optional[Dict[str, Any]] = None,
    ) -> Tuple[ChatIntent, Dict[str, Any], str]:
        """
        Route a chat message to a workflow action.
        Returns: (intent, action_params, response_message)
        """

        message_lower = message.lower().strip()

        # Detect intent
        intent, confidence = self._detect_intent(message_lower)

        if confidence < 0.6 and intent != ChatIntent.CLARIFY:
            intent = ChatIntent.CLARIFY

        # Map to action
        action_params = self._intent_to_action(intent, message_lower, project_data)

        # Generate response
        response = self._generate_response(intent, action_params)

        return intent, action_params, response

    def _detect_intent(self, message: str) -> Tuple[ChatIntent, float]:
        """Detect intent from message using pattern matching"""

        best_intent = ChatIntent.CLARIFY
        best_score = 0.0

        for intent, patterns in self.INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, message, re.IGNORECASE):
                    score = 0.8  # Base confidence for pattern match
                    if score > best_score:
                        best_intent = intent
                        best_score = score

        return best_intent, best_score

    def _intent_to_action(
        self,
        intent: ChatIntent,
        message: str,
        project_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Map intent to workflow action with parameters"""

        action = {
            "type": "invoke_stage",
            "stage": None,
            "params": {},
        }

        if intent == ChatIntent.REVISE_SCRIPT_BEAT:
            # Extract beat number
            beat_match = re.search(r"beat\s+(\d+)", message, re.IGNORECASE)
            beat_id = f"beat_{int(beat_match.group(1)):03d}" if beat_match else None

            # Extract instruction
            instruction = self._extract_instruction(message)

            action["stage"] = "SCRIPT"
            action["params"] = {
                "revision_target": beat_id,
                "instruction": instruction or "Revise this beat",
            }

        elif intent == ChatIntent.REGENERATE_SCRIPT:
            action["stage"] = "SCRIPT"
            action["params"] = {"regenerate": True}

        elif intent == ChatIntent.REGENERATE_STORYBOARD:
            action["stage"] = "STORYBOARD"
            action["params"] = {}

        elif intent == ChatIntent.CHANGE_AUDIO_MODE:
            action["type"] = "update_config"
            if "creator" in message or "my voice" in message:
                action["params"] = {"audio_mode": "CREATOR_VOICE"}
            elif "ai" in message:
                action["params"] = {"audio_mode": "AI_VOICE"}

        elif intent == ChatIntent.CHECK_COMPLIANCE:
            action["type"] = "run_compliance"
            action["params"] = {}

        elif intent == ChatIntent.QUERY_STATUS:
            action["type"] = "return_info"
            action["params"] = {"info_type": "status"}

        elif intent == ChatIntent.APPROVE_COMPLIANCE:
            action["type"] = "approve_checkpoint"
            action["params"] = {"auto_approve": True}

        else:  # CLARIFY
            action["type"] = "clarify"
            action["params"] = {}

        return action

    def _extract_instruction(self, message: str) -> Optional[str]:
        """Extract the instruction/direction from the message"""

        # Look for phrases after key words
        patterns = [
            r"(?:make|use|try|with)\s+(.{10,100}?)(?:\.|$)",
            r"more\s+(.{5,50}?)\b",
            r"less\s+(.{5,50}?)\b",
        ]

        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    def _generate_response(
        self,
        intent: ChatIntent,
        action_params: Dict[str, Any],
    ) -> str:
        """Generate a natural response to the user"""

        responses = {
            ChatIntent.REVISE_SCRIPT_BEAT: f"I'll revise {action_params['params'].get('revision_target', 'that beat')} with: '{action_params['params'].get('instruction', 'your changes')}'. This will take about 30 seconds.",
            ChatIntent.REGENERATE_SCRIPT: "I'll regenerate the entire script from scratch. This will take about 60 seconds.",
            ChatIntent.REGENERATE_STORYBOARD: "I'll regenerate the storyboard. This will take 1-2 minutes.",
            ChatIntent.CHANGE_AUDIO_MODE: f"Switching to {action_params['params'].get('audio_mode', 'audio mode')}. I'll need the appropriate inputs.",
            ChatIntent.CHECK_COMPLIANCE: "Running compliance check on current outputs...",
            ChatIntent.QUERY_STATUS: "Here's the current project status and what we've completed so far.",
            ChatIntent.APPROVE_COMPLIANCE: "Approved! Proceeding with the next stages.",
            ChatIntent.CLARIFY: "I'm not sure what you'd like to change. Could you tell me more? For example: 'Make beat 3 more dramatic' or 'Use my voice for audio'.",
        }

        return responses.get(intent, "I'll process that request.")
