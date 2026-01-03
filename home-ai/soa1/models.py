"""Model call wrappers for Nemotron (orchestrator) and Phinance (finance specialist)."""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

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
            hidden_drains.append({
                "merchant": m,
                "avg_amount": round(avg, 2),
                "frequency": len(amts),
                "annual_cost": round(sum(amts) * 12 / (len(amts)/3), 2) # simplified annualization
            })

    return {
        "total_spent": round(total_spent, 2),
        "total_income": round(total_income, 2),
        "categories": {k: round(v, 2) for k, v in categories.items()},
        "top_merchants": top_merchants,
        "hidden_drains": hidden_drains
    }


def call_phinance(
    payload_json: str,
    validate: bool = False,
    retry_config: Optional[RetryConfig] = None,
) -> Tuple[str, int]:
    """Send pre-calculated stats to the Insight Analyst (powered by qwen2.5).

    Args:
        payload_json: JSON string with pre-calculated stats.
        validate: If True, validates response schema.
        retry_config: If provided, enables retry with feedback.

    Returns:
        Tuple of (Analysis JSON string, number of attempts)
    """

    if not isinstance(payload_json, str) or not payload_json.strip():
        raise ValueError("Phinance payload must be a JSON string")

    try:
        stats = json.loads(payload_json)
    except json.JSONDecodeError as exc:
        raise ValueError("Phinance payload must be valid JSON") from exc

    # INSIGHT ENGINE: Use qwen2.5 for superior reasoning
    endpoint = _ENDPOINTS["insights"]
    
    # INSIGHT PROMPT: Use pre-calculated Python facts
    insight_prompt = (
        f"Analyze these pre-calculated statistics and provide professional financial insights:\n"
        f"TOTAL SPENT: ${stats.get('total_spent', 0.0)}\n"
        f"CATEGORIES: {json.dumps(stats.get('categories', {}))}\n"
        f"TOP MERCHANTS: {json.dumps(stats.get('top_merchants', []))}\n"
        f"HIDDEN DRAINS: {json.dumps(stats.get('hidden_drains', []))}\n\n"
        f"Provide 3-5 specific qualitative insights and 2-3 actionable recommendations."
    )

    model_payload = _build_chat_payload(endpoint, insight_prompt)
    raw_response = _dispatch_request(endpoint, model_payload, prompt_source="phinance")
    
    try:
        # ROBUST EXTRACTION: Use helper to strip chatter/markdown
        from utils.llm_validation import extract_json_from_response
        clean_json_str = extract_json_from_response(raw_response)
        model_json = json.loads(clean_json_str)
        
        # Final output is the MERGE of Python facts and AI insights
        final_result = {**stats, **model_json}
        return json.dumps(final_result), 1
    except Exception as e:
        logger.warning(f"Failed to parse insights: {e}")
        return json.dumps({**stats, "insights": ["Qualitative insights currently unavailable."], "recommendations": []}), 1

    # Retry loop with validation feedback
    last_error: Optional[LLMValidationError] = None
    last_response: Optional[str] = None

    for attempt in range(1, retry_config.max_attempts + 1):
        # Build prompt (with feedback on retry)
        if attempt == 1:
            prompt = base_prompt
        else:
            context = RetryContext(
                attempt=attempt,
                previous_response=last_response
                if retry_config.include_previous_response
                else None,
                previous_errors=last_error.errors if last_error else [],
                feedback_prompt=last_error.feedback_prompt if last_error else None,
            )
            prompt = build_retry_prompt(base_prompt, context, retry_config)

        model_payload = _build_chat_payload(endpoint, prompt)
        response = _dispatch_request(
            endpoint, model_payload, prompt_source="phinance", attempt=1
        )
        last_response = response

        # Validate if requested
        if not validate:
            return response, attempt

        try:
            validate_phinance_response(response)
            logger.info(f"Phinance validation passed on attempt {attempt}")
            return response, attempt
        except LLMValidationError as e:
            last_error = e
            logger.warning(
                f"Phinance validation failed on attempt {attempt}/{retry_config.max_attempts}: {e.errors[:2]}"
            )
            if attempt == retry_config.max_attempts:
                raise

    # Should not reach here, but safety fallback
    raise last_error or RuntimeError("Retry loop exited unexpectedly")


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


def _build_chat_payload(endpoint: ModelEndpoint, user_content: str) -> Dict:
    # Prepare the user content. If a system_prompt exists in config, prepend it
    # as instructions to the user message to keep it additive to the Modelfile's SYSTEM.
    final_user_content = user_content
    if endpoint.system_prompt:
        final_user_content = f"### ADDITIONAL INSTRUCTIONS:\n{endpoint.system_prompt}\n\n### DATA TO ANALYZE:\n{user_content}"

    return {
        "model": endpoint.model_name,
        "messages": [{"role": "user", "content": final_user_content}],
        "options": {
            "temperature": endpoint.temperature,
            "num_predict": endpoint.max_tokens,
            "num_gpu": 99,
            "num_ctx": 32768,
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
