from typing import List, Dict, Any
import yaml
from datetime import datetime
import os, pathlib

from memory import MemoryClient
from model import ModelClient
from tts_service import tts_service
from utils.logger import get_logger
from utils.errors import ValidationError, ServiceError, InternalError

logger = get_logger("agent")


class SOA1Agent:
    def __init__(self, config_path: str = "config.yaml"):
        config_path = os.path.join(os.path.dirname(__file__), config_path)
        # Load config
        with open(config_path, "r") as f:
            cfg = yaml.safe_load(f)

        self.system_prompt: str = cfg["agent"]["system_prompt"]
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
            try:
                if not tts_service.is_available():
                    tts_service.load_model()
                logger.info("TTS service initialized and ready")
            except Exception as e:
                logger.warning(f"TTS service failed to initialize: {e}")
                self.tts_enabled = False

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
    # TTS Methods
    # ---------------------------------------------------------
    def ask_with_tts(self, query: str) -> Dict[str, Any]:
        """Ask and get TTS response with enhanced error handling"""
        
        # Validate input
        if not query or not isinstance(query, str):
            raise ValidationError("Query must be a non-empty string", "query", query)
        
        if not self.tts_enabled:
            logger.warning("TTS requested but not enabled")
            return self.ask(query)
        
        try:
            # Get text response
            result = self.ask(query)
            
            # Generate TTS
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(
                self.tts_output_dir,
                f"response_{timestamp}.wav"
            )
            
            tts_result = tts_service.text_to_speech(
                result["answer"],
                output_path=output_path,
                speaker_id=self.default_speaker
            )
            
            if tts_result["status"] == "success":
                result["audio_path"] = tts_result["audio_path"]
                result["audio_duration"] = tts_result["duration"]
                logger.info(f"TTS generated: {output_path}")
            else:
                logger.error(f"TTS failed: {tts_result['error']}")
                result["tts_error"] = tts_result["error"]
                raise ServiceError("tts", f"TTS generation failed: {tts_result['error']}")
            
            return result
            
        except ServiceError:
            raise  # Re-raise service errors
        except Exception as e:
            logger.error(f"TTS processing failed: {e}", exc_info=True)
            raise InternalError(f"TTS processing failed: {str(e)}")

    # ---------------------------------------------------------
    # Main Agent Logic
    # ---------------------------------------------------------
    def ask(self, query: str) -> Dict[str, Any]:
        """Main agent query method with enhanced error handling"""
        
        # Validate input
        if not query or not isinstance(query, str):
            raise ValidationError("Query must be a non-empty string", "query", query)
        
        if len(query) > 1000:
            raise ValidationError("Query too long (max 1000 chars)", "query", query)
        
        logger.info(f"SOA1 received query: {query}")

        # 1. Search memory
        try:
            memories = self.memory.search_memory(query)
        except Exception as e:
            logger.error(f"Memory search failed: {e}")
            raise ServiceError("memory", f"Memory search failed: {str(e)}")

        memory_context = self._format_memory_context(memories)

        # 2. Build model conversation
        convo = [
            {
                "role": "user",
                "content": (
                    "Here is relevant context from past memories:\n"
                    f"{memory_context}\n\n"
                    f"Now answer the following question for the user:\n{query}"
                ),
            }
        ]

        # 3. Model inference
        try:
            answer = self.model.chat(self.system_prompt, convo)
        except Exception as e:
            logger.error(f"Model call failed: {e}")
            raise ServiceError("model", f"Model inference failed: {str(e)}")

        # 4. Write new factual memory (with explicit time)
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
                    "recorded_epoch": int(timestamp.timestamp())
                }
            )

        except Exception as e:
            logger.warning(f"Memory write failed (non-critical): {e}")
            # Non-critical failure - continue

        # 5. Return agent output
        return {
            "answer": answer,
            "used_memories": memories,
        }
