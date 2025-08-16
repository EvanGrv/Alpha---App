"""Service VAD (Voice Activity Detection) pour détecter la parole."""

import asyncio
import logging
import numpy as np
from typing import List, Optional, Callable
from pydantic import BaseModel

from packages.common.config import Config
from packages.common.errors import VoiceError

try:
    import webrtcvad
    import pyaudio
    HAS_VAD_DEPS = True
except ImportError:
    HAS_VAD_DEPS = False


class AudioFrame(BaseModel):
    """Frame audio pour VAD."""
    data: bytes
    timestamp: float
    is_speech: bool


class VADConfig(BaseModel):
    """Configuration VAD."""
    sample_rate: int = 16000
    frame_duration_ms: int = 30  # 10, 20 ou 30ms
    aggressiveness: int = 2  # 0-3, plus élevé = plus agressif
    buffer_size: int = 1024


class VADService:
    """Service de détection d'activité vocale."""
    
    def __init__(self, config: Config):
        if not HAS_VAD_DEPS:
            raise VoiceError("Dépendances VAD manquantes: pip install webrtcvad pyaudio")
            
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Configuration VAD
        self.vad_config = VADConfig(
            sample_rate=config.get('voice.sample_rate', 16000),
            frame_duration_ms=config.get('voice.frame_duration_ms', 30),
            aggressiveness=config.get('voice.vad_aggressiveness', 2),
            buffer_size=config.get('voice.buffer_size', 1024)
        )
        
        # Initialiser WebRTC VAD
        self.vad = webrtcvad.Vad()
        self.vad.set_mode(self.vad_config.aggressiveness)
        
        # Audio
        self.audio = None
        self.stream = None
        self.is_recording = False
        
        # Callbacks
        self.speech_start_callback: Optional[Callable] = None
        self.speech_end_callback: Optional[Callable] = None
        self.audio_data_callback: Optional[Callable[[bytes], None]] = None
        
        # Buffer pour l'audio
        self.audio_buffer: List[bytes] = []
        self.speech_frames = 0
        self.silence_frames = 0
        
        # Seuils
        self.min_speech_frames = 3  # Minimum de frames de parole pour déclencher
        self.max_silence_frames = 10  # Maximum de frames de silence avant arrêt
        
    async def initialize(self) -> None:
        """Initialise le service VAD."""
        try:
            self.audio = pyaudio.PyAudio()
            self.logger.info("Service VAD initialisé")
        except Exception as e:
            raise VoiceError(f"Erreur d'initialisation VAD: {e}")
    
    def set_callbacks(self, 
                     speech_start: Optional[Callable] = None,
                     speech_end: Optional[Callable] = None,
                     audio_data: Optional[Callable[[bytes], None]] = None) -> None:
        """Configure les callbacks."""
        self.speech_start_callback = speech_start
        self.speech_end_callback = speech_end
        self.audio_data_callback = audio_data
    
    async def start_monitoring(self) -> None:
        """Démarre la surveillance audio continue."""
        if self.is_recording:
            self.logger.warning("Surveillance déjà active")
            return
            
        try:
            # Ouvrir le stream audio
            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.vad_config.sample_rate,
                input=True,
                frames_per_buffer=self.vad_config.buffer_size,
                stream_callback=self._audio_callback
            )
            
            self.is_recording = True
            self.stream.start_stream()
            
            self.logger.info("Surveillance VAD démarrée")
            
        except Exception as e:
            raise VoiceError(f"Erreur de démarrage VAD: {e}")
    
    async def stop_monitoring(self) -> None:
        """Arrête la surveillance audio."""
        if not self.is_recording:
            return
            
        self.is_recording = False
        
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
            
        self.audio_buffer.clear()
        self.speech_frames = 0
        self.silence_frames = 0
        
        self.logger.info("Surveillance VAD arrêtée")
    
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """Callback pour traitement audio en temps réel."""
        if not self.is_recording:
            return (None, pyaudio.paComplete)
            
        try:
            # Détecter la parole dans cette frame
            is_speech = self._is_speech_frame(in_data)
            
            if is_speech:
                self.speech_frames += 1
                self.silence_frames = 0
                
                # Ajouter à l'audio buffer
                self.audio_buffer.append(in_data)
                
                # Déclencher le début de parole si nécessaire
                if self.speech_frames == self.min_speech_frames and self.speech_start_callback:
                    asyncio.create_task(self._call_speech_start())
                    
            else:
                self.silence_frames += 1
                
                # Si on était en train de parler, continuer à buffer un peu
                if self.speech_frames >= self.min_speech_frames:
                    self.audio_buffer.append(in_data)
                    
                    # Arrêter si trop de silence
                    if self.silence_frames >= self.max_silence_frames:
                        asyncio.create_task(self._call_speech_end())
                        self._reset_speech_detection()
            
            # Callback pour données audio brutes si configuré
            if self.audio_data_callback:
                asyncio.create_task(self._call_audio_data(in_data))
                
        except Exception as e:
            self.logger.error(f"Erreur dans callback audio: {e}")
            
        return (None, pyaudio.paContinue)
    
    def _is_speech_frame(self, frame_data: bytes) -> bool:
        """Détermine si une frame contient de la parole."""
        try:
            # WebRTC VAD nécessite des frames de taille spécifique
            frame_size = int(self.vad_config.sample_rate * self.vad_config.frame_duration_ms / 1000)
            
            if len(frame_data) < frame_size * 2:  # 2 bytes par sample (16-bit)
                return False
                
            # Prendre seulement la taille requise
            vad_frame = frame_data[:frame_size * 2]
            
            return self.vad.is_speech(vad_frame, self.vad_config.sample_rate)
            
        except Exception as e:
            self.logger.debug(f"Erreur VAD: {e}")
            return False
    
    async def _call_speech_start(self) -> None:
        """Appelle le callback de début de parole."""
        if self.speech_start_callback:
            try:
                await self.speech_start_callback()
            except Exception as e:
                self.logger.error(f"Erreur callback speech_start: {e}")
    
    async def _call_speech_end(self) -> None:
        """Appelle le callback de fin de parole avec l'audio."""
        if self.speech_end_callback and self.audio_buffer:
            try:
                # Combiner tous les frames audio
                audio_data = b''.join(self.audio_buffer)
                await self.speech_end_callback(audio_data)
            except Exception as e:
                self.logger.error(f"Erreur callback speech_end: {e}")
    
    async def _call_audio_data(self, data: bytes) -> None:
        """Appelle le callback pour données audio."""
        if self.audio_data_callback:
            try:
                self.audio_data_callback(data)
            except Exception as e:
                self.logger.error(f"Erreur callback audio_data: {e}")
    
    def _reset_speech_detection(self) -> None:
        """Remet à zéro la détection de parole."""
        self.audio_buffer.clear()
        self.speech_frames = 0
        self.silence_frames = 0
    
    def get_audio_buffer(self) -> bytes:
        """Retourne l'audio buffer actuel."""
        return b''.join(self.audio_buffer)
    
    async def cleanup(self) -> None:
        """Nettoie les ressources."""
        await self.stop_monitoring()
        
        if self.audio:
            self.audio.terminate()
            self.audio = None
            
        self.logger.info("Service VAD nettoyé")