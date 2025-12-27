"""Core orchestration and consent enforcement for the Daily Home Assistant.

Mandated by IMPLEMENTATION_GUIDE.md and FILE_CHECKLISTS.md.
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class ConversationState(enum.Enum):
    IDLE = enum.auto()
    FILES_RECEIVED = enum.auto()
    READING_STRUCTURE = enum.auto()
    WAITING_INTENT = enum.auto()
    INTENT_CONFIRMED = enum.auto()
    SPECIALIST_RUNNING = enum.auto()
    READY_TO_PRESENT = enum.auto()
    WAITING_FORMAT_SELECTION = enum.auto()


class UserIntent(enum.Enum):
    QUESTION_ONLY = enum.auto()
    SUMMARY = enum.auto()
    EXTRACTION = enum.auto()
    ACTION_ITEMS = enum.auto()
    SPECIALIST_ANALYSIS = enum.auto()


@dataclass
class ConsentState:
    user_action_confirmed: bool = False
    confirmed_intent: Optional[UserIntent] = None
    confirmed_specialists: Set[str] = field(default_factory=set)
    last_updated: Optional[datetime] = None

    def record_specialist_consent(self, specialist: str, intent: UserIntent) -> None:
        self.user_action_confirmed = True
        self.confirmed_intent = intent
        self.confirmed_specialists.add(specialist)
        self.last_updated = datetime.utcnow()


class Orchestrator:
    def __init__(self) -> None:
        self.state: ConversationState = ConversationState.IDLE
        self.consent = ConsentState()
        self.pending_specialist: Optional[str] = None
        self.pending_intent_offer: Optional[UserIntent] = None
        self._recent_files: List[Path] = []

    def handle_upload(self, files: List[Path]) -> List[Dict]:
        if not files:
            return [
                self.emit_user_message(
                    "ERROR",
                    {
                        "text": "I didn't detect any files. Please try uploading again.",
                    },
                )
            ]

        self._recent_files = files
        self.state = ConversationState.WAITING_INTENT
        self.pending_specialist = None
        self.pending_intent_offer = None
        logger.debug("Files received: %s", [f.name for f in files])

        return [
            self.emit_user_message(
                "ACK",
                {
                    "text": (
                        "I've received files and I'm reading their structure.\n\n"
                        "You can:\n"
                        "• ask a specific question\n"
                        "• get a quick summary\n"
                        "• extract key information or deadlines\n"
                        "• request deeper analysis (if relevant)\n\n"
                        "You can also just ask your question directly.\n"
                        "Nothing happens unless you say so."
                    )
                },
            ),
            self._intent_options_message(),
        ]

    def handle_user_message(self, text: str) -> List[Dict]:
        text_normalized = text.strip().lower()
        if not text_normalized:
            return [
                self.emit_user_message(
                    "WAITING",
                    {
                        "text": "I'm ready whenever you are. Nothing has been processed beyond basic reading."
                    },
                )
            ]

        messages: List[Dict] = []

        if self.pending_intent_offer:
            if self._text_confirms_request(text_normalized):
                intent = self.pending_intent_offer
                specialist = self.pending_specialist

                if intent == UserIntent.SPECIALIST_ANALYSIS and specialist:
                    self._grant_specialist_consent()
                    msg = f"Confirmed. If you like, I can involve the {specialist.title()} specialist now."
                else:
                    self.consent.user_action_confirmed = True
                    self.consent.confirmed_intent = intent
                    self.consent.last_updated = datetime.utcnow()
                    msg = f"Confirmed. If you like, I can prepare a {intent.name.lower()} for you now."

                messages.append(
                    self.emit_user_message(
                        "CONSENT_CONFIRMED",
                        {
                            "text": msg,
                            "intent": intent.name,
                            "specialist": specialist,
                        },
                    )
                )
                self.pending_intent_offer = None
                self.pending_specialist = None
                self.state = ConversationState.INTENT_CONFIRMED
                return messages
            elif self._text_denies_request(text_normalized):
                messages.append(
                    self.emit_user_message(
                        "CONSENT_DENIED",
                        {
                            "text": "No problem. Nothing happens unless you say so. I'll keep things here unless you change your mind.",
                        },
                    )
                )
                self.pending_intent_offer = None
                self.pending_specialist = None
                self.consent.user_action_confirmed = False
                self.state = ConversationState.WAITING_INTENT
                return messages
            else:
                messages.append(
                    self.emit_user_message(
                        "CLARIFY",
                        {
                            "text": "I've received your message, but I'm waiting for your confirmation. Do you want me to proceed with the requested action? You can say yes or no.",
                        },
                    )
                )
                return messages

        is_q = self._is_interrogative(text_normalized)
        inferred_intent = self._infer_intent(text_normalized)

        if is_q or inferred_intent == UserIntent.QUESTION_ONLY:
            self.consent.user_action_confirmed = False
            self.consent.confirmed_intent = UserIntent.QUESTION_ONLY
            self.state = ConversationState.INTENT_CONFIRMED
            messages.append(
                self.emit_user_message(
                    "QUESTION_REPLY",
                    {
                        "text": "Thanks. Let me know specifics you need, or ask about anything in the uploaded files.",
                        "intent": UserIntent.QUESTION_ONLY.name,
                    },
                )
            )
            return messages

        if inferred_intent:
            self.pending_intent_offer = inferred_intent
            if inferred_intent == UserIntent.SPECIALIST_ANALYSIS:
                self.pending_specialist = "phinance"
                offer_text = "If you like, I can involve the finance specialist for deeper insights. Do you want me to proceed?"
            else:
                offer_text = f"If you like, I can prepare a {inferred_intent.name.lower()} for you. Do you want me to proceed?"

            messages.append(
                self.emit_user_message(
                    "CONSENT_REQUEST",
                    {
                        "text": offer_text,
                        "intent": inferred_intent.name,
                    },
                )
            )
            self.state = ConversationState.WAITING_INTENT
            return messages

        self.consent.user_action_confirmed = False
        self.consent.confirmed_intent = UserIntent.QUESTION_ONLY
        self.state = ConversationState.INTENT_CONFIRMED
        messages.append(
            self.emit_user_message(
                "QUESTION_REPLY",
                {
                    "text": "If you like, I can answer your questions about these files. Let me know what you need.",
                    "intent": UserIntent.QUESTION_ONLY.name,
                },
            )
        )
        return messages

    def emit_user_message(self, kind: str, payload: Dict) -> Dict:
        return {"type": kind, **payload}

    def can_invoke_specialist(self, name: str) -> bool:
        allowed = (
            self.consent.user_action_confirmed
            and name in self.consent.confirmed_specialists
        )
        logger.debug("Specialist %s allowed=%s", name, allowed)
        return allowed

    def require_consent(self, name: str) -> None:
        if not self.can_invoke_specialist(name):
            logger.warning("Blocked specialist call without consent: %s", name)
            raise PermissionError(f"Consent missing for specialist: {name}")

    def _intent_options_message(self) -> Dict:
        options = [
            {"label": "Ask a question", "intent": UserIntent.QUESTION_ONLY.name},
            {"label": "Quick summary", "intent": UserIntent.SUMMARY.name},
            {"label": "Extract key info", "intent": UserIntent.EXTRACTION.name},
            {"label": "List action items", "intent": UserIntent.ACTION_ITEMS.name},
            {
                "label": "Finance specialist",
                "intent": UserIntent.SPECIALIST_ANALYSIS.name,
            },
        ]
        return self.emit_user_message(
            "INTENT_OPTIONS",
            {"options": options},
        )

    @staticmethod
    def _text_confirms_request(text: str) -> bool:
        confirmations = {
            "yes",
            "sure",
            "please do",
            "do it",
            "confirm",
            "proceed",
            "ok",
            "okay",
        }
        return text in confirmations

    @staticmethod
    def _text_denies_request(text: str) -> bool:
        denials = {"no", "not now", "don't", "do not", "stop", "cancel"}
        return text in denials

    def _grant_specialist_consent(self) -> None:
        if not self.pending_specialist or not self.pending_intent_offer:
            logger.debug("Consent grant attempted without pending specialist")
            return
        self.consent.record_specialist_consent(
            self.pending_specialist, self.pending_intent_offer
        )

    @staticmethod
    def _is_interrogative(text: str) -> bool:
        interrogatives = {
            "what",
            "when",
            "where",
            "why",
            "how",
            "who",
            "which",
            "can",
            "could",
            "is",
            "are",
            "do",
            "does",
            "will",
            "would",
            "should",
            "may",
            "might",
        }
        words = text.split()
        if not words:
            return False
        return words[0] in interrogatives or text.endswith("?")

    @staticmethod
    def _infer_intent(text: str) -> Optional[UserIntent]:
        if any(keyword in text for keyword in ["summary", "summarize", "recap"]):
            return UserIntent.SUMMARY
        if any(keyword in text for keyword in ["extract", "key info", "deadlines"]):
            return UserIntent.EXTRACTION
        if any(keyword in text for keyword in ["action", "todo", "task"]):
            return UserIntent.ACTION_ITEMS
        if any(
            keyword in text
            for keyword in ["finance", "spending", "analysis", "phinance", "budget"]
        ):
            return UserIntent.SPECIALIST_ANALYSIS
        if "question" in text:
            return UserIntent.QUESTION_ONLY
        return None
