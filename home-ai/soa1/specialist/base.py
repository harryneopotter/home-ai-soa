from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional, Set

from orchestrator import Capability


@dataclass(frozen=True)
class SpecialistContext:
    session_id: Optional[str]
    batch_id: Optional[str]
    document_context: Optional[Dict[str, Any]]
    capabilities_granted: Set[Capability]


@dataclass(frozen=True)
class SpecialistResult:
    success: bool
    response_text: str

    analysis: Optional[Dict[str, Any]] = None
    poll_for_completion: Optional[str] = None
    redirect_url: Optional[str] = None
    download_url: Optional[str] = None


class BaseSpecialist(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def display_name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def required_capabilities(self) -> Set[Capability]:
        raise NotImplementedError

    @property
    def trigger_keywords(self) -> Set[str]:
        return set()

    def can_handle(self, context: SpecialistContext) -> bool:
        return True

    @abstractmethod
    async def invoke(self, context: SpecialistContext) -> SpecialistResult:
        raise NotImplementedError
