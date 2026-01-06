# PDF Upload Validation Implementation Plan

**Created**: January 6, 2026  
**Status**: PLANNING  
**Priority**: HIGH - Security & Data Integrity

---

## Problem Statement

Resilience testing revealed that the upload pipeline accepts **any file type** without validation:

| Test | File Type | Result | Risk |
|------|-----------|--------|------|
| Non-PDF (.md) | Markdown | **Accepted** | Data pollution, wasted processing |
| Empty .pdf | 0 bytes | Accepted | Graceful handling (OK) |
| Fake .pdf (text) | Text with .pdf extension | **Accepted** | False positives in analysis |
| Binary garbage .pdf | Random bytes | Detected as 0 pages | Graceful (OK) |

### Current Vulnerabilities

1. **No file extension validation** in `/upload-batch` endpoint
2. **No MIME type checking** - `content_type` ignored
3. **No PDF magic byte validation** - Files without `%PDF-` header processed
4. **WebUI proxy passes anything through** without validation

---

## Affected Files

| File | Endpoint | Current Validation | Needs Fix |
|------|----------|-------------------|-----------|
| `home-ai/soa1/api.py` | `/upload-batch` (line 548) | Size only | YES |
| `home-ai/soa1/api.py` | `/upload-pdf` (line 752) | Extension + size | PARTIAL (add magic bytes) |
| `soa-webui/main.py` | `/api/proxy/upload` (line 1563) | None | YES |
| `soa-webui/main.py` | `/api/proxy/upload-batch` (line 1597) | None | YES |

---

## Implementation Plan

### Phase 1: Create Shared Validation Utility

**File**: `home-ai/soa1/utils/file_validation.py` (NEW)

```python
"""File validation utilities for upload endpoints."""

from fastapi import HTTPException, UploadFile
from typing import Tuple
import logging

logger = logging.getLogger(__name__)

# Constants
ALLOWED_EXTENSIONS = {'.pdf'}
ALLOWED_MIME_TYPES = {'application/pdf', 'application/x-pdf'}
PDF_MAGIC_BYTES = b'%PDF-'
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

class FileValidationError(Exception):
    """Raised when file validation fails."""
    def __init__(self, message: str, filename: str = None):
        self.message = message
        self.filename = filename
        super().__init__(message)


async def validate_pdf_upload(file: UploadFile) -> Tuple[bytes, dict]:
    """
    Validate that an uploaded file is a legitimate PDF.
    
    Args:
        file: FastAPI UploadFile object
        
    Returns:
        Tuple of (file_bytes, validation_info)
        
    Raises:
        FileValidationError: If validation fails
    """
    filename = file.filename or "unknown"
    
    # 1. Check filename exists
    if not filename or filename.strip() == "":
        raise FileValidationError("No filename provided", filename)
    
    # 2. Check file extension
    ext = '.' + filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext not in ALLOWED_EXTENSIONS:
        raise FileValidationError(
            f"Invalid file type '{ext}'. Only PDF files are accepted.",
            filename
        )
    
    # 3. Check MIME type (warning only - browsers can lie)
    content_type = file.content_type or ""
    if content_type and content_type not in ALLOWED_MIME_TYPES:
        logger.warning(
            f"Suspicious MIME type '{content_type}' for file '{filename}'. "
            f"Expected application/pdf. Proceeding with magic byte check."
        )
    
    # 4. Read file content
    try:
        await file.seek(0)
    except Exception:
        pass
    content_bytes = await file.read()
    
    # 5. Check file size
    if len(content_bytes) > MAX_FILE_SIZE:
        raise FileValidationError(
            f"File too large ({len(content_bytes) / 1024 / 1024:.1f}MB). Maximum size is 10MB.",
            filename
        )
    
    # 6. Check for empty file
    if len(content_bytes) == 0:
        raise FileValidationError(
            "File is empty (0 bytes).",
            filename
        )
    
    # 7. Check PDF magic bytes (CRITICAL)
    if not content_bytes.startswith(PDF_MAGIC_BYTES):
        # Provide helpful error message
        header_preview = content_bytes[:20].decode('utf-8', errors='replace')
        raise FileValidationError(
            f"File does not appear to be a valid PDF. "
            f"Expected PDF header, got: '{header_preview}...'",
            filename
        )
    
    validation_info = {
        "filename": filename,
        "size_bytes": len(content_bytes),
        "content_type": content_type,
        "extension": ext,
        "has_valid_header": True
    }
    
    logger.info(f"PDF validation passed for '{filename}' ({len(content_bytes)} bytes)")
    
    return content_bytes, validation_info


def validate_pdf_bytes(content_bytes: bytes, filename: str = "unknown") -> dict:
    """
    Synchronous validation for already-read file content.
    
    Args:
        content_bytes: Raw file bytes
        filename: Original filename for error messages
        
    Returns:
        Validation info dict
        
    Raises:
        FileValidationError: If validation fails
    """
    # Check file extension
    ext = '.' + filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext not in ALLOWED_EXTENSIONS:
        raise FileValidationError(
            f"Invalid file type '{ext}'. Only PDF files are accepted.",
            filename
        )
    
    # Check size
    if len(content_bytes) > MAX_FILE_SIZE:
        raise FileValidationError(
            f"File too large ({len(content_bytes) / 1024 / 1024:.1f}MB). Maximum size is 10MB.",
            filename
        )
    
    # Check empty
    if len(content_bytes) == 0:
        raise FileValidationError("File is empty (0 bytes).", filename)
    
    # Check magic bytes
    if not content_bytes.startswith(PDF_MAGIC_BYTES):
        header_preview = content_bytes[:20].decode('utf-8', errors='replace')
        raise FileValidationError(
            f"File does not appear to be a valid PDF. "
            f"Expected PDF header, got: '{header_preview}...'",
            filename
        )
    
    return {
        "filename": filename,
        "size_bytes": len(content_bytes),
        "extension": ext,
        "has_valid_header": True
    }
```

---

### Phase 2: Update SOA1 API `/upload-batch`

**File**: `home-ai/soa1/api.py` (line ~564)

**Current code**:
```python
for idx, file in enumerate(files):
    try:
        # ... no validation ...
        content_bytes = await file.read()
        if len(content_bytes) > MAX_FILE_SIZE:
            raise ValidationError(...)
```

**New code**:
```python
from soa1.utils.file_validation import validate_pdf_upload, FileValidationError

for idx, file in enumerate(files):
    try:
        emit_pipeline_event(
            "quick_metadata_start",
            details={"file": file.filename, "index": idx + 1},
        )
        
        # NEW: Validate PDF before processing
        try:
            content_bytes, validation_info = await validate_pdf_upload(file)
        except FileValidationError as e:
            logger.warning(f"File validation failed: {e.message}")
            emit_pipeline_event(
                "validation_error",
                details={"file": e.filename, "error": e.message}
            )
            # Skip this file, continue with others
            continue
        
        # ... rest of processing ...
```

---

### Phase 3: Update SOA1 API `/upload-pdf`

**File**: `home-ai/soa1/api.py` (line ~765)

**Current code** (partial validation exists):
```python
if not file.filename.lower().endswith(".pdf"):
    return JSONResponse(status_code=400, ...)
```

**Add magic byte check after reading**:
```python
from soa1.utils.file_validation import validate_pdf_bytes, FileValidationError

# After reading content_bytes:
try:
    validate_pdf_bytes(content_bytes, file.filename)
except FileValidationError as e:
    return JSONResponse(
        status_code=400,
        content={"status": "error", "message": e.message}
    )
```

---

### Phase 4: Update WebUI Proxy Endpoints

**File**: `soa-webui/main.py`

#### `/api/proxy/upload` (line 1563)

**Add validation before forwarding**:
```python
@app.post("/api/proxy/upload")
async def api_proxy_upload(request: Request, file: UploadFile = File(...)):
    """Proxy file upload to SOA1 API."""
    try:
        # NEW: Validate file before proxying
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(
                status_code=400, 
                detail=f"Only PDF files accepted. Got: {file.filename}"
            )
        
        content = await file.read()
        
        # Check magic bytes
        if not content.startswith(b'%PDF-'):
            raise HTTPException(
                status_code=400,
                detail="File does not appear to be a valid PDF"
            )
        
        # ... rest of proxy logic ...
```

#### `/api/proxy/upload-batch` (line 1597)

**Add validation loop**:
```python
@app.post("/api/proxy/upload-batch")
async def api_proxy_upload_batch(request: Request, files: List[UploadFile] = File(...)):
    """Proxy batch file upload to SOA1 API's /upload-batch endpoint."""
    try:
        soa1_url = config.services.get("api", "http://localhost:8001")
        
        # NEW: Validate all files before proxying
        validated_files = []
        validation_errors = []
        
        for file in files:
            filename = file.filename or "unknown"
            
            # Check extension
            if not filename.lower().endswith('.pdf'):
                validation_errors.append(f"{filename}: Not a PDF file")
                continue
            
            content = await file.read()
            
            # Check magic bytes
            if not content.startswith(b'%PDF-'):
                validation_errors.append(f"{filename}: Invalid PDF (bad header)")
                continue
            
            validated_files.append((
                "files",
                (filename, content, "application/pdf")
            ))
        
        # If all files failed validation
        if not validated_files:
            return {
                "status": "ERROR",
                "error": "No valid PDF files",
                "validation_errors": validation_errors,
                "agent_response": "None of the uploaded files are valid PDFs. Please upload PDF files only."
            }
        
        # If some files failed, log warning but continue
        if validation_errors:
            logger.warning(f"Some files failed validation: {validation_errors}")
        
        # ... forward validated_files to SOA1 ...
```

---

## Test Plan

### Test 1: Non-PDF Extension Rejection
```bash
# Should return 400 error
curl -X POST http://localhost:8080/api/proxy/upload-batch \
  -F "files=@/home/ryzen/projects/AGENTS.md"
  
# Expected: {"status": "ERROR", "error": "Not a PDF file"}
```

### Test 2: Fake PDF Rejection (text content)
```bash
echo "This is not a PDF" > /tmp/fake.pdf
curl -X POST http://localhost:8080/api/proxy/upload-batch \
  -F "files=@/tmp/fake.pdf"
  
# Expected: {"status": "ERROR", "error": "Invalid PDF (bad header)"}
```

### Test 3: Binary Garbage Rejection
```bash
dd if=/dev/urandom of=/tmp/garbage.pdf bs=1024 count=10
curl -X POST http://localhost:8080/api/proxy/upload-batch \
  -F "files=@/tmp/garbage.pdf"
  
# Expected: {"status": "ERROR", "error": "Invalid PDF (bad header)"}
```

### Test 4: Valid PDF Still Works
```bash
curl -X POST http://localhost:8080/api/proxy/upload-batch \
  -F "files=@/home/ryzen/Documents/j666/some_valid.pdf"
  
# Expected: {"status": "SUCCESS", "batch_id": "batch-..."}
```

### Test 5: Mixed Batch (some valid, some invalid)
```bash
curl -X POST http://localhost:8080/api/proxy/upload-batch \
  -F "files=@/home/ryzen/Documents/valid.pdf" \
  -F "files=@/home/ryzen/projects/AGENTS.md"
  
# Expected: Process valid.pdf, skip AGENTS.md with warning
```

### Test 6: Empty File Rejection
```bash
touch /tmp/empty.pdf
curl -X POST http://localhost:8080/api/proxy/upload-batch \
  -F "files=@/tmp/empty.pdf"
  
# Expected: {"status": "ERROR", "error": "File is empty"}
```

---

## Rollback Plan

If issues arise:
1. Revert changes to `api.py` and `main.py`
2. Remove `file_validation.py`
3. No database changes required

---

## Success Criteria

- [ ] Non-PDF extensions rejected with 400 status
- [ ] Files without PDF magic bytes rejected
- [ ] Empty files rejected
- [ ] Valid PDFs still process correctly
- [ ] Mixed batches process valid files, skip invalid
- [ ] Clear error messages returned to user
- [ ] No server crashes on malformed input

---

## Implementation Order

1. Create `file_validation.py` utility
2. Update `soa-webui/main.py` proxy endpoints (first line of defense)
3. Update `home-ai/soa1/api.py` endpoints (defense in depth)
4. Run test suite
5. Update NEXT_TASKS.md

---

## Notes

- WebUI validation is "first line of defense" - catches obvious issues early
- SOA1 validation is "defense in depth" - catches anything that slips through
- MIME type is only logged as warning, not rejected (browsers lie about it)
- Magic byte check is the authoritative validation
