"""Advisory document classification for engagement option suggestions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Optional


class DocType(Enum):
    FINANCE = "finance"
    LEGAL = "legal"
    MEDICAL = "medical"
    UTILITY = "utility"
    INSURANCE = "insurance"
    GENERAL = "general"


class ConfidenceTier(Enum):
    TIER_0 = auto()  # filename only
    TIER_1 = auto()  # headers/metadata
    TIER_2 = auto()  # structural summary / body text


@dataclass
class ClassificationResult:
    doc_type: DocType
    confidence: ConfidenceTier
    recommended_intents: List[str]

    def to_dict(self) -> Dict:
        return {
            "doc_type": self.doc_type.value,
            "confidence": self.confidence.name,
            "recommended_intents": self.recommended_intents,
        }


def classify_doc(signals: Dict) -> Dict:
    """Classify document type based on staged parser signals."""

    tier = _determine_confidence(signals)
    doc_type = _infer_doc_type(signals)
    intents = _recommended_intents(doc_type)
    result = ClassificationResult(
        doc_type=doc_type, confidence=tier, recommended_intents=intents
    )
    return result.to_dict()


def _determine_confidence(signals: Dict) -> ConfidenceTier:
    if signals.get("structural_summary") or signals.get("pages"):
        return ConfidenceTier.TIER_2
    if signals.get("header_lines") or signals.get("metadata"):
        return ConfidenceTier.TIER_1
    return ConfidenceTier.TIER_0


def _infer_doc_type(signals: Dict) -> DocType:
    filename: Optional[str] = signals.get("filename", "") or ""
    header_lines: List[str] = signals.get("header_lines", []) or []
    text_blob = "\n".join(header_lines).lower()
    filename_lower = filename.lower()

    finance_tokens = ["statement", "bank", "account", "invoice", "payment", "due"]
    legal_tokens = ["contract", "agreement", "terms", "legal"]
    medical_tokens = ["medical", "health", "clinic", "patient"]
    utility_tokens = ["utility", "electric", "water", "gas", "bill"]
    insurance_tokens = ["policy", "claim", "insurance", "premium"]

    if _contains_any(filename_lower, text_blob, finance_tokens):
        return DocType.FINANCE
    if _contains_any(filename_lower, text_blob, legal_tokens):
        return DocType.LEGAL
    if _contains_any(filename_lower, text_blob, medical_tokens):
        return DocType.MEDICAL
    if _contains_any(filename_lower, text_blob, utility_tokens):
        return DocType.UTILITY
    if _contains_any(filename_lower, text_blob, insurance_tokens):
        return DocType.INSURANCE
    return DocType.GENERAL


def _recommended_intents(doc_type: DocType) -> List[str]:
    mapping = {
        DocType.FINANCE: ["SUMMARY", "EXTRACTION", "SPECIALIST_ANALYSIS"],
        DocType.LEGAL: ["SUMMARY", "ACTION_ITEMS"],
        DocType.MEDICAL: ["SUMMARY", "EXTRACTION"],
        DocType.UTILITY: ["SUMMARY", "EXTRACTION"],
        DocType.INSURANCE: ["SUMMARY", "EXTRACTION", "ACTION_ITEMS"],
        DocType.GENERAL: ["QUESTION_ONLY", "SUMMARY"],
    }
    return mapping.get(doc_type, ["QUESTION_ONLY"])


def _contains_any(filename_text: str, header_text: str, tokens: List[str]) -> bool:
    combined = f"{filename_text} {header_text}".lower()
    return any(token in combined for token in tokens)
