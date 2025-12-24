"""Intent parsing and consent extraction from user text."""

from __future__ import annotations

from typing import Optional

from orchestrator import UserIntent


def infer_intent_from_text(text: str) -> Optional[UserIntent]:
    """Conservative inference of user intent from free-form input."""

    normalized = text.strip().lower()
    if not normalized:
        return None

    if any(kw in normalized for kw in ["summary", "summarize", "recap", "overview"]):
        return UserIntent.SUMMARY

    if any(
        kw in normalized
        for kw in [
            "extract",
            "key info",
            "deadline",
            "due date",
            "date",
            "amount",
            "address",
        ]
    ):
        return UserIntent.EXTRACTION

    if any(kw in normalized for kw in ["action", "todo", "task", "step"]):
        return UserIntent.ACTION_ITEMS

    if any(
        kw in normalized
        for kw in [
            "finance",
            "spending",
            "budget",
            "phinance",
            "analysis",
            "categorize",
            "breakdown",
        ]
    ):
        return UserIntent.SPECIALIST_ANALYSIS

    if any(
        kw in normalized for kw in ["question", "what", "when", "where", "why", "how"]
    ):
        return UserIntent.QUESTION_ONLY

    return None


def extract_confirmation(text: str, pending_request: Optional[str]) -> bool:
    """Extract explicit confirmation only if a pending request context exists."""

    if not pending_request:
        return False

    normalized = text.strip().lower()
    confirmations = {
        "yes",
        "sure",
        "please",
        "go ahead",
        "do it",
        "confirm",
        "ok",
        "okay",
    }
    return normalized in confirmations
