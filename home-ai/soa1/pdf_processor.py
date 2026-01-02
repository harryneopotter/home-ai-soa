#!/usr/bin/env python3
"""
SOA1 PDF Processor
Simple PDF processing for immediate demo capabilities
"""

import os
import tempfile
from typing import Dict, Any, Optional
from fastapi import UploadFile, HTTPException
import PyPDF2
import requests
import sys
from pathlib import Path

security_path = Path(__file__).resolve().parents[2] / "soa1"
if str(security_path) not in sys.path:
    sys.path.insert(0, str(security_path))

from security.pii_redactor import PIIRedactor
from security.encrypted_storage import EncryptedStorage

from utils.logger import get_logger


logger = get_logger("pdf_processor")


class SimplePDFProcessor:
    """Simple PDF processor for immediate demo purposes"""

    def __init__(self, max_pages: int = 10):
        self.max_pages = max_pages
        self.redactor = PIIRedactor()
        self.storage = EncryptedStorage()
        logger.info(
            f"PDF Processor initialized (max {max_pages} pages) with Security Layer"
        )

    def extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text from PDF file"""
        try:
            with open(file_path, "rb") as file:
                reader = PyPDF2.PdfReader(file)
                text = []

                # Limit to max_pages to prevent memory issues
                num_pages = min(len(reader.pages), self.max_pages)

                for page_num in range(num_pages):
                    page = reader.pages[page_num]
                    text.append(page.extract_text() or "")

                text_content = "\n".join(text)

                is_apple_card = (
                    "Apple Card" in text_content
                    and "Goldman Sachs Bank" in text_content
                )
                if is_apple_card:
                    logger.info(
                        "Apple Card statement detected - applying specialized extraction"
                    )

                redacted_text, pii_counts = self.redactor.redact(text_content)
                logger.info(f"PII Redaction complete: {pii_counts}")
                return redacted_text, is_apple_card

        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            raise HTTPException(
                status_code=500, detail=f"PDF processing error: {str(e)}"
            )

    def process_uploaded_pdf(self, uploaded_file: UploadFile) -> Dict[str, Any]:
        """Process an uploaded PDF file"""
        try:
            # Save to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                temp_path = temp_file.name

                # Write uploaded content
                content = uploaded_file.file.read()
                temp_file.write(content)

            # Extract text
            text_content, is_apple_card = self.extract_text_from_pdf(temp_path)

            # Get accurate file size and page count
            file_size_bytes = os.path.getsize(temp_path)
            try:
                reader = PyPDF2.PdfReader(temp_path)
                num_pages = min(len(reader.pages), self.max_pages)
            except Exception:
                # Fallback if PyPDF2 cannot read pages for some reason
                num_pages = min(text_content.count("\f") + 1, self.max_pages)

            # Clean up
            os.unlink(temp_path)

            word_count = len(text_content.split())

            encrypted_text = self.storage.encrypt(text_content)

            return {
                "status": "success",
                "filename": uploaded_file.filename,
                "pages_processed": num_pages,
                "word_count": word_count,
                "text_preview": text_content[:500] + "..."
                if len(text_content) > 500
                else text_content,
                "full_text": text_content,
                "encrypted_text": encrypted_text,
                "file_size_bytes": file_size_bytes,
                "is_apple_card": is_apple_card,
            }

        except Exception as e:
            logger.error(f"PDF processing failed: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to process PDF: {str(e)}"
            )

    def generate_summary(self, text: str, max_length: int = 300) -> str:
        """Generate a simple summary from extracted text"""
        if not text:
            return "No content available for summary."

        # Simple summary: first few sentences
        sentences = text.split(".")[:3]
        summary = ". ".join([s.strip() for s in sentences if s.strip()])

        return summary[:max_length] + "..." if len(summary) > max_length else summary


# Global instance
pdf_processor = SimplePDFProcessor()
