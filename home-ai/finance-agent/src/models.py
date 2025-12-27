"""Async Ollama clients pinned to GPU 0/1 for finance-agent."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Any
import aiohttp
import yaml
import sys

_soa1_utils = Path(__file__).resolve().parents[2] / "soa1" / "utils"
if str(_soa1_utils) not in sys.path:
    sys.path.insert(0, str(_soa1_utils))

from model_logging import log_model_call

CONFIG_PATH = Path(__file__).with_name("config.yaml")
DEFAULT_MODELS = {
    "nemotron": {
        "base_url": "http://localhost:11434",
        "model_name": "NemoAgent",
        "temperature": 0.2,
        "max_tokens": 512,
        "gpu_id": 0,
    },
    "phinance": {
        "base_url": "http://localhost:11434",
        "model_name": "phinance-json",
        "temperature": 0.05,
        "max_tokens": 768,
        "gpu_id": 1,
    },
}


@dataclass
class ModelEndpoint:
    name: str
    base_url: str
    model_name: str
    temperature: float
    max_tokens: int
    gpu_id: int


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
            gpu_id=int(merged.get("gpu_id", DEFAULT_MODELS[key]["gpu_id"])),
        )
    return endpoints


_ENDPOINTS = _load_model_endpoints()


async def call_nemotron(prompt: str) -> str:
    """Send a plain-text prompt to Nemotron orchestrator model on GPU 0."""
    endpoint = _ENDPOINTS["nemotron"]
    payload = {
        "model": endpoint.model_name,
        "messages": [{"role": "user", "content": prompt}],
        "options": {
            "temperature": endpoint.temperature,
            "num_predict": endpoint.max_tokens,
            "num_gpu": 1,
            "num_thread": 1,
        },
        "stream": False,
        "keep_alive": -1,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            endpoint.base_url.rstrip("/") + "/api/chat",
            json=payload,
            timeout=aiohttp.ClientTimeout(total=180),
        ) as response:
            if response.status != 200:
                text = await response.text()
                raise RuntimeError(f"Nemotron error {response.status}: {text}")
            data = await response.json()
            try:
                return data["choices"][0]["message"]["content"].strip()
            except (KeyError, IndexError) as exc:
                raise RuntimeError(f"Unexpected Nemotron response: {data}") from exc


async def call_phinance(payload_json: str) -> str:
    """Send structured JSON (USD) payload to Phinance for finance analysis on GPU 1."""
    endpoint = _ENDPOINTS["phinance"]
    start_time = time.time()

    try:
        payload_dict = json.loads(payload_json)
    except json.JSONDecodeError as exc:
        raise ValueError("Phinance payload must be valid JSON") from exc

    payload_dict.setdefault("currency", "USD")
    sanitized = json.dumps(payload_dict)

    prompt = f"Analyze the following finance payload in USD. Respond with structured JSON.\n{sanitized}"

    model_payload = {
        "model": endpoint.model_name,
        "messages": [{"role": "user", "content": prompt}],
        "options": {
            "temperature": endpoint.temperature,
            "num_predict": endpoint.max_tokens,
            "num_gpu": 99,
            "num_thread": 1,
        },
        "stream": False,
        "keep_alive": -1,
    }

    log_model_call(
        model_name="phinance",
        resolved_model=endpoint.model_name,
        endpoint=endpoint.base_url + "/api/chat",
        prompt_source="phinance_adapter",
        prompt_type="request",
        prompt_text=prompt,
        options=model_payload.get("options"),
        status="pending",
    )

    async with aiohttp.ClientSession() as session:
        async with session.post(
            endpoint.base_url.rstrip("/") + "/api/chat",
            json=model_payload,
            timeout=aiohttp.ClientTimeout(total=180),
        ) as response:
            latency_ms = (time.time() - start_time) * 1000
            if response.status != 200:
                text = await response.text()
                log_model_call(
                    model_name="phinance",
                    resolved_model=endpoint.model_name,
                    endpoint=endpoint.base_url + "/api/chat",
                    prompt_source="phinance_adapter",
                    prompt_type="response",
                    prompt_text=prompt,
                    latency_ms=latency_ms,
                    status="error",
                    error=f"HTTP {response.status}: {text[:500]}",
                )
                raise RuntimeError(f"Phinance error {response.status}: {text}")
            data = await response.json()
            try:
                result = data["choices"][0]["message"]["content"].strip()
                log_model_call(
                    model_name="phinance",
                    resolved_model=endpoint.model_name,
                    endpoint=endpoint.base_url + "/api/chat",
                    prompt_source="phinance_adapter",
                    prompt_type="response",
                    prompt_text=prompt,
                    response_text=result,
                    latency_ms=latency_ms,
                    status="success",
                )
                return result
            except (KeyError, IndexError) as exc:
                log_model_call(
                    model_name="phinance",
                    resolved_model=endpoint.model_name,
                    endpoint=endpoint.base_url + "/api/chat",
                    prompt_source="phinance_adapter",
                    prompt_type="response",
                    prompt_text=prompt,
                    latency_ms=latency_ms,
                    status="error",
                    error=f"Unexpected response structure: {str(data)[:500]}",
                )
                raise RuntimeError(f"Unexpected Phinance response: {data}") from exc


async def call_phinance_insights(summary: Dict[str, Any]) -> str:
    endpoint = _ENDPOINTS["phinance"]
    start_time = time.time()

    prompt = f"""Analyze this spending data:

Total Spent: ${summary.get("total_spent", 0):.2f}
Transaction Count: {summary.get("transaction_count", 0)}
Date Range: {summary.get("date_range", {}).get("start", "N/A")} to {summary.get("date_range", {}).get("end", "N/A")}

Top Categories:
{_format_categories(summary.get("by_category", {}))}

Top Merchants:
{_format_merchants(summary.get("top_merchants", []))}"""

    model_payload = {
        "model": endpoint.model_name,
        "prompt": prompt,
        "format": "json",
        "options": {
            "num_gpu": 99,
            "num_thread": 1,
        },
        "stream": False,
        "keep_alive": -1,
    }

    log_model_call(
        model_name="phinance",
        resolved_model=endpoint.model_name,
        endpoint=endpoint.base_url + "/api/generate",
        prompt_source="phinance_insights",
        prompt_type="request",
        prompt_text=prompt,
        options=model_payload.get("options"),
        status="pending",
    )

    async with aiohttp.ClientSession() as session:
        async with session.post(
            endpoint.base_url.rstrip("/") + "/api/generate",
            json=model_payload,
            timeout=aiohttp.ClientTimeout(total=120),
        ) as response:
            latency_ms = (time.time() - start_time) * 1000
            if response.status != 200:
                text = await response.text()
                log_model_call(
                    model_name="phinance",
                    resolved_model=endpoint.model_name,
                    endpoint=endpoint.base_url + "/api/generate",
                    prompt_source="phinance_insights",
                    prompt_type="response",
                    prompt_text=prompt,
                    latency_ms=latency_ms,
                    status="error",
                    error=f"HTTP {response.status}: {text[:500]}",
                )
                raise RuntimeError(f"Phinance error {response.status}: {text}")
            data = await response.json()
            try:
                result = data["response"].strip()
                log_model_call(
                    model_name="phinance",
                    resolved_model=endpoint.model_name,
                    endpoint=endpoint.base_url + "/api/generate",
                    prompt_source="phinance_insights",
                    prompt_type="response",
                    prompt_text=prompt,
                    response_text=result,
                    latency_ms=latency_ms,
                    status="success",
                )
                return result
            except (KeyError, IndexError) as exc:
                log_model_call(
                    model_name="phinance",
                    resolved_model=endpoint.model_name,
                    endpoint=endpoint.base_url + "/api/generate",
                    prompt_source="phinance_insights",
                    prompt_type="response",
                    prompt_text=prompt,
                    latency_ms=latency_ms,
                    status="error",
                    error=f"Unexpected response structure: {str(data)[:500]}",
                )
                raise RuntimeError(f"Unexpected Phinance response: {data}") from exc


def _format_categories(by_category: Dict[str, float]) -> str:
    if not by_category:
        return "  (none)"
    lines = []
    for cat, amount in sorted(by_category.items(), key=lambda x: -x[1])[:8]:
        lines.append(f"  - {cat.title()}: ${amount:.2f}")
    return "\n".join(lines)


def _format_merchants(top_merchants: list) -> str:
    if not top_merchants:
        return "  (none)"
    lines = []
    for m in top_merchants[:5]:
        name = m.get("name", "Unknown")[:30]
        total = m.get("total", 0)
        lines.append(f"  - {name}: ${total:.2f}")
    return "\n".join(lines)
