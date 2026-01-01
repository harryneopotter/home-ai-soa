from typing import List, Dict, Any, Optional
import yaml
from datetime import datetime
import os, pathlib

from memory import MemoryClient
from model import ModelClient

# TTS disabled for now
# from tts_service import tts_service
from utils.logger import get_logger
from utils.errors import ValidationError, ServiceError, InternalError

logger = get_logger("agent")

DEFAULT_ORCHESTRATOR_PROMPT_PATH = "prompts/orchestrator.md"


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

    # ---------------------------------------------------------
    # Format memory context (with time awareness)
    # ---------------------------------------------------------
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

    # ---------------------------------------------------------
    # Format Document Context (for progressive engagement)
    # ---------------------------------------------------------
    def _format_document_context(
        self, document_context: Optional[Dict[str, Any]]
    ) -> str:
        """
        Format document metadata into the [DOCUMENT CONTEXT] block
        that the orchestrator prompt expects.

        Expected document_context structure:
        {
            "documents": [
                {
                    "filename": "statement.pdf",
                    "pages": 5,
                    "size_kb": 245,
                    "upload_time": "2025-12-27T10:30:00",
                    "detected_type": "bank_statement",  # optional
                    "preview_text": "First 200 chars..."  # optional
                }
            ],
            "session_id": "abc123"
        }
        """
        if not document_context or not document_context.get("documents"):
            return ""

        docs = document_context["documents"]
        lines = ["[DOCUMENT CONTEXT]"]

        for i, doc in enumerate(docs, 1):
            filename = doc.get("filename", "unknown")
            pages = doc.get("pages", "unknown")
            size_kb = doc.get("size_kb", "unknown")
            detected_type = doc.get("detected_type", "")
            preview = doc.get("preview_text", "")

            lines.append(f"Document {i}: {filename}")
            lines.append(f"  - Pages: {pages}")
            lines.append(f"  - Size: {size_kb} KB")

            if detected_type:
                lines.append(f"  - Detected type: {detected_type}")

            if preview:
                truncated = preview[:200] + "..." if len(preview) > 200 else preview
                lines.append(f"  - Preview: {truncated}")

        lines.append("[/DOCUMENT CONTEXT]")
        return "\n".join(lines)

    # ---------------------------------------------------------
    # TTS Methods
    # ---------------------------------------------------------
    def ask_with_tts(self, query: str) -> Dict[str, Any]:
        """TTS disabled - falls back to regular ask"""
        logger.warning("TTS requested but disabled in this build")
        return self.ask(query)

    # ---------------------------------------------------------
    # Main Agent Logic
    # ---------------------------------------------------------
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

        # 5. Write new factual memory (with explicit time)
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
        return {
            "answer": answer,
            "used_memories": memories,
        }
