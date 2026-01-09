"""Session Memory - Ephemeral state for current task/batch."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime


@dataclass
class SessionMemory:
    """
    Current task state - auto-expires at session end.
    Lives in orchestrator/session state, not persistent storage.
    """

    session_id: str
    batch_id: Optional[str] = None
    pipeline_stage: Optional[str] = None
    current_task: Optional[str] = None
    running_summary: List[str] = field(default_factory=list)
    last_user_goal: Optional[str] = None
    capabilities_granted: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    _data: Dict[str, Any] = field(default_factory=dict)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.updated_at = datetime.utcnow()

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def add_summary_point(self, point: str) -> None:
        self.running_summary.append(point)
        if len(self.running_summary) > 10:
            self.running_summary = self.running_summary[-10:]
        self.updated_at = datetime.utcnow()

    def grant_capability(self, capability: str) -> None:
        if capability not in self.capabilities_granted:
            self.capabilities_granted.append(capability)
            self.updated_at = datetime.utcnow()

    def has_capability(self, capability: str) -> bool:
        return capability in self.capabilities_granted

    def clear(self) -> None:
        self.batch_id = None
        self.pipeline_stage = None
        self.current_task = None
        self.running_summary.clear()
        self.last_user_goal = None
        self.capabilities_granted.clear()
        self._data.clear()
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "batch_id": self.batch_id,
            "pipeline_stage": self.pipeline_stage,
            "current_task": self.current_task,
            "running_summary": self.running_summary,
            "last_user_goal": self.last_user_goal,
            "capabilities_granted": self.capabilities_granted,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "data": self._data,
        }
