#!/usr/bin/env python3
"""
VibeVoice TTS Service for SOA1
Local-only text-to-speech using Microsoft VibeVoice-Realtime-0.5B
"""

from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
import soundfile as sf
import numpy as np
import os
from typing import Optional, Dict, Any
import logging
from datetime import datetime

# Set up logging
logger = logging.getLogger("tts")

class VibeVoiceTTS:
    def __init__(self, model_name: str = "microsoft/VibeVoice-Realtime-0.5B", 
                 device: Optional[str] = None):
        """Initialize VibeVoice TTS model"""
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model_name = model_name
        self.model = None
        self.tokenizer = None
        self.loaded = False
        
        logger.info(f"VibeVoice TTS service initialized (device: {self.device})")

    def load_model(self):
        """Load the TTS model"""
        if self.loaded:
            return
        
        try:
            logger.info(f"Loading VibeVoice model: {self.model_name}")
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name
            ).to(self.device)
            self.loaded = True
            logger.info("VibeVoice model loaded successfully!")
        except Exception as e:
            logger.error(f"Failed to load VibeVoice model: {e}")
            raise

    def text_to_speech(
        self,
        text: str,
        output_path: str = "output.wav",
        speaker_id: int = 0,
        sample_rate: int = 24000
    ) -> Dict[str, Any]:
        """Convert text to speech using VibeVoice"""
        if not self.loaded:
            self.load_model()
        
        try:
            # Tokenize input
            inputs = self.tokenizer(text, return_tensors="pt").to(self.device)

            # Generate speech
            with torch.no_grad():
                outputs = self.model.generate(**inputs)

            # Convert to audio
            audio = outputs.cpu().numpy()
            
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Save as WAV file
            sf.write(output_path, audio, sample_rate)
            
            return {
                "status": "success",
                "audio_path": output_path,
                "duration": len(audio) / sample_rate,
                "sample_rate": sample_rate,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"TTS generation failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    def is_available(self) -> bool:
        """Check if TTS service is available"""
        return self.loaded

# Singleton instance
tts_service = VibeVoiceTTS()

if __name__ == "__main__":
    # Test the service
    result = tts_service.text_to_speech("Hello, this is a test of VibeVoice TTS!")
    print(f"TTS Result: {result}")