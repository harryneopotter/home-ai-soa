import requests
from typing import List, Dict, Any
import yaml
from tenacity import retry, wait_exponential, stop_after_attempt
import os, pathlib

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

        logger.info(
            f"Ollama model client initialized: {self.model_name} at {self.base_url}"
        )

    @retry(wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
           stop=stop_after_attempt(3))
    def chat(self, system_prompt: str,
             conversation: List[Dict[str, str]]) -> str:
        """
        conversation: list of {"role": "user"/"assistant", "content": str}
        """
        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": [{"role": "system", "content": system_prompt}]
            + conversation,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            },
            "stream": False,
        }

        # Using Ollama's OpenAI-compatible endpoint
        resp = requests.post(
            f"{self.base_url}/v1/chat/completions", json=payload, timeout=60
        )
        resp.raise_for_status()
        data = resp.json()

        try:
            content = data["choices"][0]["message"]["content"]
        except Exception:
            logger.error(f"Unexpected Ollama response: {data}")
            raise

        logger.info("Model response received")
        return content

