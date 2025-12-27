"""Consent recording helpers and API bindings for SOA1.

This module provides a simple endpoint to record user consent for a given job/doc
and helper functions to check and require consent when invoking specialists.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import sys
from pathlib import Path

# Defer importing storage until a request is received to avoid startup-time failures
# (storage relies on local file system and DB; importing at module import time can raise errors
# in environments where the finance-agent src isn't yet available).


def _get_storage():
    """Lazily import the finance-agent storage module."""
    finance_src = Path(__file__).resolve().parents[1] / "finance-agent" / "src"
    if str(finance_src) not in sys.path:
        sys.path.insert(0, str(finance_src))
    import importlib

    try:
        storage = importlib.import_module("storage")
    except Exception as exc:
        raise RuntimeError(
            f"Failed to import 'storage' from {finance_src}: {exc}"
        ) from exc
    return storage


router = APIRouter()


class ConsentRequest(BaseModel):
    job_id: Optional[str] = None
    doc_id: Optional[str] = None
    confirm: bool = True
    specialist: Optional[str] = None
    intent: Optional[str] = None


class ConsentResponse(BaseModel):
    job_id: str
    confirmed: bool


@router.post("/consent", response_model=ConsentResponse)
async def record_consent(req: ConsentRequest):
    """Record user consent for a pending analysis job.

    Accepts either job_id or doc_id (job_id preferred). Marks the job as consented
    and records the specialist/intention selected by the user.
    """
    job = None

    storage = _get_storage()

    if req.job_id:
        job = storage.load_job(req.job_id)
    elif req.doc_id:
        job = storage.load_job_by_doc_id(req.doc_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job_id = job.get("job_id")

    if req.confirm:
        storage.update_analysis_job(
            job_id,
            status="confirmed",
            consent_given=1,
            confirmed_specialist=req.specialist or "phinance",
            confirmed_intent=req.intent or "SPECIALIST_ANALYSIS",
        )
        return ConsentResponse(job_id=job_id, confirmed=True)

    storage.update_analysis_job(job_id, status="cancelled", consent_given=0)
    return ConsentResponse(job_id=job_id, confirmed=False)
