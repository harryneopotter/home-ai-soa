"""CONTROL Header System for SOA1 Orchestrator.

Replaces prose instructions with structured control blocks per
soa_kernel_alignment_memory_consent_and_agent_awareness.md Section 4.

Every chunk of data sent to the orchestrator is preceded by a CONTROL block
that specifies exactly what the orchestrator can and cannot do.

INVARIANT: invoke_specialist is ONLY allowed when stage == READY.
           If stage != READY, invoke_specialist MUST NOT appear in allowed_actions.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from orchestrator import Capability

from orchestrator import Capability


class PipelineStage(enum.Enum):
    UPLOADING = "UPLOADING"
    PDF_PARSE = "PDF_PARSE"
    NORMALIZE = "NORMALIZE"
    AGGREGATE = "AGGREGATE"
    READY = "READY"
    ANALYZING = "ANALYZING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class DataKind(enum.Enum):
    METADATA = "metadata"
    TEXT = "text"
    TABLES = "tables"
    TRANSACTIONS = "transactions"
    ANALYSIS = "analysis"


class AllowedAction(enum.Enum):
    CLASSIFY_INTENT = "classify_intent"
    ASK_QUESTIONS = "ask_questions"
    ACKNOWLEDGE_UPLOAD = "acknowledge_upload"
    OFFER_ANALYSIS = "offer_analysis"
    INVOKE_SPECIALIST = "invoke_specialist"
    PRESENT_RESULTS = "present_results"
    OFFER_OUTPUT_FORMATS = "offer_output_formats"


class ForbiddenAction(enum.Enum):
    WRITE_DB = "write_db"
    INVOKE_WITHOUT_CONSENT = "invoke_specialist_without_consent"
    FABRICATE_DATA = "fabricate_data"
    REVEAL_PARTIAL_DATA = "reveal_partial_data"
    SKIP_CONSENT = "skip_consent"


class ExpectedNext(enum.Enum):
    MORE_CHUNKS = "MORE_CHUNKS"
    STAGE_COMPLETE = "STAGE_COMPLETE"
    ASK_USER_GOAL = "ASK_USER_GOAL"
    AWAIT_ANALYSIS = "AWAIT_ANALYSIS"
    PRESENT_RESULTS = "PRESENT_RESULTS"
    AWAIT_FORMAT_SELECTION = "AWAIT_FORMAT_SELECTION"


STAGE_ALLOWED_ACTIONS = {
    PipelineStage.UPLOADING: {
        AllowedAction.ACKNOWLEDGE_UPLOAD,
        AllowedAction.ASK_QUESTIONS,
    },
    PipelineStage.PDF_PARSE: {
        AllowedAction.ACKNOWLEDGE_UPLOAD,
        AllowedAction.ASK_QUESTIONS,
    },
    PipelineStage.NORMALIZE: {
        AllowedAction.ASK_QUESTIONS,
    },
    PipelineStage.AGGREGATE: {
        AllowedAction.ASK_QUESTIONS,
    },
    PipelineStage.READY: {
        AllowedAction.CLASSIFY_INTENT,
        AllowedAction.ASK_QUESTIONS,
        AllowedAction.OFFER_ANALYSIS,
        AllowedAction.INVOKE_SPECIALIST,
    },
    PipelineStage.ANALYZING: {
        AllowedAction.ASK_QUESTIONS,
    },
    PipelineStage.COMPLETE: {
        AllowedAction.ASK_QUESTIONS,
        AllowedAction.PRESENT_RESULTS,
        AllowedAction.OFFER_OUTPUT_FORMATS,
    },
    PipelineStage.FAILED: {
        AllowedAction.ASK_QUESTIONS,
    },
}

STAGE_FORBIDDEN_ACTIONS = {
    PipelineStage.UPLOADING: {
        ForbiddenAction.INVOKE_WITHOUT_CONSENT,
        ForbiddenAction.FABRICATE_DATA,
        ForbiddenAction.REVEAL_PARTIAL_DATA,
    },
    PipelineStage.PDF_PARSE: {
        ForbiddenAction.INVOKE_WITHOUT_CONSENT,
        ForbiddenAction.FABRICATE_DATA,
        ForbiddenAction.REVEAL_PARTIAL_DATA,
    },
    PipelineStage.NORMALIZE: {
        ForbiddenAction.INVOKE_WITHOUT_CONSENT,
        ForbiddenAction.FABRICATE_DATA,
        ForbiddenAction.REVEAL_PARTIAL_DATA,
    },
    PipelineStage.AGGREGATE: {
        ForbiddenAction.INVOKE_WITHOUT_CONSENT,
        ForbiddenAction.FABRICATE_DATA,
        ForbiddenAction.REVEAL_PARTIAL_DATA,
    },
    PipelineStage.READY: {
        ForbiddenAction.FABRICATE_DATA,
        ForbiddenAction.WRITE_DB,
    },
    PipelineStage.ANALYZING: {
        ForbiddenAction.FABRICATE_DATA,
        ForbiddenAction.INVOKE_WITHOUT_CONSENT,
    },
    PipelineStage.COMPLETE: {
        ForbiddenAction.FABRICATE_DATA,
    },
    PipelineStage.FAILED: {
        ForbiddenAction.FABRICATE_DATA,
        ForbiddenAction.INVOKE_WITHOUT_CONSENT,
    },
}

STAGE_EXPECTED_NEXT = {
    PipelineStage.UPLOADING: ExpectedNext.STAGE_COMPLETE,
    PipelineStage.PDF_PARSE: ExpectedNext.STAGE_COMPLETE,
    PipelineStage.NORMALIZE: ExpectedNext.STAGE_COMPLETE,
    PipelineStage.AGGREGATE: ExpectedNext.STAGE_COMPLETE,
    PipelineStage.READY: ExpectedNext.ASK_USER_GOAL,
    PipelineStage.ANALYZING: ExpectedNext.AWAIT_ANALYSIS,
    PipelineStage.COMPLETE: ExpectedNext.AWAIT_FORMAT_SELECTION,
    PipelineStage.FAILED: ExpectedNext.ASK_USER_GOAL,
}


@dataclass
class ControlHeaderContext:
    session_id: Optional[str] = None
    batch_id: Optional[str] = None
    stage: PipelineStage = PipelineStage.UPLOADING
    data_kind: DataKind = DataKind.METADATA
    capabilities_granted: Set[Capability] = None
    transaction_count: int = 0
    file_count: int = 0
    is_partial: bool = False

    def __post_init__(self):
        if self.capabilities_granted is None:
            self.capabilities_granted = set()


def build_control_header(ctx: ControlHeaderContext) -> str:
    """Build a CONTROL header block for the given context.

    INVARIANT: invoke_specialist only appears in allowed_actions when stage == READY.
    This is enforced by the STAGE_ALLOWED_ACTIONS mapping, but we assert it here
    as a safety check.
    """
    allowed = STAGE_ALLOWED_ACTIONS.get(ctx.stage, set())
    forbidden = STAGE_FORBIDDEN_ACTIONS.get(ctx.stage, set())
    expected = STAGE_EXPECTED_NEXT.get(ctx.stage, ExpectedNext.ASK_USER_GOAL)

    # INVARIANT: invoke_specialist is ONLY allowed at READY stage
    if ctx.stage != PipelineStage.READY:
        assert AllowedAction.INVOKE_SPECIALIST not in allowed, (
            f"INVARIANT VIOLATION: invoke_specialist in allowed_actions at stage {ctx.stage}"
        )

    lines = ["[CONTROL]"]

    if ctx.session_id:
        lines.append(f"session_id={ctx.session_id}")
    if ctx.batch_id:
        lines.append(f"batch_id={ctx.batch_id}")

    lines.append(f"stage={ctx.stage.value}")
    lines.append(f"data_kind={ctx.data_kind.value}")

    if ctx.capabilities_granted:
        caps = [c.value for c in ctx.capabilities_granted]
        lines.append(f"capabilities_granted=[{', '.join(caps)}]")

    if allowed:
        actions = [a.value for a in allowed]
        lines.append(f"allowed_actions=[{', '.join(actions)}]")

    if forbidden:
        actions = [f.value for f in forbidden]
        lines.append(f"forbidden_actions=[{', '.join(actions)}]")

    lines.append(f"expected_next={expected.value}")

    if ctx.transaction_count > 0:
        lines.append(f"transaction_count={ctx.transaction_count}")
    if ctx.file_count > 0:
        lines.append(f"file_count={ctx.file_count}")
    if ctx.is_partial:
        lines.append("partial_data=true")

    lines.append("[/CONTROL]")
    return "\n".join(lines)


def status_to_stage(status: str) -> PipelineStage:
    mapping = {
        "uploading": PipelineStage.UPLOADING,
        "parsing": PipelineStage.PDF_PARSE,
        "processing": PipelineStage.NORMALIZE,
        "extracting": PipelineStage.AGGREGATE,
        "ready": PipelineStage.READY,
        "analyzing": PipelineStage.ANALYZING,
        "complete": PipelineStage.COMPLETE,
        "failed": PipelineStage.FAILED,
    }
    return mapping.get(status.lower(), PipelineStage.UPLOADING)


def data_kind_for_stage(stage: PipelineStage) -> DataKind:
    if stage in (PipelineStage.UPLOADING, PipelineStage.PDF_PARSE):
        return DataKind.METADATA
    elif stage in (PipelineStage.NORMALIZE, PipelineStage.AGGREGATE):
        return DataKind.TEXT
    elif stage == PipelineStage.READY:
        return DataKind.TRANSACTIONS
    elif stage in (PipelineStage.ANALYZING, PipelineStage.COMPLETE):
        return DataKind.ANALYSIS
    return DataKind.METADATA
