#!/usr/bin/env python3
"""
Model Manager - Auto-initialization and health checking for Ollama models
Runs on WebUI startup to ensure required models are loaded with correct prompts
"""

import requests
import logging
import yaml
import time
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger("model-manager")


@dataclass
class ModelConfig:
    """Configuration for a model to be loaded"""

    name: str
    display_name: str
    gpu: int
    system_prompt: str
    temperature: float = 0.3
    num_ctx: int = 4096  # Context window size (tokens)
    required: bool = True


@dataclass
class LoadedModel:
    """Information about a currently loaded model"""

    name: str
    size: int
    size_vram: int
    processor: str  # "100% GPU" or similar


class OllamaManager:
    """Manages Ollama models - checking status, loading, and health monitoring"""

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.timeout = 5

    def is_running(self) -> bool:
        """Check if Ollama service is running"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=self.timeout)
            return response.status_code == 200
        except requests.exceptions.RequestException as e:
            logger.error(f"Ollama not reachable: {e}")
            return False

    def get_available_models(self) -> List[str]:
        """Get list of available models in Ollama"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            return [model["name"] for model in data.get("models", [])]
        except Exception as e:
            logger.error(f"Failed to get available models: {e}")
            return []

    def get_loaded_models(self) -> Dict[str, LoadedModel]:
        """Get currently loaded models (in memory)"""
        try:
            response = requests.get(f"{self.base_url}/api/ps", timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            loaded = {}
            for model_info in data.get("models", []):
                name = model_info.get("name", "")
                loaded[name] = LoadedModel(
                    name=name,
                    size=model_info.get("size", 0),
                    size_vram=model_info.get("size_vram", 0),
                    processor=model_info.get("details", {}).get("parameter_size", ""),
                )

            return loaded
        except Exception as e:
            logger.error(f"Failed to get loaded models: {e}")
            return {}

    def load_model(
        self,
        model_name: str,
        system_prompt: str,
        temperature: float = 0.3,
        num_ctx: int = 4096,
    ) -> Tuple[bool, Optional[str]]:
        """
        Load a model into memory with a specific system prompt
        Returns (success, error_message)
        """
        try:
            logger.info(
                f"Loading model: {model_name} (temp={temperature}, ctx={num_ctx})"
            )

            payload = {
                "model": model_name,
                "prompt": "Hello",
                "system": system_prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_ctx": num_ctx,
                    "num_gpu": 99,
                },
                "keep_alive": -1,
            }

            # Diagnostic logging for outgoing Ollama request
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            logger.info(
                f"[OLLAMA-REQ] {timestamp} | Endpoint: /api/generate | Model: {model_name} | Payload: {payload}"
            )

            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=60,
            )
            response.raise_for_status()

            logger.info(f"✅ Model loaded: {model_name}")
            return True, None

        except requests.exceptions.Timeout:
            error = f"Timeout loading {model_name} (may still be loading in background)"
            logger.warning(error)
            return False, error
        except Exception as e:
            error = f"Failed to load {model_name}: {str(e)}"
            logger.error(error)
            return False, error

    def get_model_info(self, model_name: str) -> Optional[Dict]:
        """Get detailed information about a specific model"""
        try:
            response = requests.post(
                f"{self.base_url}/api/show",
                json={"name": model_name},
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get info for {model_name}: {e}")
            return None


class ModelInitializer:
    """Handles model initialization on WebUI startup"""

    def __init__(
        self, config_path: str = "/home/ryzen/projects/home-ai/soa1/config.yaml"
    ):
        self.config_path = config_path
        self.ollama = OllamaManager()
        self.models_config: List[ModelConfig] = []

    def load_config(self) -> bool:
        """Load model configuration from config.yaml"""
        try:
            with open(self.config_path, "r") as f:
                config = yaml.safe_load(f)

            # Extract orchestrator config
            orchestrator = config.get("orchestrator", {})
            self.models_config.append(
                ModelConfig(
                    name=orchestrator.get("model_name", "NemoAgent"),
                    display_name="NemoAgent Orchestrator",
                    gpu=0,
                    system_prompt=orchestrator.get("system_prompt", ""),
                    temperature=orchestrator.get("temperature", 0.3),
                    num_ctx=32768,
                    required=True,
                )
            )

            # Extract specialist configs
            specialists = config.get("specialists", {})

            # Finance specialist
            finance = specialists.get("finance", {})
            if finance.get("enabled", True):
                self.models_config.append(
                    ModelConfig(
                        name=finance.get("model_name", "phinance-json"),
                        display_name="Finance Specialist",
                        gpu=1,
                        system_prompt=finance.get("system_prompt", ""),
                        temperature=finance.get("temperature", 0.05),
                        num_ctx=4096,
                        required=True,
                    )
                )

            logger.info(f"Loaded configuration for {len(self.models_config)} models")
            return True

        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return False

    def initialize_models(self) -> Dict[str, bool]:
        """
        Initialize all required models
        Returns dict of {model_name: success_status}
        """
        results = {}

        # Step 1: Check if Ollama is running
        logger.info("Checking Ollama status...")
        if not self.ollama.is_running():
            logger.error("❌ Ollama is not running. Please start Ollama first.")
            return {model.name: False for model in self.models_config}

        logger.info("✅ Ollama is running")

        # Step 2: Get available models
        available = self.ollama.get_available_models()
        logger.info(f"Available models: {', '.join(available)}")

        # Step 3: Get currently loaded models
        loaded = self.ollama.get_loaded_models()
        logger.info(f"Currently loaded: {', '.join(loaded.keys())}")

        # Step 4: Load each required model
        for model_config in self.models_config:
            model_name = model_config.name

            # Resolve the model name against available models (support 'name' and 'name:latest')
            def _resolve_name(
                requested: str, available_list: List[str]
            ) -> Optional[str]:
                if requested in available_list:
                    return requested
                candidate = f"{requested}:latest"
                if candidate in available_list:
                    return candidate
                for m in available_list:
                    if m.startswith(requested):
                        return m
                return None

            resolved_name = _resolve_name(model_name, available)
            if resolved_name is None:
                logger.error(f"\u274c Model not found: {model_name}")
                if model_config.required:
                    logger.error(
                        f"   This is a REQUIRED model. Please install it first."
                    )
                results[model_name] = False
                continue

            # Check if already loaded (use resolved name)
            if resolved_name in loaded:
                logger.info(f"\u2705 Model already loaded: {resolved_name}")
                results[model_name] = True
                continue

            # Load the model using the resolved name
            logger.info(f"Loading {model_config.display_name} as {resolved_name}...")
            success, error = self.ollama.load_model(
                resolved_name,
                model_config.system_prompt,
                model_config.temperature,
                model_config.num_ctx,
            )
            results[model_name] = success

            if not success and model_config.required:
                logger.error(f"\u274c Failed to load REQUIRED model: {resolved_name}")
                if error:
                    logger.error(f"   Error: {error}")

        return results

    def get_status_report(self) -> Dict:
        """Get comprehensive status report for monitoring"""
        report = {
            "ollama_running": self.ollama.is_running(),
            "available_models": [],
            "loaded_models": {},
            "configured_models": [],
            "initialization_required": False,
        }

        if not report["ollama_running"]:
            return report

        # Get available and loaded models
        report["available_models"] = self.ollama.get_available_models()
        loaded = self.ollama.get_loaded_models()
        report["loaded_models"] = {
            name: {
                "size_mb": model.size // (1024 * 1024),
                "vram_mb": model.size_vram // (1024 * 1024),
                "processor": model.processor,
            }
            for name, model in loaded.items()
        }

        # Check configured models
        for model_config in self.models_config:
            status = {
                "name": model_config.name,
                "display_name": model_config.display_name,
                "gpu": model_config.gpu,
                "required": model_config.required,
                "available": model_config.name in report["available_models"],
                "loaded": model_config.name in loaded,
            }
            report["configured_models"].append(status)

            # Check if initialization needed
            if model_config.required and not status["loaded"]:
                report["initialization_required"] = True

        return report


def initialize_on_startup(
    config_path: str = "/home/ryzen/projects/home-ai/soa1/config.yaml",
) -> Dict:
    """
    Main entry point - called on WebUI startup
    Returns status report
    """
    logger.info("=" * 60)
    logger.info("MODEL INITIALIZATION STARTING")
    logger.info("=" * 60)

    initializer = ModelInitializer(config_path)

    # Load configuration
    if not initializer.load_config():
        logger.error("Failed to load configuration")
        return {"success": False, "error": "Configuration load failed"}

    # Initialize models
    results = initializer.initialize_models()

    # Get final status
    status = initializer.get_status_report()

    # Summary
    logger.info("=" * 60)
    logger.info("MODEL INITIALIZATION COMPLETE")
    logger.info("=" * 60)

    success_count = sum(1 for success in results.values() if success)
    total_count = len(results)

    logger.info(f"Results: {success_count}/{total_count} models loaded successfully")

    for model_name, success in results.items():
        status_icon = "✅" if success else "❌"
        logger.info(f"  {status_icon} {model_name}")

    return {
        "success": success_count == total_count,
        "results": results,
        "status": status,
    }


if __name__ == "__main__":
    # Test run
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    result = initialize_on_startup()

    if result["success"]:
        print("\n✅ All models initialized successfully!")
    else:
        print("\n⚠️ Some models failed to initialize")
        print("Check logs above for details")
