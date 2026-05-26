"""Wrapper Whisper : transcrit des buffers audio PCM 16 kHz mono."""
from __future__ import annotations

import io
import numpy as np
import whisper


class WhisperRecognizer:
    def __init__(self, model_name: str = "small", language: str = "french"):
        print(f"📥 Chargement du modèle Whisper '{model_name}'...")
        self.model = whisper.load_model(model_name)
        self.language = language
        print("✅ Whisper prêt")

    def transcribe_pcm16(self, pcm_bytes: bytes, sample_rate: int = 16000) -> str:
        """Transcrit un buffer PCM 16-bit mono.
        Whisper attend du float32 normalisé à [-1, 1]."""
        if not pcm_bytes:
            return ""
        # Conversion int16 → float32 normalisé
        audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        if audio.size < sample_rate // 4:  # < 0.25s : ignore
            return ""
        result = self.model.transcribe(
            audio,
            language=self.language,
            fp16=False,
            no_speech_threshold=0.6,
        )
        return result.get("text", "").strip()
