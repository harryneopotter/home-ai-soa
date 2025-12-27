"""Finance statement parser with staged awareness for Nemotron + Phinance pipeline."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import pdfplumber

try:
    from .models import call_nemotron, call_phinance_insights
    from .storage import get_merchant_mapping
    from .sanitizer import (
        sanitize_phinance_response,
        clean_merchant_name,
        categorize_merchant,
        build_analysis_from_transactions,
    )
except ImportError:
    from models import call_nemotron, call_phinance_insights
    from storage import get_merchant_mapping
    from sanitizer import (
        sanitize_phinance_response,
        clean_merchant_name,
        categorize_merchant,
        build_analysis_from_transactions,
    )


@dataclass
class IdentityContext:
    doc_id: str
    filename: str
    pages: int
    file_size_bytes: int
    statement_type: str
    header_lines: List[str]
    account_holder: Optional[str]
    account_identifier: Optional[str]
    institution: Optional[str]


@dataclass
class StructuralSummary:
    doc_id: str
    synopsis: str
    key_sections: List[str]
    timeframe: Optional[str]


@dataclass
class ExtractionResult:
    doc_id: str
    method: str
    transactions: List[Dict[str, Any]]
    phinance_payload: Dict[str, Any]
    phinance_raw_response: str
    phinance_structured_response: Optional[Dict[str, Any]]


class FinanceStatementParser:
    APPLE_CARD_REGEX = re.compile(
        r"(?P<date>\d{2}/\d{2}/\d{4})\s+(?P<merchant>.+?)\s+\$(?P<amount>[0-9,]+\.\d{2})$",
        re.MULTILINE,
    )

    GENERIC_BANK_REGEX = re.compile(
        r"(?P<date>\d{2}/\d{2}(?:/\d{4})?)\s+(?P<merchant>[A-Za-z0-9 .,&'*-]+?)\s+(?P<amount>-?[0-9,]+\.\d{2})",
        re.MULTILINE,
    )

    def __init__(self, max_preview_chars: int = 3200) -> None:
        self.max_preview_chars = max_preview_chars

    async def get_identity_context(
        self, pdf_path: Path, doc_id: str
    ) -> IdentityContext:
        with pdfplumber.open(pdf_path) as pdf:
            header_lines: List[str] = []
            if pdf.pages:
                header_lines = (pdf.pages[0].extract_text() or "").splitlines()[:10]

            full_text = self._concatenate_pages(pdf)

        statement_type = self._detect_statement_type(header_lines, full_text)
        account_holder = self._extract_account_holder(header_lines)
        account_identifier = self._extract_account_identifier(header_lines)
        institution = self._detect_institution(header_lines)

        return IdentityContext(
            doc_id=doc_id,
            filename=pdf_path.name,
            pages=self._count_pages(pdf_path),
            file_size_bytes=pdf_path.stat().st_size,
            statement_type=statement_type,
            header_lines=header_lines,
            account_holder=account_holder,
            account_identifier=account_identifier,
            institution=institution,
        )

    async def get_structural_summary(
        self, identity: IdentityContext, pdf_path: Path
    ) -> StructuralSummary:
        full_text = self._extract_text(pdf_path)
        preview = full_text[: self.max_preview_chars]

        prompt = (
            "You are a finance document analyst. Summarize the structure of the"
            " provided statement without extracting transactions yet."
            "\n- Identify the billing period or date range."
            "\n- List the major sections you observe in order."
            "\n- Mention the document type you believe it is."
            "\nRespond in concise bullet points so a user can consent to extraction."
            "\n\nContext:"
            f"\n- Filename: {identity.filename}"
            f"\n- Pages: {identity.pages}"
            f"\n- Statement type guess: {identity.statement_type}"
            f"\n- Header lines: {identity.header_lines[:3]}"
            "\n\nPreview:"
            f"\n{preview}"
        )

        summary_text = await call_nemotron(prompt)
        key_sections = self._extract_bullets(summary_text)
        timeframe = self._extract_timeframe(summary_text)

        return StructuralSummary(
            doc_id=identity.doc_id,
            synopsis=summary_text.strip(),
            key_sections=key_sections,
            timeframe=timeframe,
        )

    async def extract_transactions(
        self, identity: IdentityContext, summary: StructuralSummary, pdf_path: Path
    ) -> ExtractionResult:
        full_text = self._extract_text(pdf_path)
        regex_transactions = self._regex_extract(full_text, identity.statement_type)
        method = "regex"
        transactions = [self._enrich_with_dictionary(tx) for tx in regex_transactions]

        if not transactions:
            method = "nemotron_fallback"
            transactions = await self._nemotron_extract(full_text, identity)

        client_analysis = build_analysis_from_transactions(
            transactions, identity.doc_id
        )

        import sys
        import logging

        logger = logging.getLogger("parser")

        phinance_raw = ""
        try:
            logger.warning(
                f"[PHINANCE] Calling with summary: total_spent={client_analysis.get('total_spent')}"
            )
            sys.stdout.flush()
            phinance_raw = await call_phinance_insights(client_analysis)
            logger.warning(
                f"[PHINANCE] Raw response length={len(phinance_raw)}: {phinance_raw[:300]}..."
            )
            sys.stdout.flush()
            sanitization_result = sanitize_phinance_response(phinance_raw)
            logger.warning(
                f"[PHINANCE] Sanitization success={sanitization_result.success}"
            )
            logger.warning(
                f"[PHINANCE] Sanitization errors={sanitization_result.errors}"
            )
            logger.warning(f"[PHINANCE] Sanitization data={sanitization_result.data}")
            sys.stdout.flush()
            if sanitization_result.success and sanitization_result.data:
                analysis_data = sanitization_result.data.get("analysis", {})
                logger.warning(
                    f"[PHINANCE] analysis_data keys: {list(analysis_data.keys()) if analysis_data else 'None'}"
                )
                if analysis_data.get("insights"):
                    client_analysis["insights"] = analysis_data["insights"]
                    logger.warning(
                        f"[PHINANCE] Added insights: {analysis_data['insights']}"
                    )
                if analysis_data.get("recommendations"):
                    client_analysis["recommendations"] = analysis_data[
                        "recommendations"
                    ]
                    logger.warning(
                        f"[PHINANCE] Added recommendations: {analysis_data['recommendations']}"
                    )
                if analysis_data.get("potential_savings"):
                    client_analysis["potential_savings"] = analysis_data[
                        "potential_savings"
                    ]
                sys.stdout.flush()
        except Exception as e:
            import traceback

            logger.error(f"[PHINANCE] Call failed: {type(e).__name__}: {e}")
            logger.error(traceback.format_exc())
            sys.stdout.flush()

        return ExtractionResult(
            doc_id=identity.doc_id,
            method=method,
            transactions=transactions,
            phinance_payload={"summary_sent": True},
            phinance_raw_response=phinance_raw,
            phinance_structured_response=client_analysis,
        )

        phinance_raw = ""
        structured_response = client_analysis
        try:
            payload = {
                "identity": {
                    "doc_id": identity.doc_id,
                    "filename": identity.filename,
                    "account_holder": identity.account_holder,
                    "account_identifier": identity.account_identifier,
                    "institution": identity.institution,
                    "statement_type": identity.statement_type,
                },
                "structural_summary": summary.synopsis,
                "transactions": transactions[:50],
            }
            phinance_raw = await call_phinance(json.dumps(payload))
            sanitization_result = sanitize_phinance_response(phinance_raw)
            if sanitization_result.success and sanitization_result.data:
                if sanitization_result.data.get("analysis"):
                    structured_response["phinance_insights"] = sanitization_result.data[
                        "analysis"
                    ]
        except Exception:
            pass

        return ExtractionResult(
            doc_id=identity.doc_id,
            method=method,
            transactions=transactions,
            phinance_payload={"transaction_count": len(transactions)},
            phinance_raw_response=phinance_raw,
            phinance_structured_response=structured_response,
        )

    def _count_pages(self, pdf_path: Path) -> int:
        with pdfplumber.open(pdf_path) as pdf:
            return len(pdf.pages)

    def _extract_text(self, pdf_path: Path) -> str:
        with pdfplumber.open(pdf_path) as pdf:
            return self._concatenate_pages(pdf)

    def _concatenate_pages(self, pdf: pdfplumber.PDF) -> str:
        chunks: List[str] = []
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text.strip():
                chunks.append(text)
        return "\n".join(chunks)

    def _detect_statement_type(
        self, header_lines: Sequence[str], full_text: str
    ) -> str:
        header_blob = " ".join(header_lines).upper()
        text_upper = full_text.upper()
        if "APPLE CARD" in header_blob or "GOLDMAN SACHS" in header_blob:
            return "apple_card"
        if "CHASE" in header_blob:
            return "chase"
        if "BANK OF AMERICA" in header_blob or "B OF A" in header_blob:
            return "boa"
        if "AMERICAN EXPRESS" in header_blob:
            return "amex"
        if "WELLS FARGO" in header_blob:
            return "wells_fargo"
        if "CITI" in header_blob:
            return "citi"
        if "STATEMENT" in header_blob or "ACCOUNT" in header_blob:
            return "generic_statement"
        if "APPLE" in text_upper:
            return "apple_card"
        return "unknown"

    def _detect_institution(self, header_lines: Sequence[str]) -> Optional[str]:
        header_blob = " ".join(header_lines).upper()
        candidates = [
            "APPLE CARD",
            "CHASE",
            "BANK OF AMERICA",
            "AMERICAN EXPRESS",
            "WELLS FARGO",
            "CITI",
        ]
        for candidate in candidates:
            if candidate in header_blob:
                return candidate.title()
        return None

    def _extract_account_holder(self, header_lines: Sequence[str]) -> Optional[str]:
        for line in header_lines:
            if line.strip().lower().startswith("account holder"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip()
        return None

    def _extract_account_identifier(self, header_lines: Sequence[str]) -> Optional[str]:
        pattern = re.compile(r"account\s+(number|id|ending)\s*[:#]?\s*(\w+)", re.I)
        for line in header_lines:
            match = pattern.search(line)
            if match:
                return match.group(2)
        return None

    def _regex_extract(self, text: str, statement_type: str) -> List[Dict[str, Any]]:
        pattern = (
            self.APPLE_CARD_REGEX
            if statement_type == "apple_card"
            else self.GENERIC_BANK_REGEX
        )
        results: List[Dict[str, Any]] = []
        for match in pattern.finditer(text):
            amount_str = match.group("amount").replace("$", "").replace(",", "")
            try:
                amount = float(amount_str)
            except ValueError:
                continue
            raw_merchant = match.group("merchant").strip()
            cleaned_merchant = clean_merchant_name(raw_merchant)
            category = categorize_merchant(cleaned_merchant)
            entry = {
                "date": match.group("date"),
                "merchant": cleaned_merchant,
                "amount": amount,
                "category": category,
                "raw_line": match.group(0).strip(),
            }
            results.append(entry)
        return results

    async def _nemotron_extract(
        self, text: str, identity: IdentityContext
    ) -> List[Dict[str, Any]]:
        chunks = self._chunk_text(text, 2800)
        aggregated: List[Dict[str, Any]] = []
        for chunk in chunks[:3]:
            prompt = (
                "Extract ALL transactions from the following statement chunk."
                ' Return ONLY valid JSON array with {"date":"MM/DD", "merchant":"", "amount":-45.23, "description":""}.'
                " Do not explain."
                f"\nDocument: {identity.filename}"
                f"\nChunk:\n{chunk}"
            )

            response = await call_nemotron(prompt)
            parsed = self._safe_load_json(response)
            if isinstance(parsed, list):
                aggregated.extend(parsed)
        return aggregated

    def _chunk_text(self, text: str, size: int) -> List[str]:
        return [text[i : i + size] for i in range(0, len(text), size)]

    def _extract_bullets(self, summary_text: str) -> List[str]:
        bullets: List[str] = []
        for line in summary_text.splitlines():
            stripped = line.strip(" -•\t")
            if not stripped:
                continue
            bullets.append(stripped)
        return bullets[:10]

    def _extract_timeframe(self, summary_text: str) -> Optional[str]:
        match = re.search(
            r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}",
            summary_text,
            re.I,
        )
        if match:
            return match.group(0)
        match = re.search(r"\d{2}/\d{2}/\d{4}", summary_text)
        if match:
            return match.group(0)
        return None

    def _safe_load_json(self, payload: str) -> Optional[Any]:
        snippet = payload.strip()
        fences = ["```json", "```", "{", "["]
        for fence in fences:
            if fence in snippet and fence.startswith("`"):
                snippet = snippet.split(fence, 1)[-1]
        snippet = snippet.strip("`\n ")
        try:
            return json.loads(snippet)
        except json.JSONDecodeError:
            return None

    def _enrich_with_dictionary(self, tx: Dict[str, Any]) -> Dict[str, Any]:
        mapping = get_merchant_mapping(tx.get("merchant", ""))
        if mapping:
            tx = {**tx}
            tx["normalized_merchant"] = mapping["normalized_name"]
            tx["merchant_confidence"] = mapping["confidence"]
        return tx


__all__ = [
    "FinanceStatementParser",
    "IdentityContext",
    "StructuralSummary",
    "ExtractionResult",
]
