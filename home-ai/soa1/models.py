"""Model call wrappers for Nemotron (orchestrator) and Phinance (finance specialist)."""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import yaml

from utils.llm_validation import (
    LLMValidationError,
    validate_transactions,
    validate_analysis,
    TransactionsResponse,
    AnalysisResponse,
    RetryConfig,
    RetryContext,
    build_retry_prompt,
)

logger = logging.getLogger(__name__)


# Dynamic system prompt for Phinance - passed at runtime, NOT baked into Modelfile
# This allows schema to vary (e.g., include drain_verifications only when drains exist)
PHINANCE_SYSTEM_PROMPT = """You are a Financial Insight Analyst providing JSON responses only.

CRITICAL RULES:
1. Output ONLY valid JSON - no markdown, no explanations, no text before or after
2. ALL keys must be in double quotes: "insights" not insights
3. insights and recommendations are arrays of STRINGS: ["text1", "text2"]
4. potential_savings is a NUMBER: 150.00 not "150.00"
5. Trust the pre-calculated numbers - do not recalculate

EXACT FORMAT:
{"insights": ["insight 1", "insight 2"], "recommendations": ["rec 1", "rec 2"], "potential_savings": 0.00}"""


CONFIG_PATH = Path(__file__).with_name("config.yaml")
DEFAULT_MODELS = {
    "nemotron": {
        "base_url": "http://localhost:11434",
        "model_name": "nemotron-8b",
        "temperature": 0.2,
        "max_tokens": 512,
    },
    "phinance": {
        "base_url": "http://localhost:11434",
        "model_name": "phinance-3.8b",
        "temperature": 0.1,
        "max_tokens": 768,
    },
    "insights": {
        "base_url": "http://localhost:11434",
        "model_name": "qwen2.5:7b-instruct",
        "temperature": 0.3,
        "max_tokens": 1024,
    },
}


@dataclass
class ModelEndpoint:
    name: str
    base_url: str
    model_name: str
    temperature: float
    max_tokens: int
    system_prompt: Optional[str] = None

    @property
    def chat_url(self) -> str:
        # Prefer Ollama native endpoint so keep_alive is honored when present
        return f"{self.base_url.rstrip('/')}/api/chat"


def _load_model_endpoints() -> Dict[str, ModelEndpoint]:
    models_cfg = DEFAULT_MODELS
    # Initialize config-based overrides
    finance_system_prompt = None

    if CONFIG_PATH.exists():
        with CONFIG_PATH.open("r", encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh) or {}

        specialists = cfg.get("specialists", {})
        finance_cfg = specialists.get("finance", {})
        if finance_cfg:
            DEFAULT_MODELS["phinance"]["model_name"] = finance_cfg.get(
                "model_name", DEFAULT_MODELS["phinance"]["model_name"]
            )
            finance_system_prompt = finance_cfg.get("system_prompt")

        orchestrator_cfg = cfg.get("orchestrator", {})
        if orchestrator_cfg:
            DEFAULT_MODELS["nemotron"]["model_name"] = orchestrator_cfg.get(
                "model_name", DEFAULT_MODELS["nemotron"]["model_name"]
            )

        models_cfg = cfg.get("models", DEFAULT_MODELS) or DEFAULT_MODELS

    endpoints: Dict[str, ModelEndpoint] = {}
    for key in ("nemotron", "phinance", "insights"):
        raw = models_cfg.get(key, {})
        merged = {**DEFAULT_MODELS[key], **raw}

        sys_prompt = finance_system_prompt if key == "phinance" else None

        endpoints[key] = ModelEndpoint(
            name=key,
            base_url=merged["base_url"],
            model_name=merged["model_name"],
            temperature=float(
                merged.get("temperature", DEFAULT_MODELS[key]["temperature"])
            ),
            max_tokens=int(merged.get("max_tokens", DEFAULT_MODELS[key]["max_tokens"])),
            system_prompt=sys_prompt,
        )
    return endpoints


_ENDPOINTS = _load_model_endpoints()


def call_nemotron(prompt: str) -> str:
    """Send a plain-text prompt to the Nemotron orchestrator model."""

    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("Nemotron prompt must be a non-empty string")
    endpoint = _ENDPOINTS["nemotron"]
    payload = _build_chat_payload(endpoint, prompt)
    return _dispatch_request(endpoint, payload)


def call_insights_model(prompt: str) -> str:
    """Call qwen2.5:7b-instruct for qualitative financial insights.

    This model generates insights, recommendations, and observations
    from pre-calculated financial data. It does NOT do arithmetic.

    Args:
        prompt: Pre-formatted insights prompt with calculated numbers

    Returns:
        JSON string with insights, recommendations, potential_savings
    """
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("Insights prompt must be a non-empty string")

    endpoint = _ENDPOINTS["insights"]
    payload = _build_chat_payload(endpoint, prompt)
    return _dispatch_request(endpoint, payload, prompt_source="insights")


def _calculate_stats(transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Deterministically calculate financial statistics from transactions."""
    total_spent = 0.0
    total_income = 0.0
    categories = {}
    merchants = {}

    for t in transactions:
        amt = float(t.get("amount", 0.0))
        if amt > 0:
            total_spent += amt
        else:
            total_income += abs(amt)

        cat = t.get("category", "Other")
        categories[cat] = categories.get(cat, 0.0) + abs(amt)

        m = t.get("merchant", "Unknown")
        merchants[m] = merchants.get(m, 0.0) + abs(amt)

    # Top 5 Merchants
    top_merchants = [
        {"merchant": k, "total": round(v, 2)}
        for k, v in sorted(merchants.items(), key=lambda x: x[1], reverse=True)[:5]
    ]

    # Hidden Drains (Under $50, 3+ times)
    drain_candidates = {}
    for t in transactions:
        m = t.get("merchant", "Unknown")
        amt = abs(float(t.get("amount", 0.0)))
        if amt < 50:
            if m not in drain_candidates:
                drain_candidates[m] = []
            drain_candidates[m].append(amt)

    hidden_drains = []
    for m, amts in drain_candidates.items():
        if len(amts) >= 3:
            avg = sum(amts) / len(amts)
            hidden_drains.append(
                {
                    "merchant": m,
                    "avg_amount": round(avg, 2),
                    "frequency": len(amts),
                    "annual_cost": round(
                        sum(amts) * 12 / (len(amts) / 3), 2
                    ),  # simplified annualization
                }
            )

    return {
        "total_spent": round(total_spent, 2),
        "total_income": round(total_income, 2),
        "categories": {k: round(v, 2) for k, v in categories.items()},
        "top_merchants": top_merchants,
        "hidden_drains": hidden_drains,
    }


def call_phinance(
    payload_json: str,
    validate: bool = False,
    retry_config: Optional[RetryConfig] = None,
) -> Tuple[str, int]:
    """Send pre-calculated stats to Phinance for qualitative insights.

    Args:
        payload_json: JSON string with pre-calculated stats from calculate_financials().
        validate: If True, validates response schema.
        retry_config: If provided, enables retry with feedback.

    Returns:
        Tuple of (Analysis JSON string, number of attempts)
    """
    from utils.financial_calculator import build_insights_prompt, calculate_financials

    if not isinstance(payload_json, str) or not payload_json.strip():
        raise ValueError("Phinance payload must be a JSON string")

    try:
        stats = json.loads(payload_json)
    except json.JSONDecodeError as exc:
        raise ValueError("Phinance payload must be valid JSON") from exc

    endpoint = _ENDPOINTS["phinance"]

    transactions = stats.get("transactions", [])
    if not transactions and "total_spent" in stats:
        user_prompt = build_insights_prompt([], stats)
    else:
        calculated_stats = calculate_financials(transactions)
        user_prompt = build_insights_prompt(transactions, calculated_stats)
        stats = calculated_stats

    model_payload = _build_chat_payload(endpoint, user_prompt)
    raw_response = _dispatch_request(endpoint, model_payload, prompt_source="phinance")

    try:
        from utils.llm_validation import extract_json_from_response

        clean_json_str = extract_json_from_response(raw_response)
        model_json = json.loads(clean_json_str)
        final_result = {**stats, **model_json}
        return json.dumps(final_result), 1
    except Exception as e:
        logger.warning(f"Failed to parse phinance response: {e}")
        return json.dumps(
            {
                **stats,
                "insights": ["Analysis currently unavailable."],
                "recommendations": [],
            }
        ), 1


def call_phinance_validated(
    payload_json: str,
    retry_config: Optional[RetryConfig] = None,
) -> Tuple[Tuple[TransactionsResponse, AnalysisResponse], int]:
    """Send payload to Phinance and return validated, typed response objects and attempts count.

    This is the preferred method when you need structured data.
    Raises LLMValidationError if response doesn't match expected schema.
    Returns:
        Tuple of (Tuple[TransactionsResponse, AnalysisResponse], number of attempts made)
    """
    if retry_config is None:
        retry_config = RetryConfig(max_attempts=3)

    raw_response, attempts = call_phinance(
        payload_json, validate=True, retry_config=retry_config
    )

    try:
        transactions, txn_warnings = validate_transactions(raw_response)
        if txn_warnings:
            logger.warning(f"Transaction validation warnings: {txn_warnings}")
    except LLMValidationError:
        transactions = TransactionsResponse(transactions=[])

    analysis, analysis_warnings = validate_analysis(raw_response)
    if analysis_warnings:
        logger.warning(f"Analysis validation warnings: {analysis_warnings}")

    return (transactions, analysis), attempts


def validate_phinance_response(raw_response: str) -> None:
    """Validate that a phinance response matches expected schema.

    Raises LLMValidationError with details if validation fails.
    """
    errors = []

    try:
        validate_analysis(raw_response)
    except LLMValidationError as e:
        errors.extend(e.errors)

    if errors:
        raise LLMValidationError(
            "Phinance response validation failed",
            errors=errors,
            raw_response=raw_response[:500],
        )


# Valid categories that match the Title Case standard in batch_processor.py
VALID_CATEGORIES = [
    "Food & Dining",
    "Groceries",
    "Gas",
    "Shopping",
    "Entertainment",
    "Travel",
    "Transportation",
    "Utilities",
    "Subscriptions",
    "Health",
    "Insurance",
    "Automotive",
    "Government & Fees",
    "Donations",
    "Housing",
    "Alcohol",
    "Transfer",
    "Education",
    "Personal Services",
    "Other",
]

CATEGORIZATION_SYSTEM_PROMPT = f"""You are a financial transaction categorization specialist.
Your task is to categorize merchant names into exactly ONE category from this list:
{", ".join(VALID_CATEGORIES)}

RULES:
1. Output ONLY valid JSON - no markdown, no explanations
2. Return a JSON object mapping each merchant name to its category
3. Use EXACT category names from the list above (Title Case)
4. If uncertain, use "Other"

Example input: ["WHATABRGR #1234 DALLAS TX", "SHELL OIL", "NETFLIX.COM"]
Example output: {{"WHATABRGR #1234 DALLAS TX": "Food & Dining", "SHELL OIL": "Gas", "NETFLIX.COM": "Subscriptions"}}"""


def categorize_merchants_llm(merchants: List[str]) -> Dict[str, str]:
    """Batch categorize unknown merchants using Phinance LLM.

    Args:
        merchants: List of unique merchant names to categorize

    Returns:
        Dict mapping merchant name -> category (Title Case)
    """
    if not merchants:
        return {}

    unique_merchants = list(set(merchants))[:100]
    logger.info(f"LLM categorizing {len(unique_merchants)} merchants")

    merchant_list = json.dumps(unique_merchants)
    user_prompt = f'Categorize these merchants:\n{merchant_list}\n\nReturn JSON format: {{"merchant_name": "category", ...}}'

    endpoint = _ENDPOINTS["phinance"]
    payload = _build_chat_payload(
        endpoint, user_prompt, system_prompt=CATEGORIZATION_SYSTEM_PROMPT
    )

    try:
        raw_response = _dispatch_request(
            endpoint, payload, prompt_source="categorization"
        )

        from utils.llm_validation import extract_json_from_response

        clean_json = extract_json_from_response(raw_response)
        result = json.loads(clean_json)

        validated = {}
        category_aliases = {
            "Dining": "Food & Dining",
            "Food": "Food & Dining",
            "Restaurant": "Food & Dining",
            "Grocery": "Groceries",
            "Fuel": "Gas",
            "Gasoline": "Gas",
            "Online Shopping": "Shopping",
            "Retail": "Shopping",
            "Streaming": "Subscriptions",
            "Subscription": "Subscriptions",
            "Medical": "Health",
            "Pharmacy": "Health",
            "Car": "Automotive",
            "Auto": "Automotive",
            "Government": "Government & Fees",
            "Fees": "Government & Fees",
            "Charity": "Donations",
            "Rent": "Housing",
            "Storage": "Housing",
            "Uber": "Transportation",
            "Rideshare": "Transportation",
            "Taxi": "Transportation",
            "Airline": "Travel",
            "Hotel": "Travel",
            "Flight": "Travel",
        }

        for merchant, category in result.items():
            normalized = category.strip().title()
            if normalized in category_aliases:
                normalized = category_aliases[normalized]

            if normalized in VALID_CATEGORIES:
                validated[merchant] = normalized
            else:
                logger.warning(
                    f"LLM returned invalid category '{category}' for '{merchant}', using Other"
                )
                validated[merchant] = "Other"

        logger.info(
            f"LLM categorization complete: {len(validated)} merchants categorized"
        )
        return validated

    except Exception as e:
        logger.error(f"LLM categorization failed: {e}")
        return {}

    # Deduplicate and limit batch size
    unique_merchants = list(set(merchants))[:100]  # Cap at 100 per batch

    logger.info(f"LLM categorizing {len(unique_merchants)} merchants")

    # Build prompt
    merchant_list = json.dumps(unique_merchants)
    user_prompt = f'Categorize these merchants:\n{merchant_list}\n\nReturn JSON format: {{"merchant_name": "category", ...}}'

    endpoint = _ENDPOINTS["phinance"]
    payload = _build_chat_payload(
        endpoint, user_prompt, system_prompt=CATEGORIZATION_SYSTEM_PROMPT
    )

    try:
        raw_response = _dispatch_request(
            endpoint, payload, prompt_source="categorization"
        )

        # Parse response
        from utils.llm_validation import extract_json_from_response

        clean_json = extract_json_from_response(raw_response)
        result = json.loads(clean_json)

        # Validate and normalize categories
        validated = {}
        for merchant, category in result.items():
            # Normalize category to Title Case and validate
            normalized = category.strip().title()
            # Map common variations
            category_map = {
                "Dining": "Food & Dining",
                "Food": "Food & Dining",
                "Restaurant": "Food & Dining",
                "Grocery": "Groceries",
                "Fuel": "Gas",
                "Gasoline": "Gas",
                "Online Shopping": "Shopping",
                "Retail": "Shopping",
                "Streaming": "Subscriptions",
                "Subscription": "Subscriptions",
                "Medical": "Health",
                "Pharmacy": "Health",
                "Car": "Automotive",
                "Auto": "Automotive",
                "Government": "Government & Fees",
                "Fees": "Government & Fees",
                "Charity": "Donations",
                "Rent": "Housing",
                "Storage": "Housing",
                "Uber": "Transportation",
                "Rideshare": "Transportation",
                "Taxi": "Transportation",
                "Airline": "Travel",
                "Hotel": "Travel",
                "Flight": "Travel",
            }
            if normalized in category_map:
                normalized = category_map[normalized]

            if normalized in VALID_CATEGORIES:
                validated[merchant] = normalized
            else:
                logger.warning(
                    f"LLM returned invalid category '{category}' for '{merchant}', using Other"
                )
                validated[merchant] = "Other"

        logger.info(
            f"LLM categorization complete: {len(validated)} merchants categorized"
        )
        return validated

    except Exception as e:
        logger.error(f"LLM categorization failed: {e}")
        # Return empty dict - caller will use "Other" for these merchants
        return {}


def _build_chat_payload(
    endpoint: ModelEndpoint, user_content: str, system_prompt: Optional[str] = None
) -> Dict:
    messages = []

    effective_system = system_prompt or endpoint.system_prompt
    if effective_system:
        messages.append({"role": "system", "content": effective_system})

    messages.append({"role": "user", "content": user_content})

    return {
        "model": endpoint.model_name,
        "messages": messages,
        "options": {
            "temperature": endpoint.temperature,
            "num_predict": endpoint.max_tokens,
            "num_gpu": 99,
            # DO NOT CHANGE num_ctx - 4096 is sufficient for Phinance.
            # Prompt sends aggregated summaries (~550 tokens), not raw transactions.
            # Typical total usage: ~1000 tokens. 4K provides 3K+ headroom.
            # Analyzed Jan 6, 2026: 32K was massive overkill, wasting VRAM.
            # See AGENTS.md and HARDWARE_SPECS.md for documentation.
            "num_ctx": 4096,
        },
        "stream": False,
        "keep_alive": -1,
    }


def _dispatch_request(
    endpoint: ModelEndpoint,
    payload: Dict,
    prompt_source: Optional[str] = None,
    correlation_id: Optional[str] = None,
    attempt: Optional[int] = None,
) -> str:
    """Dispatch request to model endpoint with structured logging.

    Args:
        endpoint: Model endpoint configuration
        payload: Request payload
        prompt_source: Source identifier for logging (defaults to endpoint.name)
        correlation_id: Unique ID to correlate request/response logs
        attempt: Attempt number for retry scenarios
    """
    source = prompt_source or endpoint.name
    logger.info(
        f"Dispatching request to {endpoint.chat_url} for model {endpoint.model_name}"
    )
    start_time = time.time()
    try:
        try:
            from utils.model_logging import log_model_call, generate_correlation_id

            if correlation_id is None:
                correlation_id = generate_correlation_id()

            log_model_call(
                model_name=endpoint.model_name,
                resolved_model=endpoint.model_name,
                endpoint="/api/chat",
                prompt_source=source,
                prompt_type="request",
                prompt_text=payload.get("messages", [{}])[0].get("content", ""),
                options=payload.get("options"),
                redact=True,
                correlation_id=correlation_id,
                attempt=attempt,
            )
        except Exception:
            pass

        response = requests.post(endpoint.chat_url, json=payload, timeout=60)
        if response.status_code != 200:
            logger.error(
                f"Error from {endpoint.name} ({endpoint.chat_url}): {response.status_code} {response.text}"
            )
        response.raise_for_status()
        data = response.json()

        latency_ms = (time.time() - start_time) * 1000
        content = ""
        if "message" in data and "content" in data["message"]:
            content = data["message"]["content"].strip()
        elif "choices" in data and data["choices"]:
            content = data["choices"][0]["message"]["content"].strip()

        try:
            from utils.model_logging import log_model_call

            log_model_call(
                model_name=endpoint.model_name,
                resolved_model=endpoint.model_name,
                endpoint="/api/chat",
                prompt_source=source,
                prompt_type="response",
                prompt_text=content,
                response_text=content,
                latency_ms=latency_ms,
                status="success",
                redact=True,
                correlation_id=correlation_id,
                attempt=attempt,
            )
        except Exception:
            pass

        return content
    except Exception as exc:
        latency_ms = (time.time() - start_time) * 1000
        logger.error(f"Request to {endpoint.name} failed: {exc}")
        try:
            from utils.model_logging import log_model_call

            log_model_call(
                model_name=endpoint.model_name,
                resolved_model=endpoint.model_name,
                endpoint="/api/chat",
                prompt_source=source,
                prompt_type="error",
                prompt_text=str(exc),
                latency_ms=latency_ms,
                status="error",
                error=str(exc),
                redact=True,
                correlation_id=correlation_id,
                attempt=attempt,
            )
        except Exception:
            pass
        raise
