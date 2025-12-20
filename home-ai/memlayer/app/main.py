from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from .memory_engine import MemoryEngine

app = FastAPI(title="Home AI – MemLayer")

engine = MemoryEngine()  # uses /mnt/models/memlayer by default


# ------------------------- Schemas -------------------------


class WriteMemoryRequest(BaseModel):
    user_id: str
    text: str
    metadata: Optional[Dict[str, Any]] = None


class WriteMemoryResponse(BaseModel):
    salient: bool
    stored_vector: bool
    stored_facts: bool
    id: Optional[str] = None
    timestamp: Optional[int] = None


class SearchMemoryRequest(BaseModel):
    user_id: str
    query: str
    k: int = 5


class SearchHit(BaseModel):
    text: str
    metadata: Dict[str, Any]
    distance: Optional[float] = None


class SearchMemoryResponse(BaseModel):
    results: List[SearchHit]


class ProfileRequest(BaseModel):
    user_id: str


class ProfileResponse(BaseModel):
    profile: Dict[str, Any]


class ReminderCreateRequest(BaseModel):
    user_id: str
    text: str
    due_iso: str


class ReminderCreateResponse(BaseModel):
    id: str
    text: str
    due: str
    created_at: int


class ReminderListResponse(BaseModel):
    reminders: List[Dict[str, Any]]


# ------------------------- Routes --------------------------


@app.get("/")
def health() -> Dict[str, str]:
    return {"status": "memlayer ok", "mode": "local"}


@app.post("/memory/write", response_model=WriteMemoryResponse)
def write_memory(req: WriteMemoryRequest):
    try:
        res = engine.write_memory(req.user_id, req.text, req.metadata)
        return WriteMemoryResponse(**res)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"write_error: {e!s}")


@app.post("/memory/search", response_model=SearchMemoryResponse)
def search_memory(req: SearchMemoryRequest):
    try:
        hits = engine.search_memory(req.user_id, req.query, req.k)
        return SearchMemoryResponse(results=[SearchHit(**h) for h in hits])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"search_error: {e!s}")


@app.post("/profile/get", response_model=ProfileResponse)
def get_profile(req: ProfileRequest):
    try:
        profile = engine.get_profile(req.user_id)
        return ProfileResponse(profile=profile)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"profile_error: {e!s}")


@app.post("/reminders/add", response_model=ReminderCreateResponse)
def add_reminder(req: ReminderCreateRequest):
    try:
        r = engine.add_reminder(req.user_id, req.text, req.due_iso)
        return ReminderCreateResponse(**r)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"reminder_add_error: {e!s}")


@app.post("/reminders/list", response_model=ReminderListResponse)
def list_reminders(req: ProfileRequest):
    try:
        rs = engine.list_reminders(req.user_id)
        return ReminderListResponse(reminders=rs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"reminder_list_error: {e!s}")
