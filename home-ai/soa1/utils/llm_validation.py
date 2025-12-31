"""
LLM Response Validation - Pydantic schemas and retry infrastructure for phinance outputs.

This module provides:
1. Pydantic models for strict validation of phinance LLM responses
2. Retry infrastructure with feedback loop (base setup, not wired by default)
3. Validation helpers that return clean data or raise descriptive errors

Usage:
    from utils.llm_validation import validate_transactions, validate_analysis

    # Validate raw LLM response
    try:
        validated = validate_transactions(raw_json_string)
    except LLMValidationError as e:
        # e.errors contains list of validation failures
        # e.feedback_prompt contains suggested retry prompt
        pass
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field, field_validator, model_validator


# =============================================================================
# Custom Exceptions
# =============================================================================


class LLMValidationError(Exception):
    """Raised when LLM response fails validation."""

    def __init__(
        self,
        message: str,
        errors: List[str],
        raw_response: Optional[str] = None,
        feedback_prompt: Optional[str] = None,
    ):
        super().__init__(message)
        self.errors = errors
        self.raw_response = raw_response
        self.feedback_prompt = feedback_prompt

    def __str__(self) -> str:
        error_list = "\n  - ".join(self.errors[:5])
        return f"{self.args[0]}\nErrors:\n  - {error_list}"


# =============================================================================
# Pydantic Models for Phinance Output
# =============================================================================


class TransactionCategory(str, Enum):
    """Known transaction categories."""

    GROCERIES = "groceries"
    DINING = "dining"
    TRANSPORTATION = "transportation"
    TRAVEL = "travel"
    SHOPPING = "shopping"
    HEALTHCARE = "healthcare"
    UTILITIES = "utilities"
    SUBSCRIPTIONS = "subscriptions"
    ENTERTAINMENT = "entertainment"
    SERVICES = "services"
    GAS = "gas"
    OTHER = "other"

    @classmethod
    def _missing_(cls, value: str) -> "TransactionCategory":
        """Allow unknown categories, map to OTHER."""
        if isinstance(value, str):
            normalized = value.lower().strip()
            for member in cls:
                if member.value == normalized:
                    return member
        return cls.OTHER


class Transaction(BaseModel):
    """Single transaction from phinance output."""

    date: str = Field(..., description="Transaction date (MM/DD/YYYY or YYYY-MM-DD)")
    merchant: str = Field(
        ..., min_length=1, max_length=500, description="Merchant name"
    )
    amount: float = Field(..., description="Transaction amount (positive = expense)")
    category: str = Field(default="other", description="Transaction category")
    raw_line: Optional[str] = Field(default=None, description="Original line from PDF")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    @field_validator("date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        """Ensure date is in a parseable format."""
        if not v or not v.strip():
            raise ValueError("Date cannot be empty")

        v = v.strip()

        DATE_PATTERNS = [
            r"^\d{1,2}/\d{1,2}/\d{4}$",  # MM/DD/YYYY
            r"^\d{4}-\d{2}-\d{2}$",  # YYYY-MM-DD
            r"^\d{1,2}-\d{1,2}-\d{4}$",  # DD-MM-YYYY
        ]
        if any(re.match(p, v) for p in DATE_PATTERNS):
            return v

        raise ValueError(f"Invalid date format: {v}. Expected MM/DD/YYYY or YYYY-MM-DD")

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: float) -> float:
        """Ensure amount is reasonable."""
        if v < -1_000_000 or v > 1_000_000:
            raise ValueError(f"Amount {v} is outside reasonable bounds (-1M to 1M)")
        return round(v, 2)

    @field_validator("merchant")
    @classmethod
    def validate_merchant(cls, v: str) -> str:
        """Clean merchant name."""
        if not v or not v.strip():
            raise ValueError("Merchant cannot be empty")
        return " ".join(v.split())

    @field_validator("category")
    @classmethod
    def normalize_category(cls, v: str) -> str:
        """Normalize category to lowercase."""
        if not v:
            return "other"
        return v.lower().strip()


class TransactionsResponse(BaseModel):
    """Container for list of transactions - handles both list and dict formats."""

    transactions: List[Transaction] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def handle_raw_list(cls, data: Any) -> Dict[str, Any]:
        """Handle case where LLM returns bare list instead of {"transactions": [...]}."""
        if isinstance(data, list):
            return {"transactions": data}
        return data

    def __len__(self) -> int:
        return len(self.transactions)


class MerchantTotal(BaseModel):
    """Merchant with total spending."""

    name: str = Field(..., min_length=1)
    total: float = Field(..., ge=0)

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        return " ".join(v.split())[:100]


class DateRange(BaseModel):
    """Date range for analysis."""

    start: Optional[str] = None
    end: Optional[str] = None


class AnalysisResponse(BaseModel):
    """Phinance analysis output."""

    doc_id: Optional[str] = None
    currency: str = Field(default="USD")
    transaction_count: int = Field(default=0, ge=0)
    total_spent: float = Field(default=0.0)
    total_income: Optional[float] = Field(default=0.0)
    by_category: Dict[str, float] = Field(default_factory=dict)
    top_merchants: List[Union[MerchantTotal, str, Dict[str, Any]]] = Field(
        default_factory=list
    )
    date_range: Optional[DateRange] = None
    insights: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    potential_savings: Optional[float] = Field(default=0.0, ge=0)

    @field_validator("total_spent")
    @classmethod
    def validate_total_spent(cls, v: float) -> float:
        if v < 0:
            return abs(v)
        return round(v, 2)

    @field_validator("by_category", mode="before")
    @classmethod
    def normalize_categories(cls, v: Any) -> Dict[str, float]:
        if not isinstance(v, dict):
            return {}
        return {k.lower().strip(): round(float(val), 2) for k, val in v.items()}

    @field_validator("top_merchants", mode="before")
    @classmethod
    def normalize_merchants(cls, v: Any) -> List[Dict[str, Any]]:
        """Handle various merchant formats."""
        if not isinstance(v, list):
            return []

        result = []
        for item in v:
            if isinstance(item, str):
                result.append({"name": item, "total": 0.0})
            elif isinstance(item, dict):
                result.append(item)
        return result

    @field_validator("insights", "recommendations", mode="before")
    @classmethod
    def ensure_list(cls, v: Any) -> List[str]:
        """Handle string or list of strings."""
        if isinstance(v, str):
            return [s.strip() for s in v.split("\n") if s.strip()]
        if isinstance(v, list):
            return [str(s).strip() for s in v if s]
        return []


# =============================================================================
# JSON Extraction Helpers
# =============================================================================


def _extract_pydantic_errors(exc: Exception) -> List[str]:
    """Extract error messages from Pydantic validation exception."""
    errors = []
    if hasattr(exc, "errors"):
        for err in exc.errors():
            loc = ".".join(str(x) for x in err.get("loc", []))
            msg = err.get("msg", str(err))
            errors.append(f"{loc}: {msg}")
    else:
        errors = [str(exc)]
    return errors


def extract_json_from_response(raw: str) -> str:
    """
    Extract JSON from LLM response that may contain markdown code blocks or prose.

    Handles:
    - ```json ... ```
    - ``` ... ```
    - Raw JSON
    - JSON embedded in prose
    """
    if not raw or not raw.strip():
        raise LLMValidationError(
            "Empty response from LLM",
            errors=["Response is empty or whitespace only"],
            raw_response=raw,
            feedback_prompt="Your previous response was empty. Please provide a valid JSON response.",
        )

    raw = raw.strip()

    CODE_BLOCK_PATTERN = re.compile(r"```(?:json)?\s*([\s\S]*?)```")
    code_block_match = CODE_BLOCK_PATTERN.search(raw)
    if code_block_match:
        return code_block_match.group(1).strip()

    if raw.startswith("[") or raw.startswith("{"):
        return raw

    JSON_OBJECT_PATTERN = re.compile(r"(\[[\s\S]*\]|\{[\s\S]*\})")
    json_match = JSON_OBJECT_PATTERN.search(raw)
    if json_match:
        return json_match.group(1)

    raise LLMValidationError(
        "No JSON found in LLM response",
        errors=["Response does not contain valid JSON structure"],
        raw_response=raw[:500],
        feedback_prompt=(
            "Your previous response did not contain valid JSON. "
            "Please respond with ONLY a JSON object or array, no explanatory text."
        ),
    )


# =============================================================================
# Validation Functions
# =============================================================================


def validate_transactions(
    raw_response: str,
) -> Tuple[TransactionsResponse, List[str]]:
    """
    Validate and parse transactions from LLM response.

    Returns:
        Tuple of (validated TransactionsResponse, list of warnings)

    Raises:
        LLMValidationError: If response is invalid and cannot be parsed
    """
    warnings: List[str] = []

    try:
        json_str = extract_json_from_response(raw_response)
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise LLMValidationError(
            "Invalid JSON in LLM response",
            errors=[f"JSON parse error: {e}"],
            raw_response=raw_response[:500],
            feedback_prompt=(
                f"Your previous response contained invalid JSON: {e}. "
                "Please respond with valid JSON only."
            ),
        )

    try:
        validated = TransactionsResponse.model_validate(data)
    except Exception as e:
        errors = _extract_pydantic_errors(e)

        raise LLMValidationError(
            "Transaction validation failed",
            errors=errors,
            raw_response=raw_response[:500],
            feedback_prompt=(
                "Your previous response had validation errors:\n"
                + "\n".join(f"- {e}" for e in errors[:3])
                + "\n\nPlease fix these issues and respond with valid JSON."
            ),
        )

    if len(validated.transactions) == 0:
        warnings.append("No transactions found in response")

    return validated, warnings


def validate_analysis(raw_response: str) -> Tuple[AnalysisResponse, List[str]]:
    """
    Validate and parse analysis from LLM response.

    Returns:
        Tuple of (validated AnalysisResponse, list of warnings)

    Raises:
        LLMValidationError: If response is invalid and cannot be parsed
    """
    warnings: List[str] = []

    try:
        json_str = extract_json_from_response(raw_response)
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise LLMValidationError(
            "Invalid JSON in LLM response",
            errors=[f"JSON parse error: {e}"],
            raw_response=raw_response[:500],
            feedback_prompt=(
                f"Your previous response contained invalid JSON: {e}. "
                "Please respond with valid JSON only."
            ),
        )

    try:
        validated = AnalysisResponse.model_validate(data)
    except Exception as e:
        errors = []
        if hasattr(e, "errors"):
            for err in e.errors():
                loc = ".".join(str(x) for x in err.get("loc", []))
                msg = err.get("msg", str(err))
                errors.append(f"{loc}: {msg}")
        else:
            errors = [str(e)]

        raise LLMValidationError(
            "Analysis validation failed",
            errors=errors,
            raw_response=raw_response[:500],
            feedback_prompt=(
                "Your previous response had validation errors:\n"
                + "\n".join(f"- {e}" for e in errors[:3])
                + "\n\nPlease fix these issues and respond with valid JSON."
            ),
        )

    if validated.transaction_count > 0 and validated.total_spent == 0:
        warnings.append("transaction_count > 0 but total_spent is 0")

    if validated.by_category:
        category_sum = sum(validated.by_category.values())
        if abs(category_sum - validated.total_spent) > 1.0:
            warnings.append(
                f"by_category sum ({category_sum:.2f}) != total_spent ({validated.total_spent:.2f})"
            )

    return validated, warnings


# =============================================================================
# Retry Infrastructure (Base Setup)
# =============================================================================


@dataclass
class RetryConfig:
    """Configuration for LLM retry behavior."""

    max_attempts: int = 3
    include_previous_response: bool = True
    include_error_feedback: bool = True


@dataclass
class RetryContext:
    """Context for a retry attempt."""

    attempt: int
    previous_response: Optional[str] = None
    previous_errors: List[str] = field(default_factory=list)
    feedback_prompt: Optional[str] = None


def build_retry_prompt(
    original_prompt: str,
    context: RetryContext,
    config: RetryConfig,
) -> str:
    """
    Build a retry prompt that includes feedback about what went wrong.

    This is the BASE infrastructure - not wired into call_phinance yet.
    To enable, integrate with models.py call flow.
    """
    parts = [original_prompt]

    if config.include_error_feedback and context.feedback_prompt:
        parts.append("\n\n--- CORRECTION REQUIRED ---")
        parts.append(context.feedback_prompt)

    if config.include_previous_response and context.previous_response:
        truncated = context.previous_response[:1000]
        parts.append(f"\n\nYour previous (invalid) response was:\n{truncated}")

    parts.append(f"\n\n(Attempt {context.attempt} of {config.max_attempts})")

    return "\n".join(parts)


# =============================================================================
# Convenience Functions
# =============================================================================


def validate_and_convert_transactions(raw: str) -> Dict[str, Any]:
    """
    Validate transactions and return as dict (for JSON serialization).

    Raises LLMValidationError on failure.
    """
    validated, warnings = validate_transactions(raw)
    result = validated.model_dump()
    if warnings:
        result["_warnings"] = warnings
    return result


def validate_and_convert_analysis(raw: str) -> Dict[str, Any]:
    """
    Validate analysis and return as dict (for JSON serialization).

    Raises LLMValidationError on failure.
    """
    validated, warnings = validate_analysis(raw)
    result = validated.model_dump()
    if warnings:
        result["_warnings"] = warnings
    return result


def is_valid_transactions(raw: str) -> bool:
    """Quick check if transactions response is valid."""
    try:
        validate_transactions(raw)
        return True
    except LLMValidationError:
        return False


def is_valid_analysis(raw: str) -> bool:
    """Quick check if analysis response is valid."""
    try:
        validate_analysis(raw)
        return True
    except LLMValidationError:
        return False
