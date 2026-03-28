import asyncio
import importlib
import logging
import os
from pathlib import Path
from typing import Dict, List

from .base import BaseSpecialist

logger = logging.getLogger(__name__)


class SpecialistRegistry:
    def __init__(self) -> None:
        self._specialists: Dict[str, BaseSpecialist] = {}

    async def discover(self) -> None:
        base = Path(__file__).resolve().parent.parent / "specialists"
        if not base.exists():
            logger.warning(
                "specialists/ directory not found; no specialists registered"
            )
            return
        for item in base.iterdir():
            if item.is_dir() and (item / "__init__.py").exists():
                name = item.name
                try:
                    mod = importlib.import_module(f"specialists.{name}")
                    cls = getattr(mod, "SPECIALIST_CLASS")
                    inst = cls()
                    if not isinstance(inst, BaseSpecialist):
                        raise TypeError("SPECIALIST_CLASS must inherit BaseSpecialist")
                    self.register(inst)
                    logger.info("Registered specialist: %s", inst.name)
                except Exception as e:
                    logger.exception("Failed to load specialist %s: %s", name, e)

    def register(self, specialist: BaseSpecialist) -> None:
        self._specialists[specialist.name] = specialist

    def get(self, name: str) -> BaseSpecialist:
        return self._specialists[name]

    def list(self) -> List[str]:
        return list(self._specialists.keys())

    def __contains__(self, name: str) -> bool:
        return name in self._specialists
