"""Memory v0 - Typed, auditable memory system.

Three distinct memory concepts (DO NOT MIX):
1. Boot Context - System identity, role, consent rules (injected via prompts)
2. Session Memory - Current task, batch_id, pipeline stage (ephemeral)
3. User Profile Memory - Preferences, stable facts, confirmed rules (durable)

See: soa_kernel_alignment_memory_consent_and_agent_awareness.md Section 2
"""

from .client import MemoryClient
from .memory_manager import MemoryManager, MemoryType, MemoryProposal
from .session_memory import SessionMemory

__all__ = [
    "MemoryClient",
    "MemoryManager",
    "MemoryType",
    "MemoryProposal",
    "SessionMemory",
]
