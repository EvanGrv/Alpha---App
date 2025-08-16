"""Service Whisper pour la reconnaissance vocale locale."""

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Optional

import whisper
import torch
from pydantic import BaseModel

from packages.common.config import Config
from packages.common.errors import VoiceError


class TranscriptionResult(BaseModel):
    """Résultat de transcription."""
    text: str
    language: str
    confidence: float
    duration: float


class WhisperService:
    """Service de transcription vocale avec Whisper."""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.model = None
        self.model_name = config.get('voice.whisper_model', 'base')
        self.device = self._get_device()
        
    def _get_device(self) -> str:
        """Détermine le device à utiliser (CPU/GPU)."""
        if torch.cuda.is_available():
            return "cuda"
        elif torch.backends.mps.is_available():
            return "mps"
        else:
            return "cpu"
    
    async def initialize(self) -> None:
        """Initialise le modèle Whisper."""
        try:
            self.logger.info(f"Chargement du modèle Whisper '{self.model_name}' sur {self.device}")
            
            # Charger le modèle de manière asynchrone
            loop = asyncio.get_event_loop()
            self.model = await loop.run_in_executor(
                None, 
                lambda: whisper.load_model(self.model_name, device=self.device)
            )
            
            self.logger.info("Modèle Whisper chargé avec succès")
            
        except Exception as e:
            self.logger.error(f"Erreur lors du chargement de Whisper: {e}")
            raise VoiceError(f"Impossible de charger Whisper: {e}")
    
    async def transcribe_audio_file(self, audio_path: Path) -> TranscriptionResult:
        """Transcrit un fichier audio."""
        if not self.model:
            raise VoiceError("Modèle Whisper non initialisé")
            
        if not audio_path.exists():
            raise VoiceError(f"Fichier audio non trouvé: {audio_path}")
        
        try:
            self.logger.debug(f"Transcription de {audio_path}")
            
            # Transcription asynchrone
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.model.transcribe(
                    str(audio_path),
                    language='fr',  # Force le français
                    task='transcribe'
                )
            )
            
            # Extraire les informations
            text = result['text'].strip()
            language = result.get('language', 'fr')
            duration = result.get('duration', 0.0)
            
            # Calculer une confiance approximative basée sur la probabilité moyenne
            segments = result.get('segments', [])
            if segments:
                avg_prob = sum(seg.get('avg_logprob', -1.0) for seg in segments) / len(segments)
                confidence = max(0.0, min(1.0, (avg_prob + 1.0)))  # Normaliser entre 0 et 1
            else:
                confidence = 0.5
            
            self.logger.info(f"Transcription réussie: '{text}' (confiance: {confidence:.2f})")
            
            return TranscriptionResult(
                text=text,
                language=language,
                confidence=confidence,
                duration=duration
            )
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la transcription: {e}")
            raise VoiceError(f"Erreur de transcription: {e}")
    
    async def transcribe_audio_data(self, audio_data: bytes) -> TranscriptionResult:
        """Transcrit des données audio brutes."""
        # Sauvegarder temporairement les données
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
            tmp_file.write(audio_data)
            tmp_path = Path(tmp_file.name)
        
        try:
            return await self.transcribe_audio_file(tmp_path)
        finally:
            # Nettoyer le fichier temporaire
            tmp_path.unlink(missing_ok=True)
    
    def is_initialized(self) -> bool:
        """Vérifie si le service est initialisé."""
        return self.model is not None
    
    async def cleanup(self) -> None:
        """Nettoie les ressources."""
        if self.model:
            # Libérer la mémoire GPU si applicable
            if self.device != "cpu":
                torch.cuda.empty_cache() if self.device == "cuda" else None
            self.model = None
            self.logger.info("Service Whisper nettoyé")