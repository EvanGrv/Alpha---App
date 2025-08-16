"""
Utilitaires de logging structuré pour Desktop Agent.

Configure structlog avec formatage JSON et rotation des fichiers.
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import structlog
from structlog.types import Processor

from .config import LoggingConfig


def setup_logging(config: LoggingConfig, service_name: str = "desktop-agent") -> None:
    """
    Configure le système de logging structuré.
    
    Args:
        config: Configuration de logging
        service_name: Nom du service pour les logs
    """
    # Configuration du niveau de log
    log_level = getattr(logging, config.level.upper(), logging.INFO)
    
    # Processeurs structlog
    processors: list[Processor] = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    
    # Ajouter des métadonnées par défaut
    processors.append(
        structlog.processors.add_fields(service=service_name)
    )
    
    # Configuration du formatage
    if config.format.lower() == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(
            structlog.dev.ConsoleRenderer(colors=True)
        )
    
    # Configuration structlog
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Configuration du logger standard Python
    handlers = []
    
    # Handler console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    handlers.append(console_handler)
    
    # Handler fichier avec rotation si configuré
    if config.file_path:
        file_path = Path(config.file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Parser la taille max
        max_bytes = _parse_size(config.max_file_size)
        
        file_handler = logging.handlers.RotatingFileHandler(
            filename=file_path,
            maxBytes=max_bytes,
            backupCount=config.backup_count,
            encoding="utf-8"
        )
        file_handler.setLevel(log_level)
        handlers.append(file_handler)
    
    # Configuration du logger racine
    logging.basicConfig(
        handlers=handlers,
        level=log_level,
        format="%(message)s"  # structlog gère le formatage
    )


def _parse_size(size_str: str) -> int:
    """
    Parse une chaîne de taille (ex: '10MB') en bytes.
    
    Args:
        size_str: Chaîne de taille
        
    Returns:
        Taille en bytes
    """
    size_str = size_str.upper().strip()
    
    multipliers = {
        'B': 1,
        'KB': 1024,
        'MB': 1024 * 1024,
        'GB': 1024 * 1024 * 1024
    }
    
    for unit, multiplier in multipliers.items():
        if size_str.endswith(unit):
            number = size_str[:-len(unit)]
            try:
                return int(float(number) * multiplier)
            except ValueError:
                break
    
    # Fallback: supposer que c'est en bytes
    try:
        return int(size_str)
    except ValueError:
        return 10 * 1024 * 1024  # 10MB par défaut


class AgentLogger:
    """Logger spécialisé pour Desktop Agent avec contexte enrichi."""
    
    def __init__(self, name: str, **default_context: Any):
        """
        Initialise le logger.
        
        Args:
            name: Nom du logger
            **default_context: Contexte par défaut à ajouter
        """
        self._logger = structlog.get_logger(name)
        self._default_context = default_context
    
    def _log(self, level: str, message: str, **context: Any) -> None:
        """Log un message avec contexte."""
        full_context = {**self._default_context, **context}
        getattr(self._logger, level)(message, **full_context)
    
    def debug(self, message: str, **context: Any) -> None:
        """Log niveau DEBUG."""
        self._log("debug", message, **context)
    
    def info(self, message: str, **context: Any) -> None:
        """Log niveau INFO."""
        self._log("info", message, **context)
    
    def warning(self, message: str, **context: Any) -> None:
        """Log niveau WARNING."""
        self._log("warning", message, **context)
    
    def error(self, message: str, **context: Any) -> None:
        """Log niveau ERROR."""
        self._log("error", message, **context)
    
    def critical(self, message: str, **context: Any) -> None:
        """Log niveau CRITICAL."""
        self._log("critical", message, **context)
    
    def bind(self, **context: Any) -> "AgentLogger":
        """Crée un nouveau logger avec contexte lié."""
        new_context = {**self._default_context, **context}
        return AgentLogger(self._logger.name, **new_context)
    
    def log_action(self, action_type: str, **details: Any) -> None:
        """Log une action avec formatage standardisé."""
        self.info(
            f"Action exécutée: {action_type}",
            action_type=action_type,
            **details
        )
    
    def log_error(self, error: Exception, context: str = "", **details: Any) -> None:
        """Log une erreur avec contexte."""
        self.error(
            f"Erreur {context}: {str(error)}",
            error_type=type(error).__name__,
            error_message=str(error),
            context=context,
            **details,
            exc_info=True
        )
    
    def log_performance(self, operation: str, duration: float, **details: Any) -> None:
        """Log des métriques de performance."""
        self.info(
            f"Performance {operation}: {duration:.3f}s",
            operation=operation,
            duration_seconds=duration,
            **details
        )
    
    def log_user_action(self, user_id: Optional[str], action: str, **details: Any) -> None:
        """Log une action utilisateur."""
        self.info(
            f"Action utilisateur: {action}",
            user_id=user_id,
            action=action,
            **details
        )


def get_logger(name: str, **context: Any) -> AgentLogger:
    """
    Crée un logger pour un composant.
    
    Args:
        name: Nom du composant
        **context: Contexte par défaut
        
    Returns:
        Logger configuré
    """
    return AgentLogger(name, **context)


# Loggers pré-configurés pour les composants principaux
def get_agent_logger(**context: Any) -> AgentLogger:
    """Logger pour le service agent."""
    return get_logger("agent", **context)


def get_perception_logger(**context: Any) -> AgentLogger:
    """Logger pour le système de perception."""
    return get_logger("perception", **context)


def get_skill_logger(skill_name: str, **context: Any) -> AgentLogger:
    """Logger pour un skill."""
    return get_logger(f"skill.{skill_name}", **context)


def get_planner_logger(**context: Any) -> AgentLogger:
    """Logger pour le planificateur."""
    return get_logger("planner", **context)


def get_nlu_logger(**context: Any) -> AgentLogger:
    """Logger pour le NLU."""
    return get_logger("nlu", **context)


def get_ui_logger(**context: Any) -> AgentLogger:
    """Logger pour l'interface utilisateur."""
    return get_logger("ui", **context)


def get_rl_logger(**context: Any) -> AgentLogger:
    """Logger pour le système RL."""
    return get_logger("rl", **context)