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

USE_LLM_CATEGORIZATION = (
    False  # Disabled until Phase 3 (chat-based correction) is implemented
)

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
        "Food & Dining": [
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
            "deli",
            "bakery",
            "food",
            "dining",
            "kitchen",
            "grill",
            "wok",
            "sushi",
            "thai",
            "indian",
            "chinese",
            "mexican",
            "italian",
            "kebab",
            "shawarma",
            "halal",
            "tandoor",
            "curry",
            "hoppers",
            "sweets",
            "bagels",
            "seafood",
            "brewhouse",
            "alehouse",
            "confiserie",
            "takeaway",
        ],
        "Groceries": [
            "grocery",
            "walmart",
            "wal-mart",
            "target",
            "costco",
            "safeway",
            "kroger",
            "whole foods",
            "trader joe",
            "aldi",
            "jewel",
            "osco",
            "market",
            "mart",
            "fruit",
            "patel brothers",
            "giant food",
            "butera",
            "suarez market",
        ],
        "Gas": [
            "shell",
            "chevron",
            "exxon",
            "mobil",
            "bp ",
            "fuel",
            "76 ",
            "gas station",
            "speedway",
            "marathon",
            "sunoco",
            "valero",
            "citgo",
            "phillips 66",
        ],
        "Shopping": [
            "amazon",
            "ebay",
            "etsy",
            "best buy",
            "apple store",
            "nordstrom",
            "macy",
            "nike",
            "adidas",
            "home depot",
            "menards",
            "lowe",
            "micro center",
            "lego",
            "five below",
            "dollar",
            "burlington",
            "b&h photo",
            "lumber",
            "hardware",
            "parts express",
            "newark",
            "oneplus",
            "anker",
            "kindle",
            "jockey",
            "marks and spencer",
            "bata",
            "retail",
            "store",
            "shop",
        ],
        "Entertainment": [
            "netflix",
            "spotify",
            "hulu",
            "disney",
            "amazon prime",
            "hbo",
            "youtube",
            "apple tv",
            "gaming",
            "steam",
            "onlyfans",
            "empire photos",
            "fosi audio",
        ],
        "Travel": [
            "airline",
            "delta",
            "united",
            "american air",
            "southwest",
            "lufthansa",
            "air india",
            "westjet",
            "swiss",
            "hotel",
            "airbnb",
            "westin",
            "hampton",
            "fairfield",
            "radisson",
            "airport",
            "terminal",
            "south block",
            "iad",
            "simplytrawell",
        ],
        "Transportation": [
            "uber",
            "lyft",
            "taxi",
            "metra",
            "transit",
            "hertz",
            "avis",
            "enterprise",
            "rental car",
            "platepass",
            "tollway",
            "toll",
        ],
        "Utilities": [
            "electric",
            "water",
            "gas bill",
            "internet",
            "comcast",
            "at&t",
            "verizon",
            "t-mobile",
            "comed",
            "recycling",
            "lakeshore recycl",
            "huntley*utility",
            "jnl climate",
        ],
        "Subscriptions": [
            "subscription",
            "membership",
            "monthly",
            "annual fee",
            "openai",
            "chatgpt",
            "telegram premium",
            "zoom",
            "better.com",
        ],
        "Health": [
            "pharmacy",
            "cvs",
            "walgreens",
            "doctor",
            "medical",
            "dental",
            "hospital",
            "health",
            "vitamin",
            "mercy mychart",
        ],
        "Insurance": [
            "progressive",
            "insurance",
            "hagerty",
            "geico",
            "allstate",
            "state farm",
        ],
        "Automotive": [
            "ford motor",
            "automotive",
            "auto parts",
            "oreilly",
            "car wash",
            "restyling",
            "obsessed garage",
            "top notch auto",
        ],
        "Government & Fees": [
            "village of",
            "city of",
            "usps",
            "ilsos",
            "ici*fee",
            "municipal",
            "muni-web",
            "government",
            "dmv",
            "secretary of state",
        ],
        "Donations": [
            "actblue",
            "donation",
            "charity",
            "nonprofit",
        ],
        "Housing": [
            "storage",
            "firstservice",
            "property management",
            "rent",
            "mortgage",
        ],
        "Alcohol": [
            "liquor",
            "wine",
            "beer",
            "spirits",
            "lith liquor",
            "singla liquor",
        ],
    }
    for category, keywords in categories.items():
        if any(kw in merchant_lower for kw in keywords):
            return category
    return "Other"


def _llm_categorize_unknown_merchants(
    transactions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Categorize 'Other' merchants using LLM with caching."""
    if not USE_LLM_CATEGORIZATION:
        return transactions

    other_merchants = set()
    for tx in transactions:
        if tx.get("category") == "Other":
            other_merchants.add(tx.get("merchant", ""))

    other_merchants.discard("")
    if not other_merchants:
        logger.info("No 'Other' merchants to categorize via LLM")
        return transactions

    logger.info(
        f"Found {len(other_merchants)} unique 'Other' merchants, checking cache..."
    )

    try:
        from home_ai.finance_agent.src import storage as fa_storage

        cached = fa_storage.get_merchant_mappings_batch(list(other_merchants))
        cached_count = len(cached)
        logger.info(f"Cache hit: {cached_count}/{len(other_merchants)} merchants")

        uncached = [m for m in other_merchants if m not in cached]

        llm_results = {}
        if uncached:
            logger.info(f"Calling LLM for {len(uncached)} uncached merchants")
            from models import categorize_merchants_llm

            llm_results = categorize_merchants_llm(uncached)

            if llm_results:
                mappings_to_save = [
                    {"raw_name": merchant, "category": category}
                    for merchant, category in llm_results.items()
                ]
                saved_count = fa_storage.upsert_merchant_mappings_batch(
                    mappings_to_save, source="phinance"
                )
                logger.info(f"Cached {saved_count} new LLM categorizations")

        category_map = {}
        for merchant, mapping in cached.items():
            category_map[merchant] = mapping.get("category", "Other")
        category_map.update(llm_results)

        updated_count = 0
        for tx in transactions:
            merchant = tx.get("merchant", "")
            if tx.get("category") == "Other" and merchant in category_map:
                new_cat = category_map[merchant]
                if new_cat != "Other":
                    tx["category"] = new_cat
                    updated_count += 1

        logger.info(f"LLM categorization updated {updated_count} transactions")
        return transactions

    except Exception as e:
        logger.error(f"LLM categorization failed: {e}")
        return transactions


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

        # 3. Regex transaction extraction - PER DOCUMENT with doc_id tagging
        try:
            self.update_batch_status(batch_id, "extracting")
            _emit_event("extraction_start", batch_id, {"text_length": len(all_text)})

            all_transactions = []
            for doc in state.files:
                doc_id = doc.get("doc_id")
                text = doc.get("full_text", "")
                is_apple = doc.get("is_apple_card", False)

                if not text:
                    continue

                if is_apple:
                    logger.info(f"Using Apple Card parser for {doc_id}")
                    doc_transactions = _extract_apple_card_transactions(text)
                else:
                    logger.info(f"Using Generic Bank regex for {doc_id}")
                    doc_transactions = _regex_extract(text, GENERIC_BANK_REGEX)

                # Tag each transaction with its source doc_id
                for tx in doc_transactions:
                    tx["doc_id"] = doc_id

                all_transactions.extend(doc_transactions)
                logger.info(
                    f"Extracted {len(doc_transactions)} transactions from {doc_id}"
                )

            _emit_event(
                "extraction_complete",
                batch_id,
                {"transaction_count": len(all_transactions)},
            )

            all_transactions = _llm_categorize_unknown_merchants(all_transactions)

            state.extracted_transactions = all_transactions
            state.transaction_count = len(all_transactions)

            if all_transactions:
                from utils.financial_calculator import calculate_financials

                calculated = calculate_financials(all_transactions)
                state.calculated_summary = calculated

                state.interesting_findings = _build_interesting_findings(
                    all_transactions, calculated
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
                generator.generate_dashboard_json(analysis, batch_id, state.files)
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

    def pre_generate_outputs_sync(self, batch_id: str, generator: Any):
        """Synchronous wrapper for pre_generate_outputs - for use in threads."""
        import asyncio

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.pre_generate_outputs(batch_id, generator))
            finally:
                loop.close()
        except Exception as e:
            print(f"Sync output pre-generation failed for {batch_id}: {e}")

    def _build_phinance_prompt(self, preliminary: Dict[str, Any]) -> str:
        return f"Analyze these transactions: {preliminary.get('transactions', [])}"


batch_processor = BatchProcessor()
