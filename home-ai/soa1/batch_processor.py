import time
import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class BatchState:
    batch_id: str
    status: str
    files: List[Dict] = field(default_factory=list)

    preliminary_insights: Optional[Dict] = None
    phinance_prompt: Optional[str] = None
    transaction_count: int = 0
    interesting_findings: List[str] = field(default_factory=list)

    phinance_analysis: Optional[Dict] = None

    outputs: Dict[str, Any] = field(
        default_factory=lambda: {
            "dashboard_json": None,
            "pdf_prompt": None,
            "infographic_prompt": None,
            "text_summary": None,
        }
    )
    outputs_ready: bool = False

    created_at: float = field(default_factory=time.time)
    analysis_ready_at: Optional[float] = None
    phinance_complete_at: Optional[float] = None
    outputs_ready_at: Optional[float] = None


class BatchProcessor:
    def __init__(self):
        self.batches: Dict[str, BatchState] = {}

    def create_batch(self, files: List[Dict]) -> str:
        batch_id = f"batch-{uuid.uuid4().hex[:8]}"
        state = BatchState(batch_id=batch_id, status="uploading", files=files)
        self.batches[batch_id] = state
        return batch_id

    def get_batch_state(self, batch_id: str) -> Optional[BatchState]:
        return self.batches.get(batch_id)

    def update_batch_status(self, batch_id: str, status: str):
        if batch_id in self.batches:
            self.batches[batch_id].status = status
            if status == "ready":
                self.batches[batch_id].analysis_ready_at = time.time()
            elif status == "complete":
                self.batches[batch_id].phinance_complete_at = time.time()


batch_processor = BatchProcessor()
