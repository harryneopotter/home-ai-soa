from fastapi import FastAPI, HTTPException, Response, UploadFile, File, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
import json
import yaml
from collections import defaultdict
import uvicorn
import os
import uuid
import asyncio
from io import BytesIO
from datetime import datetime
import time
from pathlib import Path

from agent import SOA1Agent
from pdf_processor import pdf_processor
from batch_processor import batch_processor
from output_generator import output_generator
from utils.logger import get_logger
from utils.errors import (
    SOA1Error,
    ValidationError,
    ServiceError,
    InternalError,
    RateLimitError,
    NotFoundError,
)
from utils.rate_limiter import get_limiter_for_endpoint
import requests as http_requests


WEBUI_URL = os.environ.get("WEBUI_URL", "http://localhost:8080")


def emit_pipeline_event(event_type: str, batch_id: str = None, details: dict = None):
    """Send pipeline event to WebUI monitoring dashboard (fire-and-forget)."""
    try:
        http_requests.post(
            f"{WEBUI_URL}/api/pipeline/event",
            json={"type": event_type, "batch_id": batch_id, "details": details or {}},
            timeout=1,
        )
    except Exception:
        pass


# Input validation limits
MAX_MESSAGE_LENGTH = 10000
MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_BATCH_ID_LENGTH = 100
try:
    from home_ai.finance_agent.src import storage as chat_storage

    CHAT_STORAGE_AVAILABLE = True
except ImportError:
    CHAT_STORAGE_AVAILABLE = False

logger = get_logger("api")

_pending_documents: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

_document_parse_status: Dict[str, Dict[str, Any]] = {}

if CHAT_STORAGE_AVAILABLE:

    def _persist_batch_status(batch_id: str, status: str):
        try:
            chat_storage.update_batch_status(batch_id, status)
        except Exception as e:
            logger.warning(f"Failed to persist batch status: {e}")

    batch_processor.set_status_callback(_persist_batch_status)

    try:
        chat_storage.init_db()
        hydrated = batch_processor.hydrate_from_db(chat_storage)
        if hydrated > 0:
            logger.info(f"Hydrated {hydrated} batches from database")
    except Exception as e:
        logger.warning(f"Failed to hydrate batches from DB: {e}")


def _get_session_id(request: Request) -> str:
    session_id = request.headers.get("X-Session-ID")
    if not session_id:
        session_id = request.client.host
    return session_id


def _get_pending_document_context(session_id: str) -> Optional[Dict[str, Any]]:
    legacy_docs = _pending_documents.get(session_id, [])
    if legacy_docs:
        return {"documents": legacy_docs, "session_id": session_id}

    if CHAT_STORAGE_AVAILABLE:
        try:
            batch_info = chat_storage.get_latest_batch_for_session(session_id)
            if batch_info:
                batch_id = batch_info["batch_id"]
                state = batch_processor.get_batch_state(batch_id)
                if state and state.files:
                    return {
                        "batch_id": batch_id,
                        "documents": state.files,
                        "session_id": session_id,
                        "status": state.status,
                    }
        except Exception as e:
            logger.warning(f"Failed to get batch context for session {session_id}: {e}")

    return None


def _add_pending_document(session_id: str, doc_metadata: Dict[str, Any]) -> None:
    _pending_documents[session_id].append(doc_metadata)


async def _run_phinance_background(
    batch_id: str, agent: "SOA1Agent", document_context: Dict[str, Any]
):
    try:
        state = batch_processor.get_batch_state(batch_id)
        if not state:
            logger.error(f"Batch {batch_id} not found for background phinance")
            return

        emit_pipeline_event("phinance_background_start", batch_id)

        def _sync_phinance():
            return agent._invoke_phinance(document_context)

        await asyncio.to_thread(_sync_phinance)

        state.status = "complete"
        emit_pipeline_event("phinance_background_complete", batch_id)
        logger.info(f"Background phinance complete for batch {batch_id}")

        asyncio.create_task(
            batch_processor.pre_generate_outputs(batch_id, output_generator)
        )

    except Exception as e:
        logger.error(f"Background phinance failed for {batch_id}: {e}")
        emit_pipeline_event(
            "error", batch_id, {"stage": "phinance_background", "error": str(e)}
        )
        state = batch_processor.get_batch_state(batch_id)
        if state:
            state.status = "failed"


# Request/Response Models
class AskRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)

    @validator("query")
    def validate_query_content(cls, v):
        if v.strip() == "":
            raise ValueError("Query cannot be empty or whitespace only")
        if len(v.encode("utf-8")) > 2000:  # Byte length check
            raise ValueError("Query too long (max 2000 bytes)")
        return v


class AskResponse(BaseModel):
    answer: str
    used_memories: list
    audio_path: Optional[str] = None
    audio_duration: Optional[float] = None
    tts_error: Optional[str] = None


class TTSResponse(BaseModel):
    audio_path: str
    duration: float
    answer: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    response: str
    used_memories: list = []
    redirect_url: Optional[str] = None


class PDFUploadRequest(BaseModel):
    max_pages: Optional[int] = Field(10, ge=1, le=50)


class PDFAnalysisRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    pdf_id: str = Field(..., min_length=1, max_length=50)
    top_k: Optional[int] = Field(5, ge=1, le=20)


def create_app() -> FastAPI:
    app = FastAPI(title="SOA1 Agent API", version="0.1.0")

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Initialize agent
    agent = SOA1Agent()

    # Register consent router lazily to avoid startup-time import issues.
    # Use importlib to load the module by file path and register it in sys.modules
    # to avoid ambiguous imports across different working directories.
    try:
        import importlib.util
        import sys as _sys

        consent_path = Path(__file__).resolve().parent / "consent.py"
        spec = importlib.util.spec_from_file_location("soa1_consent", str(consent_path))
        consent_mod = importlib.util.module_from_spec(spec)
        # Register before executing to avoid dataclass/module import subtleties
        _sys.modules[spec.name] = consent_mod
        spec.loader.exec_module(consent_mod)
        consent_router = getattr(consent_mod, "router")

        app.include_router(consent_router, prefix="/api", tags=["consent"])
        # Also expose under root /consent for WebUI convenience
        app.include_router(consent_router, prefix="", tags=["consent"])
        logger.info("Consent router mounted at /api/consent and /consent")
    except Exception as e:
        # If mounting fails, log but don't prevent server startup
        logger.warning("Consent router not mounted due to import error: %s", str(e))

    # Error handlers
    @app.exception_handler(SOA1Error)
    async def soa1_error_handler(request: Request, exc: SOA1Error):
        """Standardized error response format"""
        error_id = str(uuid.uuid4())
        logger.error(
            f"API Error [{error_id}]: {exc.error_code} - {exc.detail['message']}"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": exc.error_code,
                "message": exc.detail["message"],
                "details": exc.detail.get("details", {}),
                "error_id": error_id,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    @app.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException):
        """Handle standard HTTP exceptions"""
        logger.error(f"HTTP Error {exc.status_code}: {exc.detail}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": "HTTP_ERROR",
                "message": exc.detail,
                "status_code": exc.status_code,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        """Catch-all for unexpected errors"""
        error_id = str(uuid.uuid4())
        logger.error(f"Unexpected error [{error_id}]: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "error_id": error_id,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    # Rate limiting middleware
    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        """Global rate limiting middleware"""
        client_ip = request.client.host
        endpoint = request.url.path

        # Skip rate limiting for static files and health checks
        if endpoint.startswith("/static") or endpoint == "/health":
            return await call_next(request)

        # Get appropriate limiter
        limiter = get_limiter_for_endpoint(endpoint)

        if not limiter.check(client_ip):
            retry_after = limiter.get_retry_after(client_ip)
            logger.warning(f"Rate limit exceeded for {client_ip} on {endpoint}")
            raise RateLimitError(retry_after)

        response = await call_next(request)
        return response

    # ==================== API Endpoints ====================

    @app.get("/health")
    def health():
        """Health check endpoint"""
        return {"status": "ok"}

    @app.post("/api/chat", response_model=ChatResponse)
    async def chat(req: ChatRequest, request: Request):
        """Chat endpoint for WebUI - simple message in, response out"""
        client_ip = request.client.host
        session_id = _get_session_id(request)
        logger.info(
            f"[{client_ip}] /api/chat called with message: {req.message[:50]}..."
        )
        if len(req.message) > MAX_MESSAGE_LENGTH:
            raise ValidationError(
                f"Message exceeds maximum length of {MAX_MESSAGE_LENGTH} characters",
                "message",
                req.message[:100],
            )

        try:
            if CHAT_STORAGE_AVAILABLE:
                chat_storage.init_db()
                chat_storage.save_chat_message(session_id, "user", req.message)

            document_context = _get_pending_document_context(session_id)

            chat_history = []
            if CHAT_STORAGE_AVAILABLE:
                history = chat_storage.get_chat_history(session_id, limit=20)
                chat_history = [
                    {"role": h["role"], "content": h["content"]} for h in history[:-1]
                ]

            result = agent.ask(
                req.message,
                document_context=document_context,
                chat_history=chat_history,
            )
            logger.info(f"[{client_ip}] Chat response generated successfully")

            if result.get("trigger_phinance_background"):
                batch_id = result["trigger_phinance_background"]
                asyncio.create_task(
                    _run_phinance_background(batch_id, agent, document_context)
                )
                logger.info(
                    f"Started background phinance analysis for batch {batch_id}"
                )

            if result.get("trigger_output_generation"):
                batch_id = result["trigger_output_generation"]
                asyncio.create_task(
                    batch_processor.pre_generate_outputs(batch_id, output_generator)
                )
                logger.info(f"Triggered output pre-generation for batch {batch_id}")

            if CHAT_STORAGE_AVAILABLE:
                chat_storage.save_chat_message(
                    session_id, "assistant", result["answer"]
                )

            return ChatResponse(
                response=result["answer"],
                used_memories=result.get("used_memories", []),
                redirect_url=result.get("redirect_url"),
            )

        except Exception as e:
            logger.error(f"[{client_ip}] Chat processing failed: {e}", exc_info=True)
            raise InternalError(f"Chat processing failed: {str(e)}")

    @app.post("/api/chat/stream")
    async def chat_stream(req: ChatRequest, request: Request):
        """Streaming chat endpoint - returns SSE stream of chunks"""
        client_ip = request.client.host
        session_id = _get_session_id(request)
        logger.info(
            f"[{client_ip}] /api/chat/stream called with message: {req.message[:50]}..."
        )
        if len(req.message) > MAX_MESSAGE_LENGTH:
            raise ValidationError(
                f"Message exceeds maximum length of {MAX_MESSAGE_LENGTH} characters",
                "message",
                req.message[:100],
            )

        async def generate_stream():
            try:
                if CHAT_STORAGE_AVAILABLE:
                    chat_storage.init_db()
                    chat_storage.save_chat_message(session_id, "user", req.message)

                document_context = _get_pending_document_context(session_id)

                chat_history = []
                if CHAT_STORAGE_AVAILABLE:
                    history = chat_storage.get_chat_history(session_id, limit=20)
                    chat_history = [
                        {"role": h["role"], "content": h["content"]}
                        for h in history[:-1]
                    ]

                response = agent.ask(
                    req.message,
                    document_context=document_context,
                    chat_history=chat_history,
                )
                complete_response = response.get("answer", "")

                yield f"data: {json.dumps({'chunk': complete_response})}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"

                if CHAT_STORAGE_AVAILABLE:
                    chat_storage.save_chat_message(
                        session_id, "assistant", complete_response
                    )

            except Exception as e:
                logger.error(f"[{client_ip}] Stream failed: {e}", exc_info=True)
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.post("/ask", response_model=AskResponse)
    async def ask(req: AskRequest, request: Request):
        """Main query endpoint with enhanced error handling"""
        client_ip = request.client.host
        session_id = _get_session_id(request)
        logger.info(f"[{client_ip}] /ask called with query: {req.query[:50]}...")
        if len(req.query) > MAX_MESSAGE_LENGTH:
            raise ValidationError(
                f"Query exceeds maximum length of {MAX_MESSAGE_LENGTH} characters",
                "query",
                req.query[:100],
            )

        try:
            if not req.query or not isinstance(req.query, str):
                raise ValidationError(
                    "Query must be a non-empty string", "query", req.query
                )

            document_context = _get_pending_document_context(session_id)
            result = agent.ask(req.query, document_context=document_context)
            logger.info(f"[{client_ip}] Agent response generated successfully")

            if result.get("trigger_output_generation"):
                batch_id = result["trigger_output_generation"]
                asyncio.create_task(
                    batch_processor.pre_generate_outputs(batch_id, output_generator)
                )
                logger.info(f"Triggered output pre-generation for batch {batch_id}")

            return AskResponse(
                answer=result["answer"],
                used_memories=result["used_memories"],
                audio_path=result.get("audio_path"),
                audio_duration=result.get("audio_duration"),
                tts_error=result.get("tts_error"),
            )

        except ValidationError:
            raise  # Re-raise validation errors
        except Exception as e:
            logger.error(f"[{client_ip}] Agent processing failed: {e}", exc_info=True)
            raise InternalError(f"Query processing failed: {str(e)}")

    @app.post("/ask-with-tts", response_model=TTSResponse)
    async def ask_with_tts(req: AskRequest, request: Request):
        """Ask and get TTS response with enhanced error handling"""
        client_ip = request.client.host
        logger.info(
            f"[{client_ip}] /ask-with-tts called with query: {req.query[:50]}..."
        )
        if len(req.query) > MAX_MESSAGE_LENGTH:
            raise ValidationError(
                f"Query exceeds maximum length of {MAX_MESSAGE_LENGTH} characters",
                "query",
                req.query[:100],
            )

        try:
            result = agent.ask_with_tts(req.query)

            if "audio_path" not in result or not result["audio_path"]:
                logger.warning(f"[{client_ip}] TTS not available or failed")
                raise ServiceError("tts", "TTS generation failed or not enabled")

            logger.info(f"[{client_ip}] TTS response generated successfully")
            return TTSResponse(
                audio_path=result["audio_path"],
                duration=result["audio_duration"],
                answer=result["answer"],
            )

        except ServiceError:
            raise  # Re-raise service errors
        except Exception as e:
            logger.error(f"[{client_ip}] TTS processing failed: {e}", exc_info=True)
            raise InternalError(f"TTS processing failed: {str(e)}")

    @app.get("/audio/{audio_file}")
    async def get_audio(audio_file: str, request: Request):
        """Serve audio files with enhanced error handling"""
        client_ip = request.client.host

        try:
            if not audio_file or not isinstance(audio_file, str):
                raise ValidationError(
                    "Invalid audio file name", "audio_file", audio_file
                )

            if not audio_file.endswith(".wav"):
                raise ValidationError(
                    "Only WAV files are supported", "audio_file", audio_file
                )

            safe_filename = os.path.basename(audio_file)
            if safe_filename != audio_file or ".." in audio_file:
                raise ValidationError(
                    "Invalid audio file path", "audio_file", audio_file
                )

            audio_path = os.path.join("/tmp/soa1_tts", safe_filename)

            if not os.path.exists(audio_path):
                logger.warning(f"[{client_ip}] Audio file not found: {audio_file}")
                raise NotFoundError("audio_file", audio_file)

            logger.info(f"[{client_ip}] Serving audio file: {audio_file}")
            return Response(
                content=open(audio_path, "rb").read(),
                media_type="audio/wav",
                headers={"Content-Disposition": f"inline; filename={safe_filename}"},
            )

        except ValidationError:
            raise  # Re-raise validation errors
        except Exception as e:
            logger.error(f"[{client_ip}] Audio file error: {e}", exc_info=True)
            raise InternalError(f"Failed to serve audio file: {str(e)}")

    @app.post("/upload-batch")
    async def upload_batch(
        files: List[UploadFile] = File(...), request: Request = None
    ):
        client_ip = request.client.host if request else "unknown"
        session_id = _get_session_id(request)
        logger.info(f"[{client_ip}] Batch upload requested: {len(files)} files")

        emit_pipeline_event("batch_upload_start", details={"file_count": len(files)})

        # Use a temporary directory to store files for background processing
        temp_dir = Path("/tmp/soa1_batch_uploads")
        temp_dir.mkdir(parents=True, exist_ok=True)

        processed_files = []
        agent = SOA1Agent()

        for idx, file in enumerate(files):
            try:
                emit_pipeline_event(
                    "quick_metadata_start",
                    details={"file": file.filename, "index": idx + 1},
                )

                content_bytes = await file.read()
                if len(content_bytes) > MAX_FILE_SIZE:
                    raise ValidationError(
                        f"File {file.filename} exceeds maximum size of 10MB",
                        "file",
                        file.filename,
                    )

                # Save raw bytes to a temporary file for background full parsing
                temp_file_path = temp_dir / f"{uuid.uuid4().hex}_{file.filename}"
                with open(temp_file_path, "wb") as f:
                    f.write(content_bytes)

                # Run quick metadata extraction (<500ms)
                result = pdf_processor.extract_quick_metadata(str(temp_file_path))

                doc_id = f"doc-{uuid.uuid4().hex[:6]}"
                file_size_bytes = result.get("file_size_bytes", 0)
                pages = result.get("pages", 0)

                emit_pipeline_event(
                    "quick_metadata_complete",
                    details={"file": file.filename, "pages": pages, "doc_id": doc_id},
                )

                if CHAT_STORAGE_AVAILABLE:
                    try:
                        chat_storage.save_document(
                            doc_id, file.filename, pages, file_size_bytes
                        )
                    except Exception as e:
                        logger.warning(f"Failed to save document {doc_id}: {e}")

                processed_files.append(
                    {
                        "filename": file.filename,
                        "pages": pages,
                        "size_kb": round(file_size_bytes / 1024, 1),
                        "doc_id": doc_id,
                        "temp_path": str(temp_file_path),
                        "inferred_type": result.get("inferred_type", "document"),
                        "header_lines": result.get("header_lines", []),
                    }
                )
            except Exception as e:
                logger.error(f"Failed to process file {file.filename}: {e}")
                emit_pipeline_event(
                    "error", details={"file": file.filename, "error": str(e)}
                )

        batch_id = batch_processor.create_batch(processed_files)
        doc_ids = [f.get("doc_id") for f in processed_files if f.get("doc_id")]

        emit_pipeline_event(
            "batch_created",
            batch_id=batch_id,
            details={"file_count": len(processed_files)},
        )

        if CHAT_STORAGE_AVAILABLE:
            try:
                chat_storage.save_batch(
                    batch_id, session_id, "uploading", len(processed_files), doc_ids
                )
            except Exception as e:
                logger.warning(f"Failed to persist batch to DB: {e}")

        # Kick off background FULL process (extraction + PII redaction + regex)
        asyncio.create_task(batch_processor.background_full_process(batch_id, agent))

        # Map inferred type to a subject for the intent question
        doc_types = [f.get("inferred_type", "document") for f in processed_files]
        if any(
            t in ["credit_card_statement", "bank_statement", "financial_document"]
            for t in doc_types
        ):
            subject = "finance"
        elif any(t == "utility_bill" for t in doc_types):
            subject = "utility"
        elif any(t == "invoice" for t in doc_types):
            subject = "billing"
        else:
            subject = "document"

        # Pass metadata to agent.ask for engagement
        document_context = {
            "batch_id": batch_id,
            "documents": processed_files,
            "session_id": session_id,
        }

        # Request intent question from LLM based on metadata
        agent_result = agent.ask(
            query="User just uploaded these documents. Acknowledge them specifically and offer relevant options based on the document types and content detected.",
            document_context=document_context,
        )

        return {
            "status": "SUCCESS",
            "batch_id": batch_id,
            "file_count": len(processed_files),
            "agent_response": agent_result.get("answer", ""),
        }

    async def _background_full_parse(doc_id: str, dest_path: str, filename: str):
        """Background task: performs full PDF parsing after quick response is sent."""

        def _do_parse():
            from io import BytesIO

            with open(dest_path, "rb") as f:
                content_bytes = f.read()

            class _SimpleUpload:
                def __init__(self, fname: str, content: bytes):
                    self.filename = fname
                    self.file = BytesIO(content)

            return pdf_processor.process_uploaded_pdf(
                _SimpleUpload(filename, content_bytes)
            )

        try:
            _document_parse_status[doc_id]["status"] = "parsing"
            logger.info(f"[background] Starting full parse for {doc_id}")

            result = await asyncio.to_thread(_do_parse)

            _document_parse_status[doc_id].update(
                {
                    "status": "complete",
                    "full_text": result.get("full_text", ""),
                    "encrypted_text": result.get("encrypted_text", ""),
                    "text_preview": result.get("text_preview", ""),
                    "word_count": result.get("word_count", 0),
                    "is_apple_card": result.get("is_apple_card", False),
                    "completed_at": datetime.utcnow().isoformat(),
                }
            )
            logger.info(
                f"[background] Full parse complete for {doc_id}: {result.get('word_count', 0)} words"
            )

        except Exception as e:
            logger.exception(f"[background] Full parse failed for {doc_id}: {e}")
            _document_parse_status[doc_id].update(
                {
                    "status": "error",
                    "error": str(e),
                    "completed_at": datetime.utcnow().isoformat(),
                }
            )

    async def _background_generate_intent(
        doc_id: str, filename: str, document_context: dict
    ):
        """Background task: generates LLM intent question after quick response is sent."""

        def _do_llm_call():
            agent = SOA1Agent()
            return agent.ask(
                query=f"I just uploaded a document: {filename}",
                document_context=document_context,
            )

        try:
            logger.info(f"[background] Generating intent question for {doc_id}")
            agent_result = await asyncio.to_thread(_do_llm_call)
            agent_response = agent_result.get("answer", "")
            _document_parse_status[doc_id]["agent_response"] = agent_response
            _document_parse_status[doc_id]["intent_ready"] = True
            logger.info(
                f"[background] Intent question ready for {doc_id} ({len(agent_response)} chars)"
            )
        except Exception as e:
            logger.warning(f"[background] Failed to generate intent for {doc_id}: {e}")
            _document_parse_status[doc_id]["agent_response"] = None
            _document_parse_status[doc_id]["intent_ready"] = True

    @app.post("/upload-pdf")
    async def upload_pdf(file: UploadFile = File(...), request: Request = None):
        """Upload PDF - returns quick metadata immediately, full parsing runs in background."""
        client_ip = request.client.host if request else "unknown"
        upload_start = time.time()
        logger.info(f"[{client_ip}] PDF upload requested: {file.filename}")

        try:
            if not file or not file.filename:
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "message": "No file provided"},
                )

            if not file.filename.lower().endswith(".pdf"):
                return JSONResponse(
                    status_code=400,
                    content={
                        "status": "error",
                        "message": "Only PDF files are accepted",
                    },
                )

            if hasattr(file, "size") and file.size and file.size > 10 * 1024 * 1024:
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "message": "File too large (max 10MB)"},
                )

            from pathlib import Path
            import re

            webui_upload_dir = (
                Path(__file__).resolve().parents[1]
                / "finance-agent"
                / "data"
                / "uploads"
            )
            webui_upload_dir.mkdir(parents=True, exist_ok=True)

            doc_id = f"finance-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"

            safe_filename = re.sub(
                r"[^\w\-_\.]", "_", os.path.basename(file.filename or "upload.pdf")
            )
            if not safe_filename.lower().endswith(".pdf"):
                safe_filename += ".pdf"
            dest_path = webui_upload_dir / f"{doc_id}_{safe_filename}"

            try:
                try:
                    await file.seek(0)
                except Exception:
                    pass
                content_bytes = await file.read()
                with open(dest_path, "wb") as fdest:
                    fdest.write(content_bytes)
            except Exception as e:
                logger.exception("Failed to save uploaded file: %s", e)
                return JSONResponse(
                    status_code=500,
                    content={
                        "status": "error",
                        "message": "Failed to store uploaded file",
                    },
                )

            file_save_time = time.time()
            logger.info(
                f"[{client_ip}] File saved in {(file_save_time - upload_start) * 1000:.0f}ms"
            )

            quick_meta = pdf_processor.extract_quick_metadata(str(dest_path))
            quick_meta_time = time.time()
            logger.info(
                f"[{client_ip}] Quick metadata in {(quick_meta_time - file_save_time) * 1000:.0f}ms"
            )

            _document_parse_status[doc_id] = {
                "status": "pending_full_parse",
                "filename": file.filename,
                "pages": quick_meta.get("pages", 0),
                "file_size_bytes": quick_meta.get("file_size_bytes", 0),
                "inferred_type": quick_meta.get("inferred_type", "document"),
                "header_lines": quick_meta.get("header_lines", []),
                "dest_path": str(dest_path),
                "created_at": datetime.utcnow().isoformat(),
            }

            try:
                from home_ai.finance_agent.src import storage as fa_storage
            except Exception:
                import sys
                import importlib

                fa_src_path = (
                    Path(__file__).resolve().parents[1] / "finance-agent" / "src"
                )
                if str(fa_src_path) not in sys.path:
                    sys.path.insert(0, str(fa_src_path))
                fa_storage = importlib.import_module("storage")

            fa_storage.save_document(
                doc_id,
                file.filename,
                quick_meta.get("pages", 0),
                quick_meta.get("file_size_bytes", 0),
            )

            job_id = f"job-{doc_id}-{uuid.uuid4().hex[:6]}"
            fa_storage.create_analysis_job(job_id, doc_id, status="pending")

            session_id = _get_session_id(request)
            inferred_type = quick_meta.get("inferred_type", "document")
            _add_pending_document(
                session_id,
                {
                    "filename": file.filename,
                    "pages": quick_meta.get("pages", 0),
                    "size_kb": round(quick_meta.get("file_size_bytes", 0) / 1024, 1),
                    "upload_time": datetime.utcnow().isoformat(),
                    "detected_type": inferred_type,
                    "doc_id": doc_id,
                },
            )

            header_preview = "\n".join(quick_meta.get("header_lines", [])[:5])
            document_context = {
                "documents": [
                    {
                        "doc_id": doc_id,
                        "filename": file.filename,
                        "pages": quick_meta.get("pages", 0),
                        "size_kb": round(
                            quick_meta.get("file_size_bytes", 0) / 1024, 1
                        ),
                        "upload_time": datetime.utcnow().isoformat(),
                        "detected_type": inferred_type,
                        "preview_text": header_preview,
                    }
                ],
                "session_id": session_id,
            }

            asyncio.create_task(
                _background_full_parse(doc_id, str(dest_path), file.filename)
            )
            asyncio.create_task(
                _background_generate_intent(doc_id, file.filename, document_context)
            )

            total_time = time.time() - upload_start
            logger.info(
                f"[{client_ip}] Upload response ready in {total_time * 1000:.0f}ms (parse + LLM continue in background)"
            )

            payload = {
                "status": "UPLOADED",
                "doc_id": doc_id,
                "job_id": job_id,
                "file_id": str(uuid.uuid4()),
                "filename": file.filename,
                "pages": quick_meta.get("pages", 0),
                "bytes": quick_meta.get("file_size_bytes", 0),
                "detected_type": inferred_type,
                "parse_status": "pending_full_parse",
                "intent_ready": False,
                "response_time_ms": round(total_time * 1000),
            }
            return JSONResponse(content=payload)

        except Exception as e:
            logger.exception(f"PDF upload failed: {e}")
            return JSONResponse(
                status_code=500, content={"status": "error", "message": str(e)}
            )

    @app.get("/upload-status/{doc_id}")
    async def get_upload_status(doc_id: str):
        """Check the parsing status of an uploaded document."""
        if doc_id not in _document_parse_status:
            raise HTTPException(status_code=404, detail="Document not found")

        status_data = _document_parse_status[doc_id]
        return {
            "doc_id": doc_id,
            "status": status_data.get("status", "unknown"),
            "filename": status_data.get("filename"),
            "pages": status_data.get("pages"),
            "inferred_type": status_data.get("inferred_type"),
            "word_count": status_data.get("word_count"),
            "is_apple_card": status_data.get("is_apple_card"),
            "created_at": status_data.get("created_at"),
            "completed_at": status_data.get("completed_at"),
            "error": status_data.get("error"),
            "intent_ready": status_data.get("intent_ready", False),
            "agent_response": status_data.get("agent_response"),
        }

    @app.post("/analyze-pdf")
    async def analyze_pdf(
        query: str = "Summarize the key points",
        text: str = None,
        file: UploadFile = None,
        request: Request = None,
    ):
        """DEPRECATED: Use orchestrator consent-gated flow instead."""
        client_ip = request.client.host if request else "unknown"
        logger.info(f"[{client_ip}] Deprecated /analyze-pdf called")

        return JSONResponse(
            status_code=410,
            content={
                "success": False,
                "error": "DEPRECATED",
                "message": "This endpoint is deprecated. Use orchestrator consent-gated flow instead.",
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    @app.post("/api/batch/consent")
    async def grant_batch_consent(batch_id: str, action: str, request: Request):
        if len(batch_id) > MAX_BATCH_ID_LENGTH:
            raise ValidationError(
                f"Batch ID exceeds maximum length of {MAX_BATCH_ID_LENGTH} characters",
                "batch_id",
                batch_id[:50],
            )
        state = batch_processor.get_batch_state(batch_id)
        if not state:
            raise HTTPException(status_code=404, detail="Batch not found")

        if action == "analyze" and state.status == "ready":
            state.status = "consent_granted"

            preliminary_msg = state.preliminary_insights.get(
                "summary", "Analyzing your documents now..."
            )

            asyncio.create_task(agent.analyze_batch(batch_id))

            return {
                "status": "ANALYZING",
                "preliminary_insights": preliminary_msg,
                "interesting_findings": state.interesting_findings,
            }

        return {"status": state.status}

    @app.get("/api/batch/status/{batch_id}")
    async def get_batch_status(batch_id: str):
        if len(batch_id) > MAX_BATCH_ID_LENGTH:
            raise ValidationError(
                f"Batch ID exceeds maximum length of {MAX_BATCH_ID_LENGTH} characters",
                "batch_id",
                batch_id[:50],
            )
        state = batch_processor.get_batch_state(batch_id)
        if not state:
            raise HTTPException(status_code=404, detail="Batch not found")

        response = {
            "batch_id": state.batch_id,
            "status": state.status,
            "file_count": len(state.files),
            "files": [
                {"filename": f.get("filename"), "pages": f.get("pages")}
                for f in state.files
            ],
            "preliminary_insights": state.preliminary_insights,
            "interesting_findings": state.interesting_findings,
            "transaction_count": state.transaction_count,
            "outputs_ready": state.outputs_ready,
            "created_at": state.created_at,
            "analysis_ready_at": state.analysis_ready_at,
            "phinance_complete_at": state.phinance_complete_at,
            "outputs_ready_at": state.outputs_ready_at,
        }

        if state.status == "complete" and state.phinance_analysis:
            analysis = state.phinance_analysis
            response["analysis_summary"] = {
                "total_spent": analysis.get("total_spent"),
                "categories": analysis.get("categories"),
                "top_merchants": analysis.get("top_merchants", [])[:5],
                "hidden_drains_count": len(analysis.get("hidden_drains", [])),
                "insights": analysis.get("insights", [])[:3],
            }
            response["completion_message"] = (
                f"Analysis complete! I found {state.transaction_count} transactions "
                f"totaling ${abs(float(analysis.get('total_spent', 0))):,.2f}. "
                "How would you like the detailed report?\n"
                "1. 🖥️ Web Dashboard\n"
                "2. 📄 PDF Export\n"
                "3. 🎨 Infographic"
            )

        return response

    @app.get("/api/batch/session/{session_id}")
    async def get_session_batch(session_id: str):
        if not CHAT_STORAGE_AVAILABLE:
            raise HTTPException(status_code=501, detail="Storage not available")

        batch_record = chat_storage.get_latest_batch_for_session(session_id)
        if not batch_record:
            return {"batch_id": None, "status": "none"}

        batch_id = batch_record["batch_id"]
        state = batch_processor.get_batch_state(batch_id)

        if state:
            return {
                "batch_id": batch_id,
                "status": state.status,
                "file_count": len(state.files),
                "in_memory": True,
            }

        return {
            "batch_id": batch_id,
            "status": batch_record.get("status", "unknown"),
            "file_count": batch_record.get("file_count", 0),
            "in_memory": False,
            "created_at": batch_record.get("created_at"),
        }

    @app.get("/api/output/{batch_id}/{format}")
    async def get_output(batch_id: str, format: str):
        state = batch_processor.get_batch_state(batch_id)
        if not state:
            raise HTTPException(status_code=404, detail="Batch not found")

        if format == "dashboard":
            data = state.outputs.get("dashboard_json")
            if not data:
                analysis = state.phinance_analysis
                if not analysis:
                    try:
                        from home_ai.finance_agent.src import storage as fa_storage

                        analysis = fa_storage.get_batch_phinance_analysis(batch_id)
                        if analysis:
                            state.phinance_analysis = analysis
                    except Exception:
                        pass
                if not analysis:
                    analysis = state.calculated_summary or {}
                data = await output_generator.generate_dashboard_json(
                    analysis, batch_id
                )
                state.outputs["dashboard_json"] = data
            return data

        elif format == "pdf":
            command = state.outputs.get("pdf_command")
            if not command and state.phinance_analysis:
                command = await output_generator.build_pdf_command(
                    state.phinance_analysis
                )
                state.outputs["pdf_command"] = command
            return {"command": command}

        elif format == "infographic":
            prompt = state.outputs.get("infographic_prompt")
            if not prompt and state.phinance_analysis:
                prompt = await output_generator.build_infographic_prompt(
                    state.phinance_analysis
                )
                state.outputs["infographic_prompt"] = prompt
            return {"prompt": prompt}

        raise HTTPException(status_code=400, detail="Invalid format")

    return app


if __name__ == "__main__":
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    with open(config_path, "r") as f:
        cfg = yaml.safe_load(f)
    host = cfg["server"]["host"]
    port = int(cfg["server"]["port"])

    uvicorn.run("api:create_app", host=host, port=port, reload=False, factory=True)
