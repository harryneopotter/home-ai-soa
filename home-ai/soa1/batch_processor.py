import time
import uuid
import asyncio
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable


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
    phinance_attempts: int = 0

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
        self._on_status_change: Optional[Callable[[str, str], None]] = None

    def set_status_callback(self, callback: Callable[[str, str], None]):
        self._on_status_change = callback

    def hydrate_from_db(self, storage_module) -> int:
        """Restore incomplete batches from database on startup. Returns count hydrated."""
        try:
            incomplete = storage_module.get_incomplete_batches()
            count = 0
            for batch_record in incomplete:
                batch_id = batch_record["batch_id"]
                if batch_id in self.batches:
                    continue

                batch_full = storage_module.get_batch_full(batch_id)
                if not batch_full:
                    continue

                extracted_text = batch_full.get("extracted_text", "")
                phinance_analysis = batch_full.get("phinance_analysis")

                state = BatchState(
                    batch_id=batch_id,
                    status=batch_full.get("status", "ready"),
                    files=[{"full_text": extracted_text}] if extracted_text else [],
                )
                state.phinance_prompt = extracted_text
                if phinance_analysis:
                    state.phinance_analysis = phinance_analysis
                    state.status = "complete"

                self.batches[batch_id] = state
                count += 1
            return count
        except Exception:
            return 0

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

            if self._on_status_change:
                try:
                    self._on_status_change(batch_id, status)
                except Exception:
                    pass

    async def background_analyze(self, batch_id: str, agent: Any):
        state = self.get_batch_state(batch_id)
        if not state:
            return

        self.update_batch_status(batch_id, "analyzing")

        all_text = ""
        for doc in state.files:
            all_text += doc.get("full_text", doc.get("text_preview", "")) + "\n"

        try:
            preliminary = await agent.analyze_preliminary_text(all_text)

            state.preliminary_insights = preliminary.get(
                "insights", {"summary": "Preliminary analysis complete."}
            )
            state.interesting_findings = preliminary.get("interesting", [])
            state.transaction_count = preliminary.get("transaction_count", 0)

            full_text = ""
            is_apple_card_batch = False
            for doc in state.files:
                full_text += doc.get("full_text", doc.get("text_preview", "")) + "\n"
                if doc.get("is_apple_card"):
                    is_apple_card_batch = True

            state.phinance_prompt = full_text
            if is_apple_card_batch:
                state.phinance_prompt = f"[FORMAT:APPLE_CARD]\n{full_text}"

            self.update_batch_status(batch_id, "ready")

        except Exception as e:
            self.update_batch_status(batch_id, "failed")
            print(f"Background analysis failed for {batch_id}: {e}")

    async def pre_generate_outputs(self, batch_id: str, generator: Any):
        state = self.get_batch_state(batch_id)
        if not state or not state.phinance_analysis:
            return

        try:
            analysis = state.phinance_analysis

            dashboard_task = asyncio.create_task(
                generator.generate_dashboard_json(analysis)
            )
            pdf_task = asyncio.create_task(generator.build_pdf_prompt(analysis))
            infographic_task = asyncio.create_task(
                generator.build_infographic_prompt(analysis)
            )
            summary_task = asyncio.create_task(
                generator.generate_text_summary(analysis)
            )

            results = await asyncio.gather(
                dashboard_task, pdf_task, infographic_task, summary_task
            )

            state.outputs = {
                "dashboard_json": results[0],
                "pdf_prompt": results[1],
                "infographic_prompt": results[2],
                "text_summary": results[3],
            }
            state.outputs_ready = True
            state.outputs_ready_at = time.time()
        except Exception as e:
            print(f"Output pre-generation failed for {batch_id}: {e}")

    def _build_phinance_prompt(self, preliminary: Dict[str, Any]) -> str:
        return f"Analyze these transactions: {preliminary.get('transactions', [])}"


batch_processor = BatchProcessor()
