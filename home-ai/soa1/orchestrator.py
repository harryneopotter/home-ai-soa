"""Core orchestration and consent enforcement for the Daily Home Assistant.

This module implements the state machine mandated by IMPLEMENTATION_GUIDE.md and
FILE_CHECKLISTS.md. It never performs parsing or specialist work directly; it is
strictly responsible for tracking intent, gating actions, and emitting structured
messages back to the UI layer.
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
    """High-level phases for the primary assistant."""

    IDLE = enum.auto()
    FILES_RECEIVED = enum.auto()
    READING_STRUCTURE = enum.auto()
    WAITING_INTENT = enum.auto()
    INTENT_CONFIRMED = enum.auto()
    SPECIALIST_RUNNING = enum.auto()
    READY_TO_PRESENT = enum.auto()
    WAITING_FORMAT_SELECTION = enum.auto()


class UserIntent(enum.Enum):
    """Explicit user intent axis (doc type is separate)."""

    QUESTION_ONLY = enum.auto()
    SUMMARY = enum.auto()
    EXTRACTION = enum.auto()
    ACTION_ITEMS = enum.auto()
    SPECIALIST_ANALYSIS = enum.auto()


@dataclass
class ConsentState:
    """Tracks whether the user has actually granted permission."""

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
    """Primary state machine and consent gatekeeper."""

    def __init__(self) -> None:
        self.state: ConversationState = ConversationState.IDLE
        self.consent = ConsentState()
        self.pending_specialist: Optional[str] = None
        self.pending_intent_offer: Optional[UserIntent] = None
        self._recent_files: List[Path] = []

    # ------------------------------------------------------------------
    # Public interface required by FILE_CHECKLISTS.md
    # ------------------------------------------------------------------
    def handle_upload(self, files: List[Path]) -> List[Dict]:
        """Handle a batch of uploaded files (metadata-level only)."""

        if not files:
            return [
                self.emit_user_message(
                    "ERROR",
                    {
                        "text": "I didn’t detect any files. Please try uploading again.",
                    },
                )
            ]

        self._recent_files = files
        self.state = ConversationState.WAITING_INTENT
        self.pending_specialist = None
        logger.debug("Files received: %s", [f.name for f in files])

        return [
            self.emit_user_message(
                "ACK",
                {
                    "text": (
                        "I’ve received the files and I’m reading their structure.\n\n"
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
        """Process a user utterance and emit structured responses."""

        text_normalized = text.strip().lower()
        if not text_normalized:
            return [
                self.emit_user_message(
                    "WAITING",
                    {
                        "text": "I’m ready whenever you are. Nothing has been processed beyond basic reading."
                    },
                )
            ]

        messages: List[Dict] = []

        # 1. Check for confirmation to a pending consent request.
        if self.pending_specialist:
            if self._text_confirms_request(text_normalized):
                self._grant_specialist_consent()
                messages.append(
                    self.emit_user_message(
                        "CONSENT_CONFIRMED",
                        {
                            "text": f"Great. I’ll be ready to involve the {self.pending_specialist.title()} specialist when you ask.",
                            "specialist": self.pending_specialist,
                        },
                    )
                )
                self.pending_specialist = None
                self.state = ConversationState.INTENT_CONFIRMED
            elif self._text_denies_request(text_normalized):
                messages.append(
                    self.emit_user_message(
                        "CONSENT_DENIED",
                        {
                            "text": "No problem. I’ll keep things here unless you change your mind.",
                            "specialist": self.pending_specialist,
                        },
                    )
                )
                self.pending_specialist = None
                self.consent.user_action_confirmed = False
                self.consent.confirmed_specialists.clear()
                self.state = ConversationState.WAITING_INTENT
                return messages
            else:
                # Clarify that a direct yes/no tied to the request is needed.
                messages.append(
                    self.emit_user_message(
                        "CLARIFY",
                        {
                            "text": "Just to confirm, should I involve the finance specialist? You can say yes or no.",
                            "specialist": self.pending_specialist,
                        },
                    )
                )
                return messages

        # 2. No pending specialist: infer requested intent.
        inferred_intent = self._infer_intent(text_normalized)
        if inferred_intent == UserIntent.SPECIALIST_ANALYSIS:
            # Ask for explicit permission before enabling specialist use.
            self.pending_specialist = "phinance"
            self.pending_intent_offer = UserIntent.SPECIALIST_ANALYSIS
            messages.append(
                self.emit_user_message(
                    "CONSENT_REQUEST",
                    {
                        "text": "If you like, I can involve the finance specialist for deeper insights. Should I proceed?",
                        "specialist": "phinance",
                    },
                )
            )
            self.state = ConversationState.WAITING_INTENT
            return messages

        if inferred_intent is None:
            # Treat as question-only unless stated otherwise.
            inferred_intent = UserIntent.QUESTION_ONLY

        self.consent.user_action_confirmed = inferred_intent != UserIntent.QUESTION_ONLY
        if self.consent.user_action_confirmed:
            self.consent.confirmed_intent = inferred_intent
            self.consent.last_updated = datetime.utcnow()
        self.state = ConversationState.INTENT_CONFIRMED

        messages.append(
            self.emit_user_message(
                "QUESTION_REPLY",
                {
                    "text": "Thanks. Go ahead and let me know the specifics you need, or ask about anything in the uploaded files.",
                    "intent": inferred_intent.name,
                },
            )
        )
        return messages

    def emit_user_message(self, kind: str, payload: Dict) -> Dict:
        """Helper to standardize outbound messages."""

        return {"type": kind, **payload}

    def can_invoke_specialist(self, name: str) -> bool:
        """Check whether a specialist invocation is currently allowed."""

        allowed = (
            self.consent.user_action_confirmed
            and name in self.consent.confirmed_specialists
        )
        logger.debug("Specialist %s allowed=%s", name, allowed)
        return allowed

    def require_consent(self, name: str) -> None:
        """Raise if consent is missing for the requested specialist."""

        if not self.can_invoke_specialist(name):
            logger.warning("Blocked specialist call without consent: %s", name)
            raise PermissionError(f"Consent missing for specialist: {name}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
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
        confirmations = {"yes", "sure", "please do", "go ahead", "do it", "confirm"}
        return text in confirmations

    @staticmethod
    def _text_denies_request(text: str) -> bool:
        denials = {"no", "not now", "don’t", "do not", "stop"}
        return text in denials

    def _grant_specialist_consent(self) -> None:
        if not self.pending_specialist or not self.pending_intent_offer:
            logger.debug("Consent grant attempted without pending specialist")
            return
        self.consent.record_specialist_consent(
            self.pending_specialist, self.pending_intent_offer
        )

    @staticmethod
    def _infer_intent(text: str) -> Optional[UserIntent]:
        if any(keyword in text for keyword in ["summary", "summarize"]):
            return UserIntent.SUMMARY
        if any(
            keyword in text
            for keyword in ["extract", "key info", "deadlines", "due date"]
        ):
            return UserIntent.EXTRACTION
        if "action" in text:
            return UserIntent.ACTION_ITEMS
        if any(
            keyword in text
            for keyword in ["finance", "spending", "analysis", "phinance", "budget"]
        ):
            return UserIntent.SPECIALIST_ANALYSIS
        if "question" in text:
            return UserIntent.QUESTION_ONLY
        return None
