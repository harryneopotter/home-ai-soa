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

    def extract_quick_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Extract quick metadata from PDF for immediate response (target: <500ms).
        Returns filename, size, page count, first 10 lines, inferred document type.
        Does NOT do full text extraction or PII redaction.
        """
        import time

        start_time = time.time()

        try:
            file_size_bytes = os.path.getsize(file_path)

            with open(file_path, "rb") as file:
                reader = PyPDF2.PdfReader(file)
                num_pages = len(reader.pages)

                header_lines = []
                if num_pages > 0:
                    first_page_text = reader.pages[0].extract_text() or ""
                    header_lines = first_page_text.splitlines()[:10]

                inferred_type = self._infer_document_type(
                    header_lines, os.path.basename(file_path)
                )

            elapsed_ms = (time.time() - start_time) * 1000
            logger.info(
                f"Quick metadata extracted in {elapsed_ms:.0f}ms: {num_pages} pages, type={inferred_type}"
            )

            return {
                "status": "success",
                "file_size_bytes": file_size_bytes,
                "pages": num_pages,
                "header_lines": header_lines,
                "inferred_type": inferred_type,
                "extraction_time_ms": elapsed_ms,
            }

        except Exception as e:
            logger.error(f"Quick metadata extraction failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "file_size_bytes": 0,
                "pages": 0,
                "header_lines": [],
                "inferred_type": "unknown",
            }

    def _infer_document_type(self, header_lines: list, filename: str) -> str:
        """Infer document type from header content and filename."""
        header_text = " ".join(header_lines).lower()
        filename_lower = filename.lower()

        BANK_KEYWORDS = [
            "statement",
            "account",
            "balance",
            "transaction",
            "deposit",
            "withdrawal",
        ]
        BANK_NAMES = [
            "chase",
            "wells fargo",
            "bank of america",
            "citi",
            "capital one",
            "goldman sachs",
            "apple card",
        ]
        CC_KEYWORDS = [
            "credit card",
            "card statement",
            "minimum payment",
            "credit limit",
            "apr",
        ]
        INVOICE_KEYWORDS = ["invoice", "bill", "amount due", "payment due", "total due"]
        UTILITY_KEYWORDS = [
            "utility",
            "electric",
            "gas",
            "water",
            "internet",
            "cable",
            "phone",
        ]

        if any(kw in header_text for kw in CC_KEYWORDS) or "card" in filename_lower:
            return "credit_card_statement"

        if any(bank in header_text for bank in BANK_NAMES) or any(
            kw in header_text for kw in BANK_KEYWORDS
        ):
            return "bank_statement"

        if any(kw in header_text for kw in UTILITY_KEYWORDS):
            return "utility_bill"

        if any(kw in header_text for kw in INVOICE_KEYWORDS):
            return "invoice"

        if any(kw in header_text for kw in ["$", "amount", "total", "payment"]):
            return "financial_document"

        return "document"

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
