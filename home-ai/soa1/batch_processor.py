import time
import uuid
import asyncio
import os
import re
import sys
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
import requests as http_requests
from utils.logger import get_logger

logger = get_logger("batch_processor")

sys.path.insert(0, "/home/ryzen/projects/home-ai/soa1")
sys.path.insert(0, "/home/ryzen/projects")

WEBUI_URL = os.environ.get("WEBUI_URL", "http://localhost:8080")

# Multi-line Apple Card pattern (Date, Merchant, Cashback %, Cashback Amt, Total Amt)
APPLE_CARD_REGEX = re.compile(
    r"^(?P<date>\d{2}/\d{2}/\d{4})\n"
    r"(?P<merchant>[^\n]+)\n"
    r"(?:\d+%\n)?"  # Optional cashback %
    r"(?:\$[\d,.]+\s*\n)?"  # Optional cashback amount
    r"\$(?P<amount>[\d,]+\.\d{2})\s*$",
    re.MULTILINE,
)

GENERIC_BANK_REGEX = re.compile(
    r"(?P<date>\d{2}/\d{2}(?:/\d{4})?)\s+(?P<merchant>[A-Za-z0-9 .,&'*-]+?)\s+(?P<amount>-?[0-9,]+\.\d{2})",
    re.MULTILINE,
)


def _emit_event(event_type: str, batch_id: str = None, details: dict = None):
    try:
        http_requests.post(
            f"{WEBUI_URL}/api/pipeline/event",
            json={"type": event_type, "batch_id": batch_id, "details": details or {}},
            timeout=1,
        )
    except Exception:
        pass


def _regex_extract(text: str, pattern: re.Pattern) -> List[Dict[str, Any]]:
    results = []
    logger.info(f"Running regex extraction on {len(text)} chars of text")

    preview = text[:200].replace("\n", " ")
    logger.debug(f"Extraction text preview: {preview}")

    matches = list(pattern.finditer(text))
    logger.info(f"Found {len(matches)} initial regex matches")

    for match in matches:
        amount_str = match.group("amount").replace("$", "").replace(",", "")
        try:
            amount = float(amount_str)
        except ValueError:
            logger.warning(f"Failed to parse amount: {amount_str}")
            continue
        merchant = match.group("merchant").strip()
        entry = {
            "date": match.group("date"),
            "merchant": merchant,
            "amount": amount,
            "category": _categorize_merchant(merchant),
            "raw_line": match.group(0).strip(),
        }
        results.append(entry)

    logger.info(f"Extraction complete: {len(results)} valid transactions found")
    return results


def _extract_apple_card_transactions(text: str) -> List[Dict[str, Any]]:
    """
    Parse Apple Card multi-line format:
    Line 1: MM/DD/YYYY (date)
    Line 2: MERCHANT NAME + ADDRESS
    Line 3: X% (cashback percentage)
    Line 4: $X.XX (cashback amount)
    Line 5: $X.XX (transaction amount)

    Skips: returns, negatives, amounts < $1.00
    """
    results = []
    lines = text.split("\n")

    date_pattern = re.compile(r"^(\d{2}/\d{2}/\d{4})$")
    amount_pattern = re.compile(r"^\$?([\d,]+\.\d{2})\s*$")

    logger.info(f"Apple Card extraction: processing {len(lines)} lines")

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        date_match = date_pattern.match(line)
        if date_match:
            date = date_match.group(1)

            # Next line should be merchant
            if i + 1 >= len(lines):
                i += 1
                continue

            merchant_line = lines[i + 1].strip()

            # Skip empty, headers, or adjustment lines
            if (
                not merchant_line
                or merchant_line.startswith("Daily Cash")
                or "(RETURN)" in merchant_line.upper()
                or "RETURN" in merchant_line.upper()
                and len(merchant_line) < 20
                or len(merchant_line) < 3
            ):
                i += 1
                continue

            merchant = merchant_line

            # Find the transaction amount (last positive amount before next date)
            # Typically: cashback %, cashback $, then transaction amount
            amount = None
            j = i + 2
            while j < len(lines) and j < i + 6:
                amt_line = lines[j].strip()

                # Stop if we hit another date
                if date_pattern.match(amt_line):
                    break

                # Skip negative amounts (returns/credits)
                if amt_line.startswith("-"):
                    j += 1
                    continue

                amt_match = amount_pattern.match(amt_line)
                if amt_match:
                    # Keep updating - the last valid amount is the transaction total
                    amount = amt_match.group(1).replace(",", "")
                j += 1

            if amount and merchant:
                try:
                    amt_float = float(amount)
                    # Skip amounts less than $1.00
                    if amt_float >= 1.00:
                        results.append(
                            {
                                "date": date,
                                "merchant": merchant,
                                "amount": amt_float,
                                "category": _categorize_merchant(merchant),
                                "raw_line": f"{date} {merchant} ${amount}",
                            }
                        )
                except ValueError:
                    pass

            i = j
            continue

        i += 1

    logger.info(f"Apple Card extraction complete: {len(results)} transactions found")
    return results


def _categorize_merchant(merchant: str) -> str:
    merchant_lower = merchant.lower()
    categories = {
        "dining": [
            "restaurant",
            "cafe",
            "coffee",
            "starbucks",
            "mcdonald",
            "chipotle",
            "subway",
            "pizza",
            "burger",
            "taco",
            "doordash",
            "uber eats",
            "grubhub",
        ],
        "groceries": [
            "grocery",
            "walmart",
            "target",
            "costco",
            "safeway",
            "kroger",
            "whole foods",
            "trader joe",
            "aldi",
        ],
        "gas": ["shell", "chevron", "exxon", "mobil", "bp ", "gas", "fuel", "76 "],
        "entertainment": [
            "netflix",
            "spotify",
            "hulu",
            "disney",
            "amazon prime",
            "hbo",
            "youtube",
            "apple tv",
            "gaming",
        ],
        "shopping": [
            "amazon",
            "ebay",
            "etsy",
            "best buy",
            "apple store",
            "nordstrom",
            "macy",
            "nike",
            "adidas",
        ],
        "travel": [
            "airline",
            "delta",
            "united",
            "american air",
            "southwest",
            "hotel",
            "airbnb",
            "uber",
            "lyft",
            "rental car",
        ],
        "utilities": [
            "electric",
            "water",
            "gas bill",
            "internet",
            "comcast",
            "at&t",
            "verizon",
            "t-mobile",
        ],
        "subscriptions": ["subscription", "membership", "monthly", "annual fee"],
        "health": [
            "pharmacy",
            "cvs",
            "walgreens",
            "doctor",
            "medical",
            "dental",
            "hospital",
            "health",
        ],
    }
    for category, keywords in categories.items():
        if any(kw in merchant_lower for kw in keywords):
            return category
    return "other"


def _build_interesting_findings(
    transactions: List[Dict], calculated: Dict
) -> List[str]:
    findings = []
    total = calculated.get("total_spent", 0)
    categories = calculated.get("categories", {})
    top_merchants = calculated.get("top_merchants", [])
    tx_count = len(transactions)

    if total > 0:
        findings.append(f"Total spending: ${total:,.2f} across {tx_count} transactions")

    if categories:
        sorted_cats = sorted(categories.items(), key=lambda x: abs(x[1]), reverse=True)
        if sorted_cats:
            top_cat, top_amount = sorted_cats[0]
            pct = (abs(top_amount) / total * 100) if total > 0 else 0
            findings.append(
                f"Highest category: {top_cat.title()} at ${abs(top_amount):,.2f} ({pct:.0f}% of total)"
            )

    if top_merchants and len(top_merchants) >= 1:
        top = top_merchants[0]
        findings.append(
            f"Top merchant: {top.get('merchant', 'Unknown')} - ${abs(top.get('total', 0)):,.2f}"
        )

    dining_total = categories.get("dining", 0)
    if dining_total > 0 and total > 0:
        dining_pct = abs(dining_total) / total * 100
        if dining_pct > 25:
            findings.append(
                f"Dining spending is {dining_pct:.0f}% of total - might be worth reviewing"
            )

    subscription_total = categories.get("subscriptions", 0) + categories.get(
        "entertainment", 0
    )
    if subscription_total > 100:
        findings.append(
            f"Subscriptions & entertainment: ${abs(subscription_total):,.2f}/month"
        )

    return findings


@dataclass
class BatchState:
    batch_id: str
    status: str
    files: List[Dict] = field(default_factory=list)

    preliminary_insights: Optional[Dict] = None
    phinance_prompt: Optional[str] = None
    transaction_count: int = 0
    interesting_findings: List[str] = field(default_factory=list)

    extracted_transactions: Optional[List[Dict]] = None
    calculated_summary: Optional[Dict] = None
    transactions_persisted: bool = False

    phinance_analysis: Optional[Dict] = None
    phinance_attempts: int = 0

    outputs: Dict[str, Any] = field(
        default_factory=lambda: {
            "dashboard_json": None,
            "pdf_command": None,
            "infographic_prompt": None,
            "text_summary": None,
        }
    )
    outputs_ready: bool = False

    created_at: float = field(default_factory=time.time)
    extraction_complete_at: Optional[float] = None
    analysis_ready_at: Optional[float] = None
    consent_given_at: Optional[float] = None
    phinance_complete_at: Optional[float] = None
    outputs_ready_at: Optional[float] = None


class BatchProcessor:
    def __init__(self):
        self.batches: Dict[str, BatchState] = {}
        self._on_status_change: Optional[Callable[[str, str], None]] = None

    def set_status_callback(self, callback: Callable[[str, str], None]):
        self._on_status_change = callback

    def hydrate_from_db(self, storage_module) -> int:
        """Restore incomplete batches from database on startup. Returns count hydrated."""
        try:
            incomplete = storage_module.get_incomplete_batches()
            count = 0
            for batch_record in incomplete:
                batch_id = batch_record["batch_id"]
                if batch_id in self.batches:
                    continue

                batch_full = storage_module.get_batch_full(batch_id)
                if not batch_full:
                    continue

                extracted_text = batch_full.get("extracted_text", "")
                phinance_analysis = batch_full.get("phinance_analysis")

                state = BatchState(
                    batch_id=batch_id,
                    status=batch_full.get("status", "ready"),
                    files=[{"full_text": extracted_text}] if extracted_text else [],
                )
                state.phinance_prompt = extracted_text
                if phinance_analysis:
                    state.phinance_analysis = phinance_analysis
                    state.status = "complete"

                self.batches[batch_id] = state
                count += 1
            return count
        except Exception:
            return 0

    def create_batch(self, files: List[Dict]) -> str:
        batch_id = f"batch-{uuid.uuid4().hex[:8]}"
        state = BatchState(batch_id=batch_id, status="uploading", files=files)
        self.batches[batch_id] = state
        return batch_id

    def get_batch_state(self, batch_id: str) -> Optional[BatchState]:
        return self.batches.get(batch_id)

    def update_batch_status(self, batch_id: str, status: str):
        if batch_id in self.batches:
            self.batches[batch_id].status = status
            if status == "ready":
                self.batches[batch_id].analysis_ready_at = time.time()
            elif status == "complete":
                self.batches[batch_id].phinance_complete_at = time.time()

            if self._on_status_change:
                try:
                    self._on_status_change(batch_id, status)
                except Exception:
                    pass

    async def background_full_process(self, batch_id: str, agent: Any):
        state = self.get_batch_state(batch_id)
        if not state:
            return

        self.update_batch_status(batch_id, "parsing")
        _emit_event(
            "background_full_process_start", batch_id, {"file_count": len(state.files)}
        )

        from pdf_processor import pdf_processor

        all_text_parts = []
        is_apple_card_batch = False

        # 1. Full text extraction + PII redaction for all files in batch
        for doc in state.files:
            temp_path = doc.get("temp_path")
            if not temp_path or not os.path.exists(temp_path):
                logger.warning(f"Temp path missing for file: {doc.get('filename')}")
                continue

            try:
                # Extract full text and apply PII redaction (uses PIIRedactor inside)
                text, is_apple = pdf_processor.extract_text_from_pdf(temp_path)
                all_text_parts.append(text)
                if is_apple:
                    is_apple_card_batch = True

                # Update doc info in state
                doc["full_text"] = text
                doc["is_apple_card"] = is_apple

                # Clean up temp file
                os.unlink(temp_path)
            except Exception as e:
                logger.error(f"Failed to extract text from {temp_path}: {e}")

        all_text = "\n".join(all_text_parts)
        logger.info(
            f"Total extracted text length: {len(all_text)} chars across {len(all_text_parts)} files"
        )

        # 2. Save full gzipped text to DB
        try:
            from home_ai.finance_agent.src import storage as fa_storage

            fa_storage.save_batch_extracted_text(batch_id, all_text)
            logger.info(f"Saved gzipped text for batch {batch_id}")
        except Exception as e:
            logger.warning(f"Failed to save batch text to DB: {e}")

        # 3. Regex transaction extraction
        try:
            self.update_batch_status(batch_id, "extracting")
            _emit_event("extraction_start", batch_id, {"text_length": len(all_text)})

            if is_apple_card_batch:
                logger.info("Using Apple Card multi-line state machine parser")
                transactions = _extract_apple_card_transactions(all_text)
            else:
                logger.info("Using Generic Bank regex pattern")
                transactions = _regex_extract(all_text, GENERIC_BANK_REGEX)

            _emit_event(
                "extraction_complete",
                batch_id,
                {"transaction_count": len(transactions)},
            )

            state.extracted_transactions = transactions
            state.transaction_count = len(transactions)

            if transactions:
                from utils.financial_calculator import calculate_financials

                calculated = calculate_financials(transactions)
                state.calculated_summary = calculated

                state.interesting_findings = _build_interesting_findings(
                    transactions, calculated
                )
                _emit_event(
                    "calculation_complete",
                    batch_id,
                    {
                        "total_spent": calculated.get("total_spent", 0),
                        "categories": len(calculated.get("categories", {})),
                        "findings_count": len(state.interesting_findings),
                    },
                )

            state.phinance_prompt = all_text
            if is_apple_card_batch:
                state.phinance_prompt = f"[FORMAT:APPLE_CARD]\n{all_text}"

            state.extraction_complete_at = time.time()
            self.update_batch_status(batch_id, "ready")
            _emit_event(
                "background_full_process_complete", batch_id, {"status": "ready"}
            )

        except Exception as e:
            self.update_batch_status(batch_id, "failed")
            _emit_event(
                "error", batch_id, {"stage": "background_full_process", "error": str(e)}
            )
            print(f"Background full process failed for {batch_id}: {e}")

    async def pre_generate_outputs(self, batch_id: str, generator: Any):
        state = self.get_batch_state(batch_id)
        if not state or not state.phinance_analysis:
            return

        try:
            analysis = state.phinance_analysis

            dashboard_task = asyncio.create_task(
                generator.generate_dashboard_json(analysis, batch_id)
            )
            pdf_task = asyncio.create_task(generator.build_pdf_command(analysis))
            infographic_task = asyncio.create_task(
                generator.build_infographic_prompt(analysis)
            )

            results = await asyncio.gather(dashboard_task, pdf_task, infographic_task)

            # Store in the standard outputs dict
            state.outputs = {
                "dashboard_json": results[0],
                "pdf_command": results[1],
                "infographic_prompt": results[2],
            }
            state.outputs_ready = True
            state.outputs_ready_at = time.time()

            _emit_event("outputs_pregenerated", batch_id, {"ready": True})

        except Exception as e:
            _emit_event(
                "error", batch_id, {"stage": "pre_generate_outputs", "error": str(e)}
            )
            print(f"Output pre-generation failed for {batch_id}: {e}")

    def _build_phinance_prompt(self, preliminary: Dict[str, Any]) -> str:
        return f"Analyze these transactions: {preliminary.get('transactions', [])}"


batch_processor = BatchProcessor()
