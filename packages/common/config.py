"""
Configuration système pour Desktop Agent.

Gère le chargement de la configuration depuis YAML et variables d'environnement.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .models import Platform


class DatabaseConfig(BaseModel):
    """Configuration de la base de données."""
    url: str = Field(default="sqlite:///data/agent.db", description="URL de connexion")
    echo: bool = Field(default=False, description="Activer les logs SQL")
    pool_size: int = Field(default=5, description="Taille du pool de connexions")


class LoggingConfig(BaseModel):
    """Configuration du système de logging."""
    level: str = Field(default="INFO", description="Niveau de log")
    format: str = Field(default="json", description="Format: json ou text")
    file_path: Optional[str] = Field(default="logs/agent.log", description="Fichier de log")
    max_file_size: str = Field(default="10MB", description="Taille max du fichier")
    backup_count: int = Field(default=5, description="Nombre de fichiers de backup")
    structured: bool = Field(default=True, description="Utiliser structlog")


class PerceptionConfig(BaseModel):
    """Configuration du système de perception."""
    screenshot_interval: float = Field(default=0.1, description="Intervalle captures (secondes)")
    ocr_confidence_threshold: float = Field(default=0.5, description="Seuil confiance OCR")
    ocr_language: str = Field(default="fr+en", description="Langues OCR")
    max_ui_elements: int = Field(default=1000, description="Max éléments UI par observation")
    cache_screenshots: bool = Field(default=True, description="Cache des captures")
    screenshot_compression: str = Field(default="png", description="Format compression")


class VoiceConfig(BaseModel):
    """Configuration du système vocal."""
    whisper_model: str = Field(default="base", description="Modèle Whisper")
    sample_rate: int = Field(default=16000, description="Fréquence d'échantillonnage")
    chunk_duration: float = Field(default=0.5, description="Durée chunks audio (secondes)")
    vad_aggressiveness: int = Field(default=2, description="Agressivité VAD (0-3)")
    push_to_talk_key: str = Field(default="alt+space", description="Raccourci push-to-talk")
    silence_timeout: float = Field(default=2.0, description="Timeout silence (secondes)")


class UIConfig(BaseModel):
    """Configuration de l'interface utilisateur."""
    overlay_hotkey: str = Field(default="ctrl+grave", description="Raccourci toggle overlay")
    overlay_height: int = Field(default=60, description="Hauteur overlay (pixels)")
    overlay_opacity: float = Field(default=0.9, description="Opacité overlay")
    theme: str = Field(default="dark", description="Thème UI")
    font_size: int = Field(default=14, description="Taille police")
    auto_hide_delay: float = Field(default=5.0, description="Délai masquage auto (secondes)")


class SecurityConfig(BaseModel):
    """Configuration sécurité."""
    require_confirmation_for_write: bool = Field(default=True, description="Confirmer écritures")
    require_confirmation_for_delete: bool = Field(default=True, description="Confirmer suppressions")
    allowed_write_paths: List[str] = Field(
        default_factory=lambda: ["~/Documents", "~/Desktop", "~/Downloads"],
        description="Chemins d'écriture autorisés"
    )
    blocked_apps: List[str] = Field(
        default_factory=lambda: ["cmd", "powershell", "terminal"],
        description="Applications bloquées"
    )
    max_execution_time: float = Field(default=300.0, description="Temps max exécution (secondes)")


class RLConfig(BaseModel):
    """Configuration Reinforcement Learning."""
    environment_name: str = Field(default="DesktopAgent-v0", description="Nom environnement")
    observation_size: tuple[int, int] = Field(default=(224, 224), description="Taille observations")
    action_space_size: int = Field(default=10, description="Taille espace actions")
    reward_shaping: bool = Field(default=True, description="Façonnage récompenses")
    episode_max_steps: int = Field(default=100, description="Max étapes par épisode")
    training_episodes: int = Field(default=1000, description="Épisodes d'entraînement")
    model_save_interval: int = Field(default=100, description="Intervalle sauvegarde modèle")


class AgentSettings(BaseSettings):
    """Configuration principale de l'agent."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="AGENT_"
    )
    
    # Informations générales
    name: str = Field(default="Desktop Agent", description="Nom de l'agent")
    version: str = Field(default="0.1.0", description="Version")
    platform: Platform = Field(default=Platform.WINDOWS, description="Plateforme OS")
    debug: bool = Field(default=False, description="Mode debug")
    
    # Chemins
    data_dir: Path = Field(default=Path("data"), description="Répertoire données")
    logs_dir: Path = Field(default=Path("logs"), description="Répertoire logs")
    models_dir: Path = Field(default=Path("data/models"), description="Répertoire modèles")
    demos_dir: Path = Field(default=Path("data/demos"), description="Répertoire démos")
    
    # API
    api_host: str = Field(default="127.0.0.1", description="Host API")
    api_port: int = Field(default=8000, description="Port API")
    api_reload: bool = Field(default=False, description="Rechargement auto API")
    cors_origins: List[str] = Field(default_factory=lambda: ["*"], description="Origines CORS")
    
    # Configurations des modules
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    perception: PerceptionConfig = Field(default_factory=PerceptionConfig)
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    rl: RLConfig = Field(default_factory=RLConfig)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Créer les répertoires nécessaires
        self.data_dir.mkdir(exist_ok=True)
        self.logs_dir.mkdir(exist_ok=True)
        self.models_dir.mkdir(exist_ok=True, parents=True)
        self.demos_dir.mkdir(exist_ok=True, parents=True)


class ConfigLoader:
    """Chargeur de configuration avec support YAML et environnement."""
    
    @staticmethod
    def load_from_file(config_path: str | Path) -> Dict[str, Any]:
        """Charge la configuration depuis un fichier YAML."""
        config_path = Path(config_path)
        if not config_path.exists():
            return {}
        
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    
    @staticmethod
    def load_settings(config_file: Optional[str] = None) -> AgentSettings:
        """Charge les paramètres complets de l'agent."""
        config_data = {}
        
        # Charger depuis fichier YAML si spécifié
        if config_file:
            config_data = ConfigLoader.load_from_file(config_file)
        
        # Chercher config.yaml dans le répertoire courant
        elif Path("config.yaml").exists():
            config_data = ConfigLoader.load_from_file("config.yaml")
        
        # Créer les settings (variables d'environnement prendront le dessus)
        return AgentSettings(**config_data)
    
    @staticmethod
    def save_to_file(settings: AgentSettings, config_path: str | Path) -> None:
        """Sauvegarde la configuration dans un fichier YAML."""
        config_path = Path(config_path)
        config_data = settings.model_dump(exclude={"model_config"})
        
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)


# Instance globale des settings
_settings: Optional[AgentSettings] = None


def get_settings() -> AgentSettings:
    """Récupère l'instance globale des settings."""
    global _settings
    if _settings is None:
        _settings = ConfigLoader.load_settings()
    return _settings


def reload_settings(config_file: Optional[str] = None) -> AgentSettings:
    """Recharge les settings."""
    global _settings
    _settings = ConfigLoader.load_settings(config_file)
    return _settings


# Configuration par défaut pour le développement
DEFAULT_CONFIG = {
    "debug": True,
    "api_reload": True,
    "logging": {
        "level": "DEBUG",
        "format": "text"
    },
    "perception": {
        "screenshot_interval": 0.5,
        "cache_screenshots": False
    },
    "security": {
        "require_confirmation_for_write": False
    }
}