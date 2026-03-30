import requests
from typing import List, Dict, Any, Optional
import yaml
from tenacity import retry, wait_exponential, stop_after_attempt
import os

from kernel import kernel

from utils.logger import get_logger

logger = get_logger("memory")


class MemoryClient:
    def __init__(self, config_path: str = "config.yaml"):
        config_path = os.path.join(os.path.dirname(__file__), config_path)
        with open(config_path, "r") as f:
            cfg = yaml.safe_load(f)

        self.base_url: str = cfg["memlayer"]["base_url"].rstrip("/")
        self.top_k: int = int(cfg["memlayer"].get("top_k", 5))

        logger.info(
            "MemLayer client initialized at %s (user from kernel context)",
            self.base_url,
        )

    def _get_context(self) -> Dict[str, str]:
        if not kernel.active_user:
            raise PermissionError("Memory access requires an active user context")
        return {"user_id": kernel.active_user.user_id, "profile_id": "main"}

    @retry(wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
           stop=stop_after_attempt(3))
    def health_check(self) -> bool:
        resp = requests.get(f"{self.base_url}/", timeout=3)
        resp.raise_for_status()
        data = resp.json()
        ok = data.get("status") == "memlayer ok"
        logger.info(f"MemLayer health: {data}")
        return ok

    @retry(wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
           stop=stop_after_attempt(3))
    def write_memory(self, text: str,
                     metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        ctx = self._get_context()
        payload: Dict[str, Any] = {
            "user_id": ctx["user_id"],
            "profile_id": ctx["profile_id"],
            "text": text,
        }
        if metadata:
            payload["metadata"] = metadata

        resp = requests.post(
            f"{self.base_url}/memory/write", json=payload, timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"Memory write result: {data}")
        return data

    @retry(wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
           stop=stop_after_attempt(3))
    def search_memory(self, query: str,
                      top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        k = top_k or self.top_k
        ctx = self._get_context()
        payload = {
            "user_id": ctx["user_id"],
            "profile_id": ctx["profile_id"],
            "query": query,
            "top_k": k,
        }
        resp = requests.post(
            f"{self.base_url}/memory/search", json=payload, timeout=10
        )
        resp.raise_for_status()
        data = resp.json()

        # Either {"results": [...]} or raw list
        if isinstance(data, dict) and "results" in data:
            results = data["results"]
        else:
            results = data

        logger.info(f"Memory search returned {len(results)} items")
        return results
