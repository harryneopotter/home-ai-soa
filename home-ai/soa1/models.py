"""Model call wrappers for Nemotron (orchestrator) and Phinance (finance specialist)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import requests
import yaml


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
        return f"{self.base_url.rstrip('/')}/v1/chat/completions"


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


def call_phinance(payload_json: str) -> str:
    """Send structured JSON (USD) payload to Phinance for finance analysis."""

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
    return _dispatch_request(endpoint, model_payload)


def _build_chat_payload(endpoint: ModelEndpoint, user_content: str) -> Dict:
    return {
        "model": endpoint.model_name,
        "messages": [{"role": "user", "content": user_content}],
        "options": {
            "temperature": endpoint.temperature,
            "num_predict": endpoint.max_tokens,
        },
        "stream": False,
    }


def _dispatch_request(endpoint: ModelEndpoint, payload: Dict) -> str:
    response = requests.post(endpoint.chat_url, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"Unexpected response from {endpoint.name}: {data}") from exc
