from typing import List, Dict, Any, Optional, Generator
import yaml
from datetime import datetime
import os, pathlib
import re
import json
import time

from memory import MemoryClient
from model import ModelClient

# TTS disabled for now
# from tts_service import tts_service
from batch_processor import batch_processor
from output_generator import output_generator
from utils.logger import get_logger
from utils.errors import ValidationError, ServiceError, InternalError
from utils.merchant_normalizer import normalize_transactions
from utils.financial_calculator import (
    calculate_financials,
    build_insights_prompt,
    merge_calculated_with_llm_response,
    strip_markdown_fences,
)

logger = get_logger("agent")

DEFAULT_ORCHESTRATOR_PROMPT_PATH = "prompts/orchestrator.md"

INVOKE_PATTERN = re.compile(r"\[INVOKE:phinance\]", re.IGNORECASE)

OUTPUT_PATTERNS = {
    "web": re.compile(r"\b(web|dashboard|1)\b", re.IGNORECASE),
    "pdf": re.compile(r"\b(pdf|export|2)\b", re.IGNORECASE),
    "infographic": re.compile(r"\b(infographic|image|3)\b", re.IGNORECASE),
}


def _load_system_prompt(base_dir: str, cfg: dict) -> str:
    """
    Fallback chain: orchestrator.prompt_file → prompts/orchestrator.md → orchestrator.system_prompt → agent.system_prompt
    """
    orchestrator_cfg = cfg.get("orchestrator", {})

    prompt_file = orchestrator_cfg.get("prompt_file")
    if prompt_file:
        prompt_path = os.path.join(base_dir, prompt_file)
        if os.path.exists(prompt_path):
            logger.info(f"Loading orchestrator prompt from: {prompt_path}")
            with open(prompt_path, "r") as f:
                return f.read().strip()
        else:
            logger.warning(f"Configured prompt_file not found: {prompt_path}")

    default_prompt_path = os.path.join(base_dir, DEFAULT_ORCHESTRATOR_PROMPT_PATH)
    if os.path.exists(default_prompt_path):
        logger.info(f"Loading orchestrator prompt from default: {default_prompt_path}")
        with open(default_prompt_path, "r") as f:
            return f.read().strip()

    if "system_prompt" in orchestrator_cfg:
        logger.info("Using inline orchestrator.system_prompt from config")
        return orchestrator_cfg["system_prompt"]

    agent_cfg = cfg.get("agent", {})
    if "system_prompt" in agent_cfg:
        logger.warning("Using legacy agent.system_prompt - migrate to orchestrator.md")
        return agent_cfg["system_prompt"]

    raise ValueError("No system prompt found in config or orchestrator.md file")


class SOA1Agent:
    def __init__(self, config_path: str = "config.yaml"):
        base_dir = os.path.dirname(__file__)
        config_path = os.path.join(base_dir, config_path)
        # Load config
        with open(config_path, "r") as f:
            cfg = yaml.safe_load(f)

        self.system_prompt: str = _load_system_prompt(base_dir, cfg)
        self.memory = MemoryClient(config_path=config_path)
        self.model = ModelClient(config_path=config_path)

        # TTS Configuration
        tts_config = cfg.get("tts", {})
        self.tts_enabled = tts_config.get("enabled", False)
        self.default_speaker = tts_config.get("speaker_id", 0)
        self.tts_output_dir = tts_config.get("output_dir", "/tmp/soa1_tts")

        # Optional: test memory connectivity on startup
        try:
            self.memory.health_check()
        except Exception as e:
            logger.warning(f"MemLayer health check failed at init: {e}")

        # Optional: test TTS availability
        if self.tts_enabled:
            logger.info("TTS is disabled in this build")

    # Format memory context (with time awareness)
    def _format_memory_context(self, memories: List[Dict[str, Any]]) -> str:
        if not memories:
            return "No relevant past memories were found."

        lines = []
        for m in memories:
            text = m.get("text", "")
            meta = m.get("metadata", {})

            # Try metadata timestamps first
            recorded = (
                meta.get("recorded_at_local")
                or meta.get("recorded_at_utc")
                or m.get("timestamp")
            )

            if recorded:
                try:
                    ts_str = datetime.fromisoformat(recorded).isoformat()
                except:
                    try:
                        ts_str = datetime.fromtimestamp(float(recorded)).isoformat()
                    except:
                        ts_str = str(recorded)
            else:
                ts_str = "unknown_time"

            lines.append(f"- ({ts_str}) {text}")

        return "\n".join(lines)

    # Format Document Context (for progressive engagement)
    def _format_document_context(
        self, document_context: Optional[Dict[str, Any]]
    ) -> str:
        """
        Format document metadata and BATCH STATE into the [DOCUMENT CONTEXT] block.
        """
        if not document_context or not document_context.get("documents"):
            return ""

        batch_id = document_context.get("batch_id")
        docs = document_context["documents"]
        lines = ["[DOCUMENT CONTEXT]"]

        if batch_id:
            lines.append(f"Batch ID: {batch_id}")
            state = batch_processor.get_batch_state(batch_id)
            if state:
                lines.append(f"Processing Status: {state.status}")
                if state.transaction_count > 0:
                    lines.append(f"Transactions Found: {state.transaction_count}")
                if state.interesting_findings:
                    lines.append("Preliminary Findings:")
                    for finding in state.interesting_findings:
                        lines.append(f"  - {finding}")

        lines.append("Files in this session:")
        for i, doc in enumerate(docs, 1):
            filename = doc.get("filename", "unknown")
            pages = doc.get("pages", "unknown")
            inferred_type = doc.get("inferred_type", "")

            lines.append(
                f"Document {i}: {filename} ({pages} pages, type: {inferred_type})"
            )

            headers = doc.get("header_lines", [])
            if headers:
                preview = "\\n".join(headers[:3])
                lines.append(f"  Headers: {preview}")

        lines.append("[/DOCUMENT CONTEXT]")
        return "\n".join(lines)

    def _invoke_phinance(self, document_context: Optional[Dict[str, Any]]) -> str:
        if not document_context or not document_context.get("documents"):
            return "I don't have any documents loaded to analyze. Please upload a document first."

        try:
            batch_id = document_context.get("batch_id")
            docs = document_context.get("documents", [])
            doc_ids = [d.get("doc_id") for d in docs if d.get("doc_id")]

            if batch_id:
                state = batch_processor.get_batch_state(batch_id)
                if state and state.extracted_transactions:
                    return self._process_with_batch_state(state, doc_ids)

            if not doc_ids:
                return "No document IDs found. Please upload a document first."

            try:
                from home_ai.finance_agent.src import storage as fa_storage

                all_transactions = []
                for doc_id in doc_ids:
                    txns = fa_storage.get_transactions_by_doc(doc_id)
                    if txns:
                        all_transactions.extend(txns)
            except Exception as e:
                logger.warning(f"Could not load transactions from storage: {e}")
                all_transactions = []

            if all_transactions:
                all_transactions = normalize_transactions(all_transactions)

            if not all_transactions:
                return (
                    "I couldn't find any transaction data for these documents. "
                    "The documents may need to be processed first. "
                    "Would you like me to extract the transactions?"
                )

            return self._run_hybrid_analysis(all_transactions)

        except Exception as e:
            logger.error(f"Phinance invocation failed: {e}")
            return f"I encountered an issue while analyzing your documents: {str(e)}"

    def _process_with_batch_state(self, state, doc_ids: List[str]) -> str:
        all_transactions = state.extracted_transactions
        if not all_transactions:
            return "No transactions were extracted from your documents. They may not contain recognizable transaction data."

        if not state.transactions_persisted and doc_ids:
            try:
                from home_ai.finance_agent.src import storage as fa_storage

                for doc_id in doc_ids:
                    doc_txns = [t for t in all_transactions]
                    if doc_txns:
                        fa_storage.save_transactions_for_doc(doc_id, doc_txns)
                        logger.info(
                            f"Persisted {len(doc_txns)} transactions for {doc_id}"
                        )
                state.transactions_persisted = True
                state.consent_given_at = time.time()
            except Exception as e:
                logger.warning(f"Failed to persist transactions: {e}")

        all_transactions = normalize_transactions(all_transactions)

        if state.calculated_summary:
            calculated = state.calculated_summary
        else:
            calculated = calculate_financials(all_transactions)
            state.calculated_summary = calculated

        logger.info(
            f"Using batch state: total=${calculated['total_spent']}, "
            f"categories={len(calculated['categories'])}, tx_count={len(all_transactions)}"
        )

        return self._run_hybrid_analysis(all_transactions, calculated, state)

    def _run_hybrid_analysis(
        self,
        transactions: List[Dict],
        calculated: Optional[Dict] = None,
        state: Optional[Any] = None,
    ) -> str:
        if not calculated:
            calculated = calculate_financials(transactions)

        logger.info(
            f"Calculated financials: total=${calculated['total_spent']}, "
            f"categories={len(calculated['categories'])}, "
            f"merchants={len(calculated['top_merchants'])}"
        )

        insights_prompt = build_insights_prompt(transactions, calculated)
        logger.info("Invoking insights model (qwen2.5) with pre-calculated data")

        from models import call_insights_model

        raw_response = call_insights_model(insights_prompt)

        try:
            cleaned_response = strip_markdown_fences(raw_response)
            llm_insights = json.loads(cleaned_response)
        except json.JSONDecodeError:
            llm_insights = {
                "insights": [],
                "recommendations": [],
                "potential_savings": 0,
                "verified_drains": [],
            }

        analysis = merge_calculated_with_llm_response(calculated, llm_insights)

        if state:
            state.phinance_analysis = analysis
            state.phinance_complete_at = time.time()

        analysis_text = self._format_analysis_response(analysis, len(transactions))

        return analysis_text

    def _format_analysis_response(self, analysis: Dict[str, Any], tx_count: int) -> str:
        """Format phinance analysis results into user-friendly text."""
        lines = [f"Here's what I found from analyzing {tx_count} transactions:\n"]

        total = analysis.get("total_spent") or analysis.get("total")
        if total:
            lines.append(f"📊 **Total Spending**: ${abs(float(total)):,.2f}\n")

        categories = analysis.get("categories") or analysis.get("by_category", {})
        if categories:
            lines.append("💰 **By Category**:")
            sorted_cats = sorted(
                categories.items(), key=lambda x: abs(float(x[1])), reverse=True
            )
            for cat, amount in sorted_cats[:5]:
                lines.append(f"  • {cat.title()}: ${abs(float(amount)):,.2f}")
            lines.append("")

        merchants = analysis.get("top_merchants") or analysis.get("merchants", [])
        if merchants:
            lines.append("🏪 **Top Merchants**:")
            if isinstance(merchants, dict):
                sorted_merch = sorted(
                    merchants.items(), key=lambda x: abs(float(x[1])), reverse=True
                )[:5]
                for merch, amount in sorted_merch:
                    lines.append(f"  • {merch}: ${abs(float(amount)):,.2f}")
            elif isinstance(merchants, list):
                for m in merchants[:5]:
                    if isinstance(m, dict):
                        name = m.get("name") or m.get("merchant", "Unknown")
                        amt = m.get("amount") or m.get("total", 0)
                        lines.append(f"  • {name}: ${abs(float(amt)):,.2f}")
            lines.append("")

        drains = analysis.get("hidden_drains", [])
        if drains:
            lines.append("💸 **Hidden Drains** (Small recurring charges):")
            for drain in drains:
                if isinstance(drain, dict):
                    name = drain.get("merchant", "Unknown")
                    annual = drain.get("annual_projection") or drain.get(
                        "annual_cost", 0
                    )
                    is_drain = drain.get("is_drain", True)
                    reason = drain.get("llm_reason", "")

                    if is_drain:
                        lines.append(f"  🚨 {name}: ~${float(annual):,.2f}/year")
                        if reason:
                            lines.append(f"     → {reason}")
                    else:
                        lines.append(
                            f"  ✅ {name}: ~${float(annual):,.2f}/year (verified OK)"
                        )
            lines.append("")

        insights = analysis.get("insights") or analysis.get("recommendations", [])
        if insights:
            lines.append("🔍 **Insights**:")
            if isinstance(insights, list):
                for insight in insights[:3]:
                    lines.append(f"  • {insight}")
            elif isinstance(insights, str):
                lines.append(f"  • {insights}")
            lines.append("")

        # Phase 3: Ask for output format
        lines.append("📋 **How would you like the detailed report?**")
        lines.append("  1. 🖥️ Web Dashboard")
        lines.append("  2. 📄 PDF Export")
        lines.append("  3. 🎨 Infographic")
        lines.append("")
        lines.append(
            "Just say 'web', 'pdf', or 'infographic' (or ask me any other questions)."
        )
        return "\n".join(lines)

    # TTS Methods
    def ask_with_tts(self, query: str) -> Dict[str, Any]:
        """TTS disabled - falls back to regular ask"""
        logger.warning("TTS requested but disabled in this build")
        return self.ask(query)

    # Main Agent Logic
    async def analyze_preliminary_text(self, text: str) -> Dict[str, Any]:
        prompt = f"Analyze this text and provide preliminary insights, transaction count, and interesting findings in JSON format:\n{text}"
        convo = [{"role": "user", "content": prompt}]

        try:
            response = self.model.chat(self.system_prompt, convo)
            try:
                start = response.find("{")
                end = response.rfind("}") + 1
                if start != -1 and end != 0:
                    return json.loads(response[start:end])
            except:
                pass

            return {
                "insights": {"summary": response},
                "interesting": [],
                "transaction_count": 0,
                "transactions": [],
            }
        except Exception as e:
            logger.error(f"Preliminary analysis failed: {e}")
            return {}

    async def analyze_batch(self, batch_id: str):
        state = batch_processor.get_batch_state(batch_id)
        if not state:
            return

        try:
            from models import call_phinance_validated

            payload = {
                "text": state.phinance_prompt,
                "currency": "USD",
                "request_type": "full_analysis",
            }

            logger.info(
                f"Calling phinance for batch {batch_id} with validation and retries"
            )
            (transactions, analysis), attempts = call_phinance_validated(
                json.dumps(payload)
            )
            logger.info(
                f"Phinance analysis complete for {batch_id} in {attempts} attempt(s)."
            )

            analysis_dict = analysis.model_dump()
            tx_list = [t.model_dump() for t in transactions.transactions]

            if tx_list:
                tx_list = normalize_transactions(tx_list)

            analysis_dict["transactions"] = tx_list

            if tx_list:
                calculated = calculate_financials(tx_list)
                analysis_dict["total_spent"] = calculated["total_spent"]
                analysis_dict["categories"] = calculated["categories"]
                analysis_dict["top_merchants"] = calculated["top_merchants"]
                analysis_dict["transaction_count"] = calculated["transaction_count"]
                analysis_dict["avg_transaction"] = calculated["avg_transaction"]
                analysis_dict["date_range"] = calculated.get("date_range")
                logger.info(
                    f"Python-calculated financials: total=${calculated['total_spent']}, "
                    f"tx_count={calculated['transaction_count']}"
                )

            state.phinance_analysis = analysis_dict
            state.phinance_attempts = attempts
            state.status = "complete"
            state.phinance_complete_at = time.time()

            try:
                from home_ai.finance_agent.src import storage as chat_storage

                chat_storage.save_batch_phinance_analysis(batch_id, analysis_dict)
                logger.info(f"Persisted phinance analysis for batch {batch_id}")
            except Exception as persist_err:
                logger.warning(f"Failed to persist phinance analysis: {persist_err}")

            await batch_processor.pre_generate_outputs(batch_id, output_generator)

        except Exception as e:
            logger.error(f"Batch analysis failed for {batch_id}: {e}")
            state.status = "failed"

    def ask(
        self,
        query: str,
        document_context: Optional[Dict[str, Any]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Main agent query method with enhanced error handling

        Args:
            query: User's question
            document_context: Optional document/transaction context
            chat_history: Optional list of previous messages [{"role": "user/assistant", "content": "..."}]
        """

        # Validate input
        if not query or not isinstance(query, str):
            raise ValidationError("Query must be a non-empty string", "query", query)

        if len(query) > 1000:
            raise ValidationError("Query too long (max 1000 chars)", "query", query)

        logger.info(f"SOA1 received query: {query}")

        # 1. Search memory (graceful degradation if unavailable)
        memories = []
        try:
            memories = self.memory.search_memory(query)
        except Exception as e:
            logger.warning(f"Memory search failed (continuing without): {e}")

        memory_context = self._format_memory_context(memories)

        # 2. Format document context if provided
        doc_context_block = self._format_document_context(document_context)

        # 3. Build model conversation
        convo = []

        if chat_history:
            for msg in chat_history:
                if msg.get("role") in ("user", "assistant") and msg.get("content"):
                    convo.append({"role": msg["role"], "content": msg["content"]})

        content_parts = []

        if doc_context_block:
            content_parts.append(doc_context_block)

        content_parts.append(
            f"Here is relevant context from past memories:\n{memory_context}"
        )

        content_parts.append(
            f"Now answer the following question for the user:\n{query}"
        )

        convo.append(
            {
                "role": "user",
                "content": "\n\n".join(content_parts),
            }
        )

        # 4. Model inference
        try:
            answer = self.model.chat(self.system_prompt, convo)
        except Exception as e:
            logger.error(f"Model call failed: {e}")
            raise ServiceError("model", f"Model inference failed: {str(e)}")

        # 5. Check for [INVOKE:phinance] tag and handle specialist routing
        is_invoke = INVOKE_PATTERN.search(answer)

        # BACKUP CATCH: If the LLM forgot the tag but the user asked for analysis
        # and we are in the 'ready' state, force it.
        if not is_invoke and document_context and document_context.get("batch_id"):
            state = batch_processor.get_batch_state(document_context["batch_id"])
            if state and state.status == "ready":
                trigger_keywords = ["analyze", "analysis", "breakdown", "spending"]
                if any(kw in query.lower() for kw in trigger_keywords):
                    logger.info("Backup catch triggered: Forcing [INVOKE:phinance]")
                    is_invoke = True

        if is_invoke:
            logger.info("Detected [INVOKE:phinance] signal - routing to phinance")
            answer_without_tag = INVOKE_PATTERN.sub("", answer).strip()

            # If the response looks like a hallucinated report (contains multiple $ signs or numbers)
            # and the tag was missing (triggered by backup catch), or it's just too long,
            # sanitize it to keep only the engagement part.
            if ("$" in answer_without_tag and answer_without_tag.count("$") > 2) or len(
                answer_without_tag
            ) > 300:
                logger.warning(
                    "Discarding potential hallucinated LLM report in engagement message"
                )
                answer_without_tag = "Starting your analysis now! I'll have the results for you in a few seconds."

            batch_id = document_context.get("batch_id") if document_context else None
            if batch_id:
                state = batch_processor.get_batch_state(batch_id)
                if state and state.status == "ready":
                    findings_text = ""
                    if state.interesting_findings:
                        findings_text = "\n\n**While I analyze the details, here's what I noticed:**\n"
                        for finding in state.interesting_findings:
                            findings_text += f"• {finding}\n"

                    if answer_without_tag:
                        answer = f"{answer_without_tag}{findings_text}\n\nI'm running the deep analysis now - I'll have the full report ready in a few seconds."
                    else:
                        answer = f"Starting your analysis now!{findings_text}\n\nI'll have the full report ready in a few seconds."

                    state.status = "analyzing"

                    return {
                        "answer": answer,
                        "used_memories": memories,
                        "trigger_phinance_background": batch_id,
                    }

            phinance_result = self._invoke_phinance(document_context)
            if answer_without_tag:
                answer = f"{answer_without_tag}\n\n{phinance_result}"
            else:
                answer = phinance_result

        # 6. Check for output format selection
        if document_context and document_context.get("batch_id"):
            batch_id = document_context["batch_id"]
            state = batch_processor.get_batch_state(batch_id)

            # Only allow format selection if analysis is complete
            if state and state.status == "complete":
                for format_name, pattern in OUTPUT_PATTERNS.items():
                    if pattern.search(query):
                        logger.info(
                            f"Detected request for {format_name} output for batch {batch_id}"
                        )

                        if format_name == "web":
                            answer = f"Opening your interactive Web Report for batch {batch_id}..."
                            # We'll return this extra field for the API to handle the redirect
                            redirect_url = f"/dashboard/batch/{batch_id}"

                            return {
                                "answer": answer,
                                "used_memories": memories,
                                "redirect_url": redirect_url,
                            }
                        elif format_name == "pdf":
                            answer = "I'm preparing your PDF report. It will be ready for download in a few seconds."
                            # Trigger pre-generation if not already done
                            if not state.outputs_ready:
                                asyncio.create_task(
                                    batch_processor.pre_generate_outputs(
                                        batch_id, output_generator
                                    )
                                )
                        elif format_name == "infographic":
                            answer = "I'm generating your visual infographic. I'll let you know as soon as it's ready."
                            if not state.outputs_ready:
                                asyncio.create_task(
                                    batch_processor.pre_generate_outputs(
                                        batch_id, output_generator
                                    )
                                )

        # 7. Write new factual memory (with explicit time)
        try:
            timestamp = datetime.utcnow()

            summary_text = (
                f"[Event]\n"
                f"question: {query}\n"
                f"answer: {answer}\n"
                f"recorded_at_utc: {timestamp.isoformat()}\n"
                f"recorded_at_local: {timestamp.astimezone().isoformat()}\n"
            )

            self.memory.write_memory(
                text=summary_text,
                metadata={
                    "event_type": "qa_interaction",
                    "recorded_at_utc": timestamp.isoformat(),
                    "recorded_epoch": int(timestamp.timestamp()),
                },
            )

        except Exception as e:
            logger.warning(f"Memory write failed (non-critical): {e}")
            # Non-critical failure - continue

        # 6. Return agent output
        result = {
            "answer": answer,
            "used_memories": memories,
        }

        # Signal for Phase 3: output pre-generation if phinance completed
        if document_context and document_context.get("batch_id"):
            batch_id = document_context["batch_id"]
            state = batch_processor.get_batch_state(batch_id)
            if state and state.phinance_analysis and not state.outputs_ready:
                result["trigger_output_generation"] = batch_id

        return result

    def ask_stream(
        self,
        query: str,
        document_context: Optional[Dict[str, Any]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> Generator[str, None, None]:
        """Streaming version of ask - yields response chunks."""
        if not query or not isinstance(query, str):
            yield "Error: Query must be a non-empty string"
            return

        if len(query) > 1000:
            yield "Error: Query too long (max 1000 chars)"
            return

        logger.info(f"SOA1 streaming query: {query}")

        memories = []
        try:
            memories = self.memory.search_memory(query)
        except Exception as e:
            logger.warning(f"Memory search failed (continuing without): {e}")

        memory_context = self._format_memory_context(memories)
        doc_context_block = self._format_document_context(document_context)

        convo = []
        if chat_history:
            for msg in chat_history:
                if msg.get("role") in ("user", "assistant") and msg.get("content"):
                    convo.append({"role": msg["role"], "content": msg["content"]})

        content_parts = []
        if doc_context_block:
            content_parts.append(doc_context_block)
        content_parts.append(
            f"Here is relevant context from past memories:\n{memory_context}"
        )
        content_parts.append(
            f"Now answer the following question for the user:\n{query}"
        )

        convo.append({"role": "user", "content": "\n\n".join(content_parts)})

        try:
            for chunk in self.model.chat_stream(self.system_prompt, convo):
                yield chunk
        except Exception as e:
            logger.error(f"Streaming model call failed: {e}")
            yield f"\n\nError: {str(e)}"
