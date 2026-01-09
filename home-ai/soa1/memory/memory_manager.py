"""
Memory Manager - Kernel-controlled memory with propose/commit pattern.

Agents can only propose writes; kernel commits them after validation.
This ensures all memory writes are auditable and consent-gated.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
import json
import os

from utils.logger import get_logger

logger = get_logger("memory_manager")


class MemoryType(Enum):
    """Three distinct memory types - DO NOT MIX."""

    BOOT_CONTEXT = "boot_context"  # System identity, injected at startup
    SESSION = "session"  # Current task state, ephemeral
    USER_PROFILE = "user_profile"  # Preferences, durable


@dataclass
class MemoryProposal:
    """Agent-proposed memory write, pending kernel approval."""

    memory_type: MemoryType
    key: str
    value: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    proposed_at: datetime = field(default_factory=datetime.utcnow)
    proposed_by: str = "agent"
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory_type": self.memory_type.value,
            "key": self.key,
            "value": self.value,
            "metadata": self.metadata,
            "proposed_at": self.proposed_at.isoformat(),
            "proposed_by": self.proposed_by,
            "reason": self.reason,
        }


class MemoryManager:
    """
    Kernel-controlled memory system.

    - Agents call propose_write() to suggest memory updates
    - Kernel calls commit_write() to persist approved proposals
    - query() retrieves memories filtered by type and scope
    """

    def __init__(
        self,
        backend: Optional[Any] = None,
        audit_log_path: str = "logs/memory_audit.jsonl",
    ):
        self._backend = backend  # MemoryClient or None for local-only
        self._pending_proposals: List[MemoryProposal] = []
        self._session_memory: Dict[str, Any] = {}
        self._audit_log_path = audit_log_path

        os.makedirs(os.path.dirname(audit_log_path), exist_ok=True)
        logger.info(
            f"MemoryManager initialized (backend={'remote' if backend else 'local'})"
        )

    def propose_write(
        self,
        memory_type: MemoryType,
        key: str,
        value: Any,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryProposal:
        """
        Agent proposes a memory write. Does NOT persist immediately.
        Kernel must call commit_write() to actually store.

        Raises ValueError for BOOT_CONTEXT (read-only, not writable).
        """
        if memory_type == MemoryType.BOOT_CONTEXT:
            logger.error("BOOT_CONTEXT is read-only, cannot propose writes")
            raise ValueError("BOOT_CONTEXT is read-only and cannot be written")

        proposal = MemoryProposal(
            memory_type=memory_type,
            key=key,
            value=value,
            reason=reason,
            metadata=metadata or {},
        )
        self._pending_proposals.append(proposal)
        logger.info(f"Memory proposal: {memory_type.value}/{key} (reason: {reason})")
        return proposal

    def commit_write(
        self,
        proposal: MemoryProposal,
        approved_by: str = "kernel",
    ) -> bool:
        """
        Kernel commits an approved proposal. Auditable.
        Returns True if committed successfully.
        """
        if proposal not in self._pending_proposals:
            logger.warning(f"Attempted to commit non-pending proposal: {proposal.key}")
            return False

        self._pending_proposals.remove(proposal)

        if proposal.memory_type == MemoryType.SESSION:
            self._session_memory[proposal.key] = proposal.value
            self._audit_log("commit", proposal, approved_by, "session_store")
            return True

        elif proposal.memory_type == MemoryType.USER_PROFILE:
            if self._backend:
                try:
                    self._backend.write_memory(
                        text=json.dumps({"key": proposal.key, "value": proposal.value}),
                        metadata={
                            "memory_type": proposal.memory_type.value,
                            "key": proposal.key,
                            **proposal.metadata,
                        },
                    )
                    self._audit_log("commit", proposal, approved_by, "backend")
                    return True
                except Exception as e:
                    logger.error(f"Backend write failed: {e}")
                    self._audit_log("commit_failed", proposal, approved_by, str(e))
                    return False
            else:
                logger.warning("No backend configured for USER_PROFILE writes")
                self._audit_log("commit_skipped", proposal, approved_by, "no_backend")
                return False

        elif proposal.memory_type == MemoryType.BOOT_CONTEXT:
            logger.error("BOOT_CONTEXT is read-only, cannot commit writes")
            self._audit_log(
                "commit_rejected", proposal, approved_by, "boot_context_readonly"
            )
            return False

        return False

    def commit_all_pending(self, approved_by: str = "kernel") -> int:
        """Commit all pending proposals. Returns count of successful commits."""
        committed = 0
        for proposal in list(self._pending_proposals):
            if self.commit_write(proposal, approved_by):
                committed += 1
        return committed

    def reject_proposal(self, proposal: MemoryProposal, reason: str = "") -> None:
        """Reject a pending proposal without committing."""
        if proposal in self._pending_proposals:
            self._pending_proposals.remove(proposal)
            self._audit_log("reject", proposal, "kernel", reason)
            logger.info(f"Rejected proposal: {proposal.key} ({reason})")

    def clear_pending(self) -> int:
        """Clear all pending proposals without committing. Returns count cleared."""
        count = len(self._pending_proposals)
        self._pending_proposals.clear()
        return count

    def query(
        self,
        memory_type: MemoryType,
        key: Optional[str] = None,
        search_text: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Query memories by type. Scoped and filtered.

        - SESSION: returns from local session_memory dict
        - USER_PROFILE: searches backend if available
        - BOOT_CONTEXT: not queryable (injected via prompts)
        """
        if memory_type == MemoryType.BOOT_CONTEXT:
            logger.warning("BOOT_CONTEXT is not queryable")
            return []

        if memory_type == MemoryType.SESSION:
            if key:
                val = self._session_memory.get(key)
                return [{"key": key, "value": val}] if val is not None else []
            return [{"key": k, "value": v} for k, v in self._session_memory.items()]

        if memory_type == MemoryType.USER_PROFILE:
            if not self._backend:
                logger.warning("No backend for USER_PROFILE queries")
                return []
            if not search_text:
                logger.warning("USER_PROFILE query requires search_text")
                return []
            try:
                results = self._backend.search_memory(search_text, top_k=top_k)
                return [
                    r
                    for r in results
                    if r.get("metadata", {}).get("memory_type") == "user_profile"
                ]
            except Exception as e:
                logger.error(f"Backend search failed: {e}")
                return []

        return []

    def get_session(self, key: str, default: Any = None) -> Any:
        """Convenience method for session memory reads."""
        return self._session_memory.get(key, default)

    def set_session(self, key: str, value: Any) -> None:
        """Convenience method for direct session writes (kernel-only, no proposal needed)."""
        self._session_memory[key] = value

    def clear_session(self) -> None:
        """Clear all session memory (e.g., on session end)."""
        self._session_memory.clear()

    @property
    def pending_count(self) -> int:
        return len(self._pending_proposals)

    @property
    def pending_proposals(self) -> List[MemoryProposal]:
        return list(self._pending_proposals)

    def _audit_log(
        self,
        action: str,
        proposal: MemoryProposal,
        actor: str,
        detail: str = "",
    ) -> None:
        """Append to audit log."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "actor": actor,
            "memory_type": proposal.memory_type.value,
            "key": proposal.key,
            "detail": detail,
        }
        try:
            with open(self._audit_log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"Audit log write failed: {e}")
