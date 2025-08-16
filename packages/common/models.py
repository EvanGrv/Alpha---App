"""
Modèles de données Pydantic pour Desktop Agent.

Définit les structures de données principales utilisées dans tout le système.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, validator


class Platform(str, Enum):
    """Plateformes supportées."""
    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"


class UiElementRole(str, Enum):
    """Rôles des éléments UI pour l'accessibilité."""
    BUTTON = "button"
    TEXT = "text"
    TEXTBOX = "textbox"
    WINDOW = "window"
    MENUITEM = "menuitem"
    LINK = "link"
    IMAGE = "image"
    LIST = "list"
    LISTITEM = "listitem"
    UNKNOWN = "unknown"


class BoundingBox(BaseModel):
    """Rectangle de délimitation pour les éléments UI."""
    x: int = Field(..., description="Position X (gauche)")
    y: int = Field(..., description="Position Y (haut)")
    width: int = Field(..., ge=0, description="Largeur")
    height: int = Field(..., ge=0, description="Hauteur")
    
    @property
    def center(self) -> tuple[int, int]:
        """Centre du rectangle."""
        return (self.x + self.width // 2, self.y + self.height // 2)
    
    @property
    def right(self) -> int:
        """Position X droite."""
        return self.x + self.width
    
    @property
    def bottom(self) -> int:
        """Position Y bas."""
        return self.y + self.height


class UiObject(BaseModel):
    """Représentation d'un élément UI détecté."""
    id: str = Field(default_factory=lambda: str(uuid4()), description="Identifiant unique")
    name: str = Field(..., description="Nom/titre de l'élément")
    role: UiElementRole = Field(..., description="Rôle de l'élément")
    bounds: BoundingBox = Field(..., description="Position et taille")
    text: Optional[str] = Field(None, description="Texte contenu")
    value: Optional[str] = Field(None, description="Valeur actuelle")
    enabled: bool = Field(True, description="Élément activé")
    visible: bool = Field(True, description="Élément visible")
    focused: bool = Field(False, description="Élément en focus")
    parent_id: Optional[str] = Field(None, description="ID du parent")
    children_ids: List[str] = Field(default_factory=list, description="IDs des enfants")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Propriétés additionnelles")


class ScreenCapture(BaseModel):
    """Capture d'écran avec métadonnées."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=datetime.now)
    width: int = Field(..., ge=1)
    height: int = Field(..., ge=1)
    monitor_id: int = Field(0, description="ID du moniteur")
    file_path: Optional[str] = Field(None, description="Chemin du fichier image")
    hash: Optional[str] = Field(None, description="Hash de l'image pour déduplication")


class TextMatch(BaseModel):
    """Correspondance de texte trouvée via OCR."""
    text: str = Field(..., description="Texte trouvé")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confiance OCR")
    bounds: BoundingBox = Field(..., description="Position du texte")


class Observation(BaseModel):
    """Observation de l'état actuel du bureau."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=datetime.now)
    screenshot: ScreenCapture = Field(..., description="Capture d'écran")
    ui_elements: List[UiObject] = Field(default_factory=list, description="Éléments UI détectés")
    text_matches: List[TextMatch] = Field(default_factory=list, description="Texte OCR trouvé")
    active_window: Optional[UiObject] = Field(None, description="Fenêtre active")
    mouse_position: tuple[int, int] = Field((0, 0), description="Position de la souris")
    platform: Platform = Field(..., description="Plateforme OS")


class IntentType(str, Enum):
    """Types d'intentions reconnues."""
    OPEN_APP = "open_app"
    FOCUS_APP = "focus_app"
    CLICK_TEXT = "click_text"
    TYPE_TEXT = "type_text"
    SAVE_FILE = "save_file"
    WEB_SEARCH = "web_search"
    WRITE_TEXT_FILE = "write_text_file"
    UNKNOWN = "unknown"


class Intent(BaseModel):
    """Intention extraite du langage naturel."""
    type: IntentType = Field(..., description="Type d'intention")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confiance du parsing")
    slots: Dict[str, Any] = Field(default_factory=dict, description="Paramètres extraits")
    original_text: str = Field(..., description="Texte original")
    normalized_text: Optional[str] = Field(None, description="Texte normalisé")


class ActionType(str, Enum):
    """Types d'actions primitives."""
    MOVE_MOUSE = "move_mouse"
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    TYPE_TEXT = "type_text"
    KEY_PRESS = "key_press"
    HOTKEY = "hotkey"
    SCROLL = "scroll"
    WAIT = "wait"
    SCREENSHOT = "screenshot"


class Action(BaseModel):
    """Action primitive à exécuter."""
    type: ActionType = Field(..., description="Type d'action")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Paramètres de l'action")
    description: str = Field(..., description="Description lisible")
    timeout: float = Field(5.0, ge=0.0, description="Timeout en secondes")


class StepStatus(str, Enum):
    """Statut d'exécution d'une étape."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class StepResult(BaseModel):
    """Résultat d'exécution d'une étape."""
    step_id: str = Field(..., description="ID de l'étape")
    status: StepStatus = Field(..., description="Statut d'exécution")
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = Field(None)
    error_message: Optional[str] = Field(None, description="Message d'erreur si échec")
    output: Optional[Any] = Field(None, description="Sortie de l'étape")
    screenshot_before: Optional[str] = Field(None, description="Capture avant exécution")
    screenshot_after: Optional[str] = Field(None, description="Capture après exécution")
    
    @property
    def duration(self) -> Optional[float]:
        """Durée d'exécution en secondes."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None


class Plan(BaseModel):
    """Plan d'exécution pour une intention."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    intent: Intent = Field(..., description="Intention d'origine")
    actions: List[Action] = Field(..., description="Séquence d'actions")
    summary: str = Field(..., description="Résumé lisible du plan")
    requires_confirmation: bool = Field(False, description="Nécessite confirmation utilisateur")
    estimated_duration: float = Field(0.0, description="Durée estimée en secondes")
    risk_level: str = Field("low", description="Niveau de risque: low/medium/high")


class ExecutionSession(BaseModel):
    """Session d'exécution d'un plan."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    plan: Plan = Field(..., description="Plan à exécuter")
    status: StepStatus = Field(StepStatus.PENDING, description="Statut global")
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = Field(None)
    step_results: List[StepResult] = Field(default_factory=list, description="Résultats des étapes")
    initial_observation: Optional[Observation] = Field(None, description="État initial")
    final_observation: Optional[Observation] = Field(None, description="État final")
    
    @property
    def duration(self) -> Optional[float]:
        """Durée totale d'exécution."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
    
    @property
    def success_rate(self) -> float:
        """Taux de succès des étapes."""
        if not self.step_results:
            return 0.0
        successful = sum(1 for r in self.step_results if r.status == StepStatus.SUCCESS)
        return successful / len(self.step_results)


class CommandSource(str, Enum):
    """Source d'une commande."""
    TEXT = "text"
    VOICE = "voice"
    API = "api"


class Command(BaseModel):
    """Commande utilisateur."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    source: CommandSource = Field(..., description="Source de la commande")
    text: str = Field(..., description="Texte de la commande")
    timestamp: datetime = Field(default_factory=datetime.now)
    user_id: Optional[str] = Field(None, description="ID utilisateur")
    session_id: Optional[str] = Field(None, description="ID de session")
    require_confirmation: bool = Field(False, description="Nécessite confirmation")


class AgentEvent(BaseModel):
    """Événement du système agent."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=datetime.now)
    event_type: str = Field(..., description="Type d'événement")
    level: str = Field("INFO", description="Niveau: DEBUG/INFO/WARNING/ERROR")
    message: str = Field(..., description="Message de l'événement")
    data: Dict[str, Any] = Field(default_factory=dict, description="Données additionnelles")
    session_id: Optional[str] = Field(None, description="ID de session associé")


# Modèles pour l'environnement RL

class RLAction(BaseModel):
    """Action pour l'environnement RL."""
    type: str = Field(..., description="Type d'action")
    parameters: Dict[str, Any] = Field(default_factory=dict)


class RLObservation(BaseModel):
    """Observation pour l'environnement RL."""
    screenshot: List[List[List[int]]] = Field(..., description="Image RGB")
    ui_elements: List[Dict[str, Any]] = Field(default_factory=list)
    cursor_position: tuple[int, int] = Field((0, 0))
    active_window_title: str = Field("", description="Titre fenêtre active")


class RLReward(BaseModel):
    """Récompense pour l'environnement RL."""
    value: float = Field(..., description="Valeur de la récompense")
    components: Dict[str, float] = Field(default_factory=dict, description="Composantes détaillées")
    terminal: bool = Field(False, description="État terminal atteint")


class Episode(BaseModel):
    """Episode d'entraînement ou de replay."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = Field(None)
    task_description: str = Field(..., description="Description de la tâche")
    steps: List[Dict[str, Any]] = Field(default_factory=list, description="Étapes de l'épisode")
    total_reward: float = Field(0.0, description="Récompense totale")
    success: bool = Field(False, description="Épisode réussi")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Métadonnées")