"""File validation utilities for upload endpoints."""

from fastapi import UploadFile
from typing import Tuple
import logging

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf"}
ALLOWED_MIME_TYPES = {"application/pdf", "application/x-pdf"}
PDF_MAGIC_BYTES = b"%PDF-"
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024


class FileValidationError(Exception):
    """Raised when file validation fails."""

    def __init__(self, message: str, filename: str = None):
        self.message = message
        self.filename = filename
        super().__init__(message)


async def validate_pdf_upload(file: UploadFile) -> Tuple[bytes, dict]:
    """
    Validate uploaded file is a legitimate PDF.

    Raises:
        FileValidationError: If validation fails
    """
    filename = file.filename or "unknown"

    if not filename or filename.strip() == "":
        raise FileValidationError("No filename provided", filename)

    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise FileValidationError(
            f"Invalid file type '{ext}'. Only PDF files are accepted.", filename
        )

    content_type = file.content_type or ""
    if content_type and content_type not in ALLOWED_MIME_TYPES:
        logger.warning(
            f"Suspicious MIME type '{content_type}' for '{filename}'. "
            f"Proceeding with magic byte check."
        )

    try:
        await file.seek(0)
    except Exception:
        pass
    content_bytes = await file.read()

    if len(content_bytes) > MAX_FILE_SIZE_BYTES:
        raise FileValidationError(
            f"File too large ({len(content_bytes) / 1024 / 1024:.1f}MB). Maximum is 10MB.",
            filename,
        )

    if len(content_bytes) == 0:
        raise FileValidationError("File is empty (0 bytes).", filename)

    if not content_bytes.startswith(PDF_MAGIC_BYTES):
        header_preview = content_bytes[:20].decode("utf-8", errors="replace")
        raise FileValidationError(
            f"Invalid PDF. Expected PDF header, got: '{header_preview}...'", filename
        )

    validation_info = {
        "filename": filename,
        "size_bytes": len(content_bytes),
        "content_type": content_type,
        "extension": ext,
        "has_valid_header": True,
    }

    logger.info(f"PDF validation passed: '{filename}' ({len(content_bytes)} bytes)")

    return content_bytes, validation_info


def validate_pdf_bytes(content_bytes: bytes, filename: str = "unknown") -> dict:
    """
    Synchronous validation for already-read file content.

    Raises:
        FileValidationError: If validation fails
    """
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise FileValidationError(
            f"Invalid file type '{ext}'. Only PDF files are accepted.", filename
        )

    if len(content_bytes) > MAX_FILE_SIZE_BYTES:
        raise FileValidationError(
            f"File too large ({len(content_bytes) / 1024 / 1024:.1f}MB). Maximum is 10MB.",
            filename,
        )

    if len(content_bytes) == 0:
        raise FileValidationError("File is empty (0 bytes).", filename)

    if not content_bytes.startswith(PDF_MAGIC_BYTES):
        header_preview = content_bytes[:20].decode("utf-8", errors="replace")
        raise FileValidationError(
            f"Invalid PDF. Expected PDF header, got: '{header_preview}...'", filename
        )

    return {
        "filename": filename,
        "size_bytes": len(content_bytes),
        "extension": ext,
        "has_valid_header": True,
    }
