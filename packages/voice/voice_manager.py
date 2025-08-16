"""Manager principal pour la gestion vocale (Whisper + VAD)."""

import asyncio
import logging
from typing import Optional, Callable
from pathlib import Path

from packages.common.config import Config
from packages.common.errors import VoiceError
from .whisper_service import WhisperService, TranscriptionResult
from .vad_service import VADService


class VoiceManager:
    """Manager principal pour les fonctionnalités vocales."""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Services
        self.whisper_service = WhisperService(config)
        self.vad_service = VADService(config)
        
        # État
        self.is_listening = False
        self.push_to_talk_active = False
        
        # Callbacks
        self.transcription_callback: Optional[Callable[[TranscriptionResult], None]] = None
        self.listening_start_callback: Optional[Callable] = None
        self.listening_end_callback: Optional[Callable] = None
        
    async def initialize(self) -> None:
        """Initialise tous les services vocaux."""
        try:
            self.logger.info("Initialisation des services vocaux...")
            
            # Initialiser Whisper
            await self.whisper_service.initialize()
            
            # Initialiser VAD
            await self.vad_service.initialize()
            
            # Configurer les callbacks VAD
            self.vad_service.set_callbacks(
                speech_start=self._on_speech_start,
                speech_end=self._on_speech_end
            )
            
            self.logger.info("Services vocaux initialisés avec succès")
            
        except Exception as e:
            self.logger.error(f"Erreur d'initialisation vocale: {e}")
            raise VoiceError(f"Impossible d'initialiser les services vocaux: {e}")
    
    def set_callbacks(self,
                     transcription: Optional[Callable[[TranscriptionResult], None]] = None,
                     listening_start: Optional[Callable] = None,
                     listening_end: Optional[Callable] = None) -> None:
        """Configure les callbacks."""
        self.transcription_callback = transcription
        self.listening_start_callback = listening_start
        self.listening_end_callback = listening_end
    
    async def start_continuous_listening(self) -> None:
        """Démarre l'écoute continue avec VAD."""
        if self.is_listening:
            self.logger.warning("Écoute déjà active")
            return
            
        try:
            self.is_listening = True
            await self.vad_service.start_monitoring()
            
            if self.listening_start_callback:
                await self.listening_start_callback()
                
            self.logger.info("Écoute continue démarrée")
            
        except Exception as e:
            self.is_listening = False
            raise VoiceError(f"Erreur de démarrage d'écoute: {e}")
    
    async def stop_continuous_listening(self) -> None:
        """Arrête l'écoute continue."""
        if not self.is_listening:
            return
            
        self.is_listening = False
        await self.vad_service.stop_monitoring()
        
        if self.listening_end_callback:
            await self.listening_end_callback()
            
        self.logger.info("Écoute continue arrêtée")
    
    async def start_push_to_talk(self) -> None:
        """Démarre le mode push-to-talk."""
        if self.push_to_talk_active:
            self.logger.warning("Push-to-talk déjà actif")
            return
            
        try:
            self.push_to_talk_active = True
            await self.vad_service.start_monitoring()
            
            self.logger.info("Push-to-talk activé")
            
        except Exception as e:
            self.push_to_talk_active = False
            raise VoiceError(f"Erreur push-to-talk: {e}")
    
    async def stop_push_to_talk(self) -> None:
        """Arrête le mode push-to-talk et traite l'audio."""
        if not self.push_to_talk_active:
            return
            
        try:
            # Récupérer l'audio buffer
            audio_data = self.vad_service.get_audio_buffer()
            
            # Arrêter la surveillance
            self.push_to_talk_active = False
            await self.vad_service.stop_monitoring()
            
            # Transcrire si on a de l'audio
            if audio_data and len(audio_data) > 1000:  # Minimum de données
                try:
                    result = await self.whisper_service.transcribe_audio_data(audio_data)
                    
                    if self.transcription_callback and result.text.strip():
                        await self.transcription_callback(result)
                        
                except Exception as e:
                    self.logger.error(f"Erreur de transcription push-to-talk: {e}")
            
            self.logger.info("Push-to-talk arrêté")
            
        except Exception as e:
            self.push_to_talk_active = False
            raise VoiceError(f"Erreur arrêt push-to-talk: {e}")
    
    async def transcribe_file(self, audio_path: Path) -> TranscriptionResult:
        """Transcrit un fichier audio."""
        return await self.whisper_service.transcribe_audio_file(audio_path)
    
    async def _on_speech_start(self) -> None:
        """Callback appelé au début de la détection de parole."""
        self.logger.debug("Début de parole détecté")
        
        if self.listening_start_callback:
            try:
                await self.listening_start_callback()
            except Exception as e:
                self.logger.error(f"Erreur callback listening_start: {e}")
    
    async def _on_speech_end(self, audio_data: bytes) -> None:
        """Callback appelé à la fin de la détection de parole."""
        self.logger.debug("Fin de parole détectée, transcription...")
        
        try:
            # Transcrire l'audio
            result = await self.whisper_service.transcribe_audio_data(audio_data)
            
            # Appeler le callback si on a du texte
            if self.transcription_callback and result.text.strip():
                await self.transcription_callback(result)
                
        except Exception as e:
            self.logger.error(f"Erreur de transcription: {e}")
        
        if self.listening_end_callback:
            try:
                await self.listening_end_callback()
            except Exception as e:
                self.logger.error(f"Erreur callback listening_end: {e}")
    
    def is_initialized(self) -> bool:
        """Vérifie si tous les services sont initialisés."""
        return (self.whisper_service.is_initialized() and 
                self.vad_service is not None)
    
    async def cleanup(self) -> None:
        """Nettoie toutes les ressources."""
        try:
            await self.stop_continuous_listening()
            await self.stop_push_to_talk()
            
            await self.whisper_service.cleanup()
            await self.vad_service.cleanup()
            
            self.logger.info("Voice Manager nettoyé")
            
        except Exception as e:
            self.logger.error(f"Erreur lors du nettoyage: {e}")