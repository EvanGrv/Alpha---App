"""
Classes d'erreurs personnalisées pour Desktop Agent.

Définit une hiérarchie d'exceptions pour une gestion d'erreurs précise.
"""

from typing import Any, Dict, Optional


class DesktopAgentError(Exception):
    """Exception de base pour Desktop Agent."""
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}


class ConfigurationError(DesktopAgentError):
    """Erreur de configuration."""
    pass


class PerceptionError(DesktopAgentError):
    """Erreur du système de perception."""
    pass


class ScreenCaptureError(PerceptionError):
    """Erreur de capture d'écran."""
    pass


class OCRError(PerceptionError):
    """Erreur OCR."""
    pass


class AccessibilityError(PerceptionError):
    """Erreur d'accessibilité."""
    pass


class SkillError(DesktopAgentError):
    """Erreur d'exécution de skill."""
    pass


class AppNotFoundError(SkillError):
    """Application non trouvée."""
    pass


class ElementNotFoundError(SkillError):
    """Élément UI non trouvé."""
    pass


class ActionFailedError(SkillError):
    """Action échouée."""
    pass


class TimeoutError(SkillError):
    """Timeout d'exécution."""
    pass


class NLUError(DesktopAgentError):
    """Erreur de compréhension du langage naturel."""
    pass


class IntentParsingError(NLUError):
    """Erreur de parsing d'intention."""
    pass


class SlotExtractionError(NLUError):
    """Erreur d'extraction de slots."""
    pass


class PlannerError(DesktopAgentError):
    """Erreur du planificateur."""
    pass


class PlanGenerationError(PlannerError):
    """Erreur de génération de plan."""
    pass


class PlanValidationError(PlannerError):
    """Erreur de validation de plan."""
    pass


class SecurityError(DesktopAgentError):
    """Erreur de sécurité."""
    pass


class PermissionDeniedError(SecurityError):
    """Permission refusée."""
    pass


class UnsafeOperationError(SecurityError):
    """Opération non sécurisée."""
    pass


class OSAdapterError(DesktopAgentError):
    """Erreur d'adaptateur OS."""
    pass


class PlatformNotSupportedError(OSAdapterError):
    """Plateforme non supportée."""
    pass


class SystemCallError(OSAdapterError):
    """Erreur d'appel système."""
    pass


class VoiceError(DesktopAgentError):
    """Erreur du système vocal."""
    pass


class AudioCaptureError(VoiceError):
    """Erreur de capture audio."""
    pass


class SpeechRecognitionError(VoiceError):
    """Erreur de reconnaissance vocale."""
    pass


class UIError(DesktopAgentError):
    """Erreur d'interface utilisateur."""
    pass


class OverlayError(UIError):
    """Erreur d'overlay."""
    pass


class HotkeyError(UIError):
    """Erreur de raccourci clavier."""
    pass


class RLError(DesktopAgentError):
    """Erreur du système RL."""
    pass


class EnvironmentError(RLError):
    """Erreur d'environnement RL."""
    pass


class PolicyError(RLError):
    """Erreur de politique RL."""
    pass


class TrainingError(RLError):
    """Erreur d'entraînement."""
    pass


class DatabaseError(DesktopAgentError):
    """Erreur de base de données."""
    pass


class ReplayError(DesktopAgentError):
    """Erreur de replay."""
    pass


class EpisodeNotFoundError(ReplayError):
    """Épisode non trouvé."""
    pass


class CorruptedDataError(ReplayError):
    """Données corrompues."""
    pass


# Mapping des codes d'erreur vers les classes
ERROR_CODE_MAPPING = {
    "CONFIG_001": ConfigurationError,
    "PERCEPTION_001": ScreenCaptureError,
    "PERCEPTION_002": OCRError,
    "PERCEPTION_003": AccessibilityError,
    "SKILL_001": AppNotFoundError,
    "SKILL_002": ElementNotFoundError,
    "SKILL_003": ActionFailedError,
    "SKILL_004": TimeoutError,
    "NLU_001": IntentParsingError,
    "NLU_002": SlotExtractionError,
    "PLANNER_001": PlanGenerationError,
    "PLANNER_002": PlanValidationError,
    "SECURITY_001": PermissionDeniedError,
    "SECURITY_002": UnsafeOperationError,
    "OS_001": PlatformNotSupportedError,
    "OS_002": SystemCallError,
    "VOICE_001": AudioCaptureError,
    "VOICE_002": SpeechRecognitionError,
    "UI_001": OverlayError,
    "UI_002": HotkeyError,
    "RL_001": EnvironmentError,
    "RL_002": PolicyError,
    "RL_003": TrainingError,
    "DB_001": DatabaseError,
    "REPLAY_001": EpisodeNotFoundError,
    "REPLAY_002": CorruptedDataError,
}


def create_error_from_code(
    error_code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None
) -> DesktopAgentError:
    """
    Crée une exception à partir d'un code d'erreur.
    
    Args:
        error_code: Code d'erreur
        message: Message d'erreur
        details: Détails additionnels
        
    Returns:
        Exception appropriée
    """
    error_class = ERROR_CODE_MAPPING.get(error_code, DesktopAgentError)
    return error_class(message, error_code, details)


def is_retryable_error(error: Exception) -> bool:
    """
    Détermine si une erreur est récupérable.
    
    Args:
        error: Exception à vérifier
        
    Returns:
        True si l'erreur peut être retentée
    """
    retryable_errors = (
        ScreenCaptureError,
        OCRError,
        TimeoutError,
        SystemCallError,
        AudioCaptureError,
        DatabaseError,
    )
    
    return isinstance(error, retryable_errors)


def get_error_severity(error: Exception) -> str:
    """
    Détermine la sévérité d'une erreur.
    
    Args:
        error: Exception à évaluer
        
    Returns:
        Niveau de sévérité: "low", "medium", "high", "critical"
    """
    if isinstance(error, (SecurityError, PermissionDeniedError)):
        return "critical"
    
    if isinstance(error, (ConfigurationError, PlatformNotSupportedError)):
        return "high"
    
    if isinstance(error, (SkillError, NLUError, PlannerError)):
        return "medium"
    
    return "low"