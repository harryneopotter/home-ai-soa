from fastapi import FastAPI, HTTPException, Response, UploadFile, File, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any
import yaml
import uvicorn
import os
import uuid
from datetime import datetime
import time

from agent import SOA1Agent
from pdf_processor import pdf_processor
from utils.logger import get_logger
from utils.errors import SOA1Error, ValidationError, ServiceError, InternalError, RateLimitError
from utils.rate_limiter import get_limiter_for_endpoint

logger = get_logger("api")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    query: str


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


# Enhanced request models with validation
class AskRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    
    @validator('query')
    def validate_query_content(cls, v):
        if v.strip() == '':
            raise ValueError("Query cannot be empty or whitespace only")
        if len(v.encode('utf-8')) > 2000:  # Byte length check
            raise ValueError("Query too long (max 2000 bytes)")
        return v


class PDFUploadRequest(BaseModel):
    max_pages: Optional[int] = Field(10, ge=1, le=50)


class PDFAnalysisRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    pdf_id: str = Field(..., min_length=1, max_length=50)
    top_k: Optional[int] = Field(5, ge=1, le=20)


# Error handlers
@app.exception_handler(SOA1Error)
async def soa1_error_handler(request: Request, exc: SOA1Error):
    """Standardized error response format"""
    error_id = str(uuid.uuid4())
    logger.error(f"API Error [{error_id}]: {exc.error_code} - {exc.detail['message']}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.error_code,
            "message": exc.detail['message'],
            "details": exc.detail.get('details', {}),
            "error_id": error_id,
            "timestamp": datetime.utcnow().isoformat()
        }
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
            "timestamp": datetime.utcnow().isoformat()
        }
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
            "timestamp": datetime.utcnow().isoformat()
        }
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


def create_app() -> FastAPI:
    app = FastAPI(title="SOA1 Agent API", version="0.1.0")
    agent = SOA1Agent()

    @app.post("/ask", response_model=AskResponse)
    def ask(req: AskRequest):
        """Main query endpoint with enhanced error handling"""
        client_ip = req.client.host
        logger.info(f"[{client_ip}] /ask called with query: {req.query[:50]}...")
        
        try:
            # Validate input
            if not req.query or not isinstance(req.query, str):
                raise ValidationError("Query must be a non-empty string", "query", req.query)
            
            result = agent.ask(req.query)
            logger.info(f"[{client_ip}] Agent response generated successfully")
            
            return AskResponse(
                answer=result["answer"],
                used_memories=result["used_memories"],
                audio_path=result.get("audio_path"),
                audio_duration=result.get("audio_duration"),
                tts_error=result.get("tts_error")
            )
            
        except ValidationError:
            raise  # Re-raise validation errors
        except Exception as e:
            logger.error(f"[{client_ip}] Agent processing failed: {e}", exc_info=True)
            raise InternalError(f"Query processing failed: {str(e)}")

    @app.post("/ask-with-tts", response_model=TTSResponse)
    def ask_with_tts(req: AskRequest):
        """Ask and get TTS response with enhanced error handling"""
        client_ip = req.client.host
        logger.info(f"[{client_ip}] /ask-with-tts called with query: {req.query[:50]}...")
        
        try:
            result = agent.ask_with_tts(req.query)
            
            if "audio_path" not in result or not result["audio_path"]:
                logger.warning(f"[{client_ip}] TTS not available or failed")
                raise ServiceError("tts", "TTS generation failed or not enabled")
            
            logger.info(f"[{client_ip}] TTS response generated successfully")
            return TTSResponse(
                audio_path=result["audio_path"],
                duration=result["audio_duration"],
                answer=result["answer"]
            )
            
        except ServiceError:
            raise  # Re-raise service errors
        except Exception as e:
            logger.error(f"[{client_ip}] TTS processing failed: {e}", exc_info=True)
            raise InternalError(f"TTS processing failed: {str(e)}")

    @app.get("/audio/{audio_file}")
    def get_audio(audio_file: str):
        """Serve audio files with enhanced error handling"""
        client_ip = req.client.host
        
        try:
            # Validate filename
            if not audio_file or not isinstance(audio_file, str):
                raise ValidationError("Invalid audio file name", "audio_file", audio_file)
            
            if not audio_file.endswith('.wav'):
                raise ValidationError("Only WAV files are supported", "audio_file", audio_file)
            
            audio_path = os.path.join("/tmp/soa1_tts", audio_file)
            
            if not os.path.exists(audio_path):
                logger.warning(f"[{client_ip}] Audio file not found: {audio_file}")
                raise NotFoundError("audio_file", audio_file)
            
            logger.info(f"[{client_ip}] Serving audio file: {audio_file}")
            return Response(
                content=open(audio_path, "rb").read(),
                media_type="audio/wav",
                headers={"Content-Disposition": f"inline; filename={audio_file}"}
            )
            
        except ValidationError:
            raise  # Re-raise validation errors
        except Exception as e:
            logger.error(f"[{client_ip}] Audio file error: {e}", exc_info=True)
            raise InternalError(f"Failed to serve audio file: {str(e)}")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


if __name__ == "__main__":
    with open("config.yaml", "r") as f:
        cfg = yaml.safe_load(f)
    host = cfg["server"]["host"]
    port = int(cfg["server"]["port"])

    uvicorn.run("api:create_app", host=host, port=port,
                reload=False, factory=True)


# PDF Processing Endpoints (for demo)
@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    """Upload and process PDF document with enhanced error handling"""
    client_ip = req.client.host
    logger.info(f"[{client_ip}] PDF upload requested: {file.filename}")
    
    try:
        # Validate file
        if not file or not file.filename:
            raise ValidationError("No file provided", "file", "None")
        
        if not file.filename.lower().endswith('.pdf'):
            raise ValidationError("Only PDF files are accepted", "file", file.filename)
        
        if file.size > 10 * 1024 * 1024:  # 10MB limit
            raise ValidationError("File too large (max 10MB)", "file", file.filename)
        
        # Process the PDF
        result = pdf_processor.process_uploaded_pdf(file)
        
        # Generate summary
        summary = pdf_processor.generate_summary(result["full_text"])
        
        logger.info(f"[{client_ip}] PDF processed: {result['pages_processed']} pages, {result['word_count']} words")
        
        return {
            "status": "success",
            "filename": result["filename"],
            "pages_processed": result["pages_processed"],
            "word_count": result["word_count"],
            "summary": summary,
            "preview": result["text_preview"]
        }
    
    except Exception as e:
        logger.error(f"PDF processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze-pdf")
async def analyze_pdf(
    query: str = "Summarize the key points",
    text: str = None,
    file: UploadFile = None
):
    """Analyze PDF content using SOA1 agent with enhanced error handling"""
    client_ip = req.client.host
    logger.info(f"[{client_ip}] PDF analysis requested: {query[:50]}...")
    
    try:
        # Validate input
        if not query or not isinstance(query, str):
            raise ValidationError("Query must be a non-empty string", "query", query)
        
        # Get text from file or use provided text
        if file:
            if not file.filename.lower().endswith('.pdf'):
                raise ValidationError("Only PDF files are accepted", "file", file.filename)
            
            if file.size > 10 * 1024 * 1024:  # 10MB limit
                raise ValidationError("File too large (max 10MB)", "file", file.filename)
            
            result = pdf_processor.process_uploaded_pdf(file)
            analysis_text = result["full_text"]
        elif text:
            if not text or not isinstance(text, str):
                raise ValidationError("Text must be a non-empty string", "text", text)
            analysis_text = text
        else:
            raise ValidationError("Either file or text must be provided", "input", "none")
        
        # Create analysis prompt
        analysis_prompt = (
            f"Document Content:\n"
            f"{analysis_text[:2000]}{'...' if len(analysis_text) > 2000 else ''}\n\n"
            f"User Query: {query}\n\n"
            f"Please provide a concise analysis or summary."
        )
        
        # Use SOA1 agent for analysis
        agent = SOA1Agent()  # Create agent instance
        analysis_result = agent.ask(analysis_prompt)
        
        logger.info(f"[{client_ip}] PDF analysis completed successfully")
        
        return {
            "status": "success",
            "query": query,
            "analysis": analysis_result["answer"],
            "word_count": len(analysis_text.split()),
            "analysis_type": "agent-based"
        }
    
    except ValidationError:
        raise  # Re-raise validation errors
    except Exception as e:
        logger.error(f"[{client_ip}] PDF analysis failed: {e}", exc_info=True)
        raise InternalError(f"PDF analysis failed: {str(e)}")

