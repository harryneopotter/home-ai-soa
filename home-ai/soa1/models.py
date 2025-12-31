"""Model call wrappers for Nemotron (orchestrator) and Phinance (finance specialist)."""

from __future__ import annotations

import json
import logging
import os
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
}


@dataclass
class ModelEndpoint:
    name: str
    base_url: str
    model_name: str
    temperature: float
    max_tokens: int

    @property
    def chat_url(self) -> str:
        # Prefer Ollama native endpoint so keep_alive is honored when present
        return f"{self.base_url.rstrip('/')}/api/chat"


def _load_model_endpoints() -> Dict[str, ModelEndpoint]:
    models_cfg = DEFAULT_MODELS
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open("r", encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh) or {}
        models_cfg = cfg.get("models", DEFAULT_MODELS) or DEFAULT_MODELS

    endpoints: Dict[str, ModelEndpoint] = {}
    for key in ("nemotron", "phinance"):
        raw = models_cfg.get(key, {})
        merged = {**DEFAULT_MODELS[key], **raw}
        endpoints[key] = ModelEndpoint(
            name=key,
            base_url=merged["base_url"],
            model_name=merged["model_name"],
            temperature=float(
                merged.get("temperature", DEFAULT_MODELS[key]["temperature"])
            ),
            max_tokens=int(merged.get("max_tokens", DEFAULT_MODELS[key]["max_tokens"])),
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


def call_phinance(payload_json: str, validate: bool = False) -> str:
    """Send structured JSON (USD) payload to Phinance for finance analysis.

    Args:
        payload_json: JSON string with transaction data
        validate: If True, validates response schema (raises LLMValidationError on failure)

    Returns:
        Raw LLM response string (caller should validate if needed)
    """

    if not isinstance(payload_json, str) or not payload_json.strip():
        raise ValueError("Phinance payload must be a JSON string")

    try:
        payload_dict = json.loads(payload_json)
    except json.JSONDecodeError as exc:
        raise ValueError("Phinance payload must be valid JSON") from exc

    payload_dict.setdefault("currency", "USD")
    sanitized = json.dumps(payload_dict)

    endpoint = _ENDPOINTS["phinance"]
    prompt = f"Analyze the following finance payload in USD. Respond with structured JSON.\n{sanitized}"
    model_payload = _build_chat_payload(endpoint, prompt)
    response = _dispatch_request(endpoint, model_payload)

    if validate:
        validate_phinance_response(response)

    return response


def call_phinance_validated(
    payload_json: str,
) -> Tuple[TransactionsResponse, AnalysisResponse]:
    """Send payload to Phinance and return validated, typed response objects.

    This is the preferred method when you need structured data.
    Raises LLMValidationError if response doesn't match expected schema.
    """
    raw_response = call_phinance(payload_json, validate=False)

    try:
        transactions, txn_warnings = validate_transactions(raw_response)
        if txn_warnings:
            logger.warning(f"Transaction validation warnings: {txn_warnings}")
    except LLMValidationError:
        transactions = TransactionsResponse(transactions=[])

    try:
        analysis, analysis_warnings = validate_analysis(raw_response)
        if analysis_warnings:
            logger.warning(f"Analysis validation warnings: {analysis_warnings}")
    except LLMValidationError as e:
        logger.error(f"Analysis validation failed: {e}")
        raise

    return transactions, analysis


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
    return {
        "model": endpoint.model_name,
        "messages": [{"role": "user", "content": user_content}],
        "options": {
            "temperature": endpoint.temperature,
            "num_predict": endpoint.max_tokens,
            "num_gpu": 99,
            "num_ctx": 32768,
        },
        "stream": False,
        "keep_alive": -1,
    }


def _dispatch_request(endpoint: ModelEndpoint, payload: Dict) -> str:
    response = requests.post(endpoint.chat_url, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()
    try:
        if "message" in data and "content" in data["message"]:
            return data["message"]["content"].strip()
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"Unexpected response from {endpoint.name}: {data}") from exc
