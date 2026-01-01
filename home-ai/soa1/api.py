from fastapi import FastAPI, HTTPException, Response, UploadFile, File, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
import yaml
from collections import defaultdict
import uvicorn
import os
import uuid
from datetime import datetime
import time
from pathlib import Path

from agent import SOA1Agent
from pdf_processor import pdf_processor
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

try:
    from home_ai.finance_agent.src import storage as chat_storage

    CHAT_STORAGE_AVAILABLE = True
except ImportError:
    CHAT_STORAGE_AVAILABLE = False

logger = get_logger("api")

_pending_documents: Dict[str, List[Dict[str, Any]]] = defaultdict(list)


def _get_session_id(request: Request) -> str:
    session_id = request.headers.get("X-Session-ID")
    if not session_id:
        session_id = request.client.host
    return session_id


def _get_pending_document_context(session_id: str) -> Optional[Dict[str, Any]]:
    docs = _pending_documents.get(session_id, [])
    if not docs:
        return None
    return {"documents": docs, "session_id": session_id}


def _add_pending_document(session_id: str, doc_metadata: Dict[str, Any]) -> None:
    _pending_documents[session_id].append(doc_metadata)


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

            if CHAT_STORAGE_AVAILABLE:
                chat_storage.save_chat_message(
                    session_id, "assistant", result["answer"]
                )

            return ChatResponse(
                response=result["answer"],
                used_memories=result.get("used_memories", []),
            )

        except Exception as e:
            logger.error(f"[{client_ip}] Chat processing failed: {e}", exc_info=True)
            raise InternalError(f"Chat processing failed: {str(e)}")

    @app.post("/ask", response_model=AskResponse)
    async def ask(req: AskRequest, request: Request):
        """Main query endpoint with enhanced error handling"""
        client_ip = request.client.host
        session_id = _get_session_id(request)
        logger.info(f"[{client_ip}] /ask called with query: {req.query[:50]}...")

        try:
            if not req.query or not isinstance(req.query, str):
                raise ValidationError(
                    "Query must be a non-empty string", "query", req.query
                )

            document_context = _get_pending_document_context(session_id)
            result = agent.ask(req.query, document_context=document_context)
            logger.info(f"[{client_ip}] Agent response generated successfully")

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

    # ==================== PDF Endpoints (Demo) ====================
    # Consent gate: analysis must be orchestrator-driven.

    @app.post("/upload-pdf")
    async def upload_pdf(file: UploadFile = File(...), request: Request = None):
        """Upload PDF document - metadata only. No auto-processing without consent."""
        client_ip = request.client.host if request else "unknown"
        logger.info(f"[{client_ip}] PDF upload requested: {file.filename}")

        try:
            # Validate file
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

            if (
                hasattr(file, "size") and file.size and file.size > 10 * 1024 * 1024
            ):  # 10MB limit
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "message": "File too large (max 10MB)"},
                )

            # Save a copy into the WebUI finance upload directory so other components (e.g., /analyze-stage-ab)
            # can find the file by doc_id. This keeps the upload and analysis flows compatible.
            from pathlib import Path
            from io import BytesIO

            # Compute canonical finance uploads directory (project-root/home-ai/finance-agent/data/uploads)
            webui_upload_dir = (
                Path(__file__).resolve().parents[1]
                / "finance-agent"
                / "data"
                / "uploads"
            )
            webui_upload_dir.mkdir(parents=True, exist_ok=True)

            # Create a finance-style doc_id matching the web UI convention
            doc_id = f"finance-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"

            # Sanitize filename to prevent path traversal
            import re

            safe_filename = re.sub(
                r"[^\w\-_\.]", "_", os.path.basename(file.filename or "upload.pdf")
            )
            if not safe_filename.lower().endswith(".pdf"):
                safe_filename += ".pdf"
            dest_path = webui_upload_dir / f"{doc_id}_{safe_filename}"

            # Read the uploaded file content and write to the destination
            try:
                # Ensure we read from the start
                try:
                    await file.seek(0)
                except Exception:
                    pass

                content_bytes = await file.read()
                with open(dest_path, "wb") as fdest:
                    fdest.write(content_bytes)
            except Exception as e:
                logger.exception(
                    "Failed to save uploaded file to webui uploads dir: %s", e
                )
                return JSONResponse(
                    status_code=500,
                    content={
                        "status": "error",
                        "message": "Failed to store uploaded file",
                    },
                )

            # Create a simple file-like wrapper for pdf_processor
            class _SimpleUpload:
                def __init__(self, filename: str, content: bytes):
                    self.filename = filename
                    self.file = BytesIO(content)

            try:
                result = pdf_processor.process_uploaded_pdf(
                    _SimpleUpload(file.filename, content_bytes)
                )
            except Exception as e:
                logger.exception("PDF processing failed: %s", e)
                return JSONResponse(
                    status_code=500, content={"status": "error", "message": str(e)}
                )

            # Log result keys (avoid logging full text for privacy)
            try:
                logger.info(
                    f"[{client_ip}] PDF processor returned keys: {list(result.keys())}"
                )
            except Exception:
                logger.info(
                    f"[{client_ip}] PDF processor returned a non-dict result: {type(result)}"
                )

            logger.info(
                f"[{client_ip}] PDF uploaded: {result.get('pages_processed')} pages, {result.get('word_count')} words"
            )

            # Persist document metadata and create analysis job record
            try:
                from home_ai.finance_agent.src import storage as fa_storage
            except Exception:
                import sys
                from pathlib import Path
                import importlib

                # Add the finance-agent src directory to sys.path as a fallback
                fa_src_path = (
                    Path(__file__).resolve().parents[1] / "finance-agent" / "src"
                )
                if str(fa_src_path) not in sys.path:
                    sys.path.insert(0, str(fa_src_path))

                # Import the storage module directly from the finance-agent src
                fa_storage = importlib.import_module("storage")

            fa_storage.save_document(
                doc_id,
                result.get("filename"),
                result.get("pages_processed", 0),
                result.get("file_size_bytes", 0),
            )

            # Create a job id and create analysis job record (pending consent)
            job_id = f"job-{doc_id}-{uuid.uuid4().hex[:6]}"
            fa_storage.create_analysis_job(job_id, doc_id, status="pending")

            payload = {
                "status": "UPLOADED",
                "doc_id": doc_id,
                "job_id": job_id,
                "file_id": str(uuid.uuid4()),
                "filename": result.get("filename"),
                "pages": result.get("pages_processed"),
                "bytes": result.get("file_size_bytes", 0),
            }

            # Track document in session for context injection
            session_id = _get_session_id(request)
            _add_pending_document(
                session_id,
                {
                    "filename": result.get("filename"),
                    "pages": result.get("pages_processed", 0),
                    "size_kb": round(result.get("file_size_bytes", 0) / 1024, 1),
                    "upload_time": datetime.utcnow().isoformat(),
                    "detected_type": "financial_document",
                    "doc_id": doc_id,
                },
            )

            logger.info(
                f"[{client_ip}] PDF uploaded: {result.get('pages_processed')} pages, {result.get('word_count')} words"
            )

            # Build document context for LLM response generation
            document_context = {
                "documents": [
                    {
                        "doc_id": doc_id,
                        "filename": result.get("filename"),
                        "pages": result.get("pages_processed", 0),
                        "size_kb": round(result.get("file_size_bytes", 0) / 1024, 1),
                        "upload_time": datetime.utcnow().isoformat(),
                        "detected_type": "financial_document",
                        "preview_text": result.get("text_preview", "")[:500]
                        if result.get("text_preview")
                        else "",
                    }
                ],
                "session_id": session_id,
            }

            # Get LLM-generated response for the upload
            # This follows the LLM-Driven Responses principle (see RemAssist/LLM_DRIVEN_RESPONSES.md)
            agent_response = None
            try:
                agent = SOA1Agent()
                agent_result = agent.ask(
                    query=f"I just uploaded a document: {result.get('filename')}",
                    document_context=document_context,
                )
                agent_response = agent_result.get("answer", "")
                logger.info(
                    f"[{client_ip}] LLM generated upload response ({len(agent_response)} chars)"
                )
            except Exception as e:
                logger.warning(
                    f"[{client_ip}] Failed to get LLM response for upload: {e}"
                )
                # Graceful degradation - continue without LLM response

            payload["agent_response"] = agent_response
            return JSONResponse(content=payload)

        except Exception as e:
            # Log full stack trace for debugging
            logger.exception(f"PDF upload failed: {e}")
            return JSONResponse(
                status_code=500, content={"status": "error", "message": str(e)}
            )

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

    return app


if __name__ == "__main__":
    with open("config.yaml", "r") as f:
        cfg = yaml.safe_load(f)
    host = cfg["server"]["host"]
    port = int(cfg["server"]["port"])

    uvicorn.run("api:create_app", host=host, port=port, reload=False, factory=True)
