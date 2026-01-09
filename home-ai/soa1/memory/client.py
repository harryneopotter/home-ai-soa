import requests
from typing import List, Dict, Any, Optional
import yaml
from tenacity import retry, wait_exponential, stop_after_attempt
import os, pathlib

from utils.logger import get_logger

logger = get_logger("memory")


class MemoryClient:
    def __init__(self, config_path: str = "config.yaml"):
        config_path = os.path.join(os.path.dirname(__file__), config_path)
        with open(config_path, "r") as f:
            cfg = yaml.safe_load(f)

        self.base_url: str = cfg["memlayer"]["base_url"].rstrip("/")
        self.user_id: str = cfg["memlayer"]["user_id"]
        self.profile_id: str = cfg["memlayer"]["profile_id"]
        self.top_k: int = int(cfg["memlayer"].get("top_k", 5))

        logger.info(
            f"MemLayer client initialized at {self.base_url} "
            f"for user={self.user_id}, profile={self.profile_id}"
        )

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
        payload: Dict[str, Any] = {
            "user_id": self.user_id,
            "profile_id": self.profile_id,
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
        payload = {
            "user_id": self.user_id,
            "profile_id": self.profile_id,
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

