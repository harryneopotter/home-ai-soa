import requests
from typing import List, Dict, Any
import yaml
import json
import time
from tenacity import retry, wait_exponential, stop_after_attempt
import os

from utils.logger import get_logger

logger = get_logger("model")


class ModelClient:
    def __init__(self, config_path: str = "config.yaml"):
        config_path = os.path.join(os.path.dirname(__file__), config_path)
        with open(config_path, "r") as f:
            cfg = yaml.safe_load(f)

        m_cfg = cfg["model"]
        self.base_url: str = m_cfg["base_url"].rstrip("/")
        self.model_name: str = m_cfg["model_name"]
        self.temperature: float = float(m_cfg.get("temperature", 0.3))
        self.max_tokens: int = int(m_cfg.get("max_tokens", 512))
        self.num_ctx: int = int(m_cfg.get("num_ctx", 32768))
        self.verbose_logging: bool = m_cfg.get("verbose_logging", True)

        logger.info(
            f"Ollama model client initialized: {self.model_name} at {self.base_url} (ctx={self.num_ctx})"
        )

    def _truncate_for_log(self, text: str, max_len: int = 500) -> str:
        if len(text) <= max_len:
            return text
        return text[:max_len] + f"... [truncated, total {len(text)} chars]"

    def _log_request(self, system_prompt: str, conversation: List[Dict[str, str]]):
        if not self.verbose_logging:
            return

        logger.info("=" * 60)
        logger.info("LLM REQUEST")
        logger.info("=" * 60)
        logger.info(f"Model: {self.model_name}")
        logger.info(f"Temperature: {self.temperature}")
        logger.info(f"Max Tokens: {self.max_tokens}")
        logger.info("-" * 40)
        logger.info(f"SYSTEM PROMPT:\n{self._truncate_for_log(system_prompt, 1000)}")
        logger.info("-" * 40)

        for i, msg in enumerate(conversation):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            logger.info(
                f"MESSAGE [{i}] ({role}):\n{self._truncate_for_log(content, 800)}"
            )

        logger.info("=" * 60)

    def _log_response(self, content: str, latency_ms: float, usage: Dict[str, Any]):
        if not self.verbose_logging:
            return

        logger.info("=" * 60)
        logger.info("LLM RESPONSE")
        logger.info("=" * 60)
        logger.info(f"Latency: {latency_ms:.0f}ms ({latency_ms / 1000:.2f}s)")

        if usage:
            prompt_tokens = usage.get("prompt_tokens", "N/A")
            completion_tokens = usage.get("completion_tokens", "N/A")
            total_tokens = usage.get("total_tokens", "N/A")
            logger.info(
                f"Tokens: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}"
            )

        logger.info("-" * 40)
        logger.info(f"RESPONSE:\n{content}")
        logger.info("=" * 60)

    @retry(
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        stop=stop_after_attempt(3),
    )
    def chat(self, system_prompt: str, conversation: List[Dict[str, str]]) -> str:
        self._log_request(system_prompt, conversation)

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": [{"role": "system", "content": system_prompt}] + conversation,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
                "num_ctx": self.num_ctx,
                "num_gpu": 99,
            },
            "stream": False,
            "keep_alive": -1,
        }

        # Diagnostic logging for the outgoing request options and keep_alive
        logger.info(
            f"[OLLAMA-REQ] model={self.model_name} keep_alive={payload.get('keep_alive')} options={payload.get('options')}"
        )

        # Structured model call logging (non-blocking)
        try:
            from utils.model_logging import log_model_call

            log_model_call(
                model_name=self.model_name,
                resolved_model=self.model_name,
                endpoint="/api/chat",
                prompt_source="nemoagent",
                prompt_type="system+user",
                prompt_text=system_prompt
                + "\n"
                + "\n".join([m.get("content", "") for m in conversation]),
                options=payload.get("options"),
                redact=True,
            )
        except Exception:
            pass

        start_time = time.time()

        # Use Ollama native API endpoint so "keep_alive" is honored
        resp = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        latency_ms = (time.time() - start_time) * 1000

        # Robust parsing to support both Ollama native and OpenAI-compatible shapes
        content = None
        usage = {}
        try:
            # Ollama native: { "message": { "content": "..." }, "usage": {...} }
            if isinstance(data, dict) and "message" in data:
                msg = data.get("message")
                if isinstance(msg, dict):
                    content = msg.get("content", "")
                else:
                    content = str(msg)
                usage = data.get("usage", {})
            # OpenAI-compatible: { "choices": [{ "message": { "content": "..." } }], "usage": {...} }
            elif "choices" in data and isinstance(data["choices"], list):
                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
            # Fallback: try some common alternate shapes
            elif (
                "results" in data
                and isinstance(data["results"], list)
                and data["results"]
            ):
                first = data["results"][0]
                if isinstance(first, dict):
                    content = (
                        first.get("content")
                        or first.get("message")
                        or first.get("result")
                    )
                    if isinstance(content, dict):
                        # e.g. {"message": {"content": "..."}}
                        content = content.get("content")
                    usage = data.get("usage", {})

            if content is None:
                raise ValueError("Unexpected Ollama response shape")
        except Exception:
            logger.error(f"Unexpected Ollama response: {json.dumps(data, indent=2)}")
            raise

        # Optionally capture response id for observability
        resp_id = data.get("id") if isinstance(data, dict) else None
        if resp_id:
            logger.info(f"[OLLAMA-RESP-ID] {resp_id}")

        # Log the model response in structured model_calls.jsonl
        try:
            from utils.model_logging import log_model_call

            log_model_call(
                model_name=self.model_name,
                resolved_model=self.model_name,
                endpoint="/api/chat",
                prompt_source="nemoagent",
                prompt_type="response",
                prompt_text=content,
                response_id=resp_id,
                response_text=content,
                latency_ms=latency_ms,
                status="success",
                redact=True,
            )
        except Exception:
            pass

        self._log_response(content, latency_ms, usage)

        return content
