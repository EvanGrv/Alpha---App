"""
Interface de base pour les adaptateurs OS.

Définit l'interface commune que tous les adaptateurs doivent implémenter.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from ..common.models import BoundingBox, Platform, UiObject


class OSAdapter(ABC):
    """Interface abstraite pour les adaptateurs OS."""
    
    @property
    @abstractmethod
    def platform(self) -> Platform:
        """Retourne la plateforme supportée."""
        pass
    
    @abstractmethod
    def is_supported(self) -> bool:
        """Vérifie si l'adaptateur est supporté sur le système actuel."""
        pass
    
    # Gestion des applications
    
    @abstractmethod
    def open_app(self, name: str, **kwargs: Any) -> bool:
        """
        Ouvre une application.
        
        Args:
            name: Nom de l'application
            **kwargs: Arguments additionnels
            
        Returns:
            True si succès
        """
        pass
    
    @abstractmethod
    def focus_app(self, name: str, **kwargs: Any) -> bool:
        """
        Met le focus sur une application.
        
        Args:
            name: Nom de l'application
            **kwargs: Arguments additionnels
            
        Returns:
            True si succès
        """
        pass
    
    @abstractmethod
    def close_app(self, name: str, **kwargs: Any) -> bool:
        """
        Ferme une application.
        
        Args:
            name: Nom de l'application
            **kwargs: Arguments additionnels
            
        Returns:
            True si succès
        """
        pass
    
    @abstractmethod
    def get_running_apps(self) -> List[Dict[str, Any]]:
        """
        Retourne la liste des applications en cours d'exécution.
        
        Returns:
            Liste des applications avec métadonnées
        """
        pass
    
    # Contrôle de la souris
    
    @abstractmethod
    def move_mouse(self, x: int, y: int) -> bool:
        """
        Déplace la souris à la position spécifiée.
        
        Args:
            x: Position X
            y: Position Y
            
        Returns:
            True si succès
        """
        pass
    
    @abstractmethod
    def click(self, x: int, y: int, button: str = "left") -> bool:
        """
        Effectue un clic à la position spécifiée.
        
        Args:
            x: Position X
            y: Position Y
            button: Bouton de la souris ("left", "right", "middle")
            
        Returns:
            True si succès
        """
        pass
    
    @abstractmethod
    def double_click(self, x: int, y: int, button: str = "left") -> bool:
        """
        Effectue un double-clic.
        
        Args:
            x: Position X
            y: Position Y
            button: Bouton de la souris
            
        Returns:
            True si succès
        """
        pass
    
    @abstractmethod
    def drag(self, start_x: int, start_y: int, end_x: int, end_y: int) -> bool:
        """
        Effectue un glisser-déposer.
        
        Args:
            start_x: Position X de départ
            start_y: Position Y de départ
            end_x: Position X d'arrivée
            end_y: Position Y d'arrivée
            
        Returns:
            True si succès
        """
        pass
    
    @abstractmethod
    def scroll(self, x: int, y: int, direction: str, amount: int = 3) -> bool:
        """
        Effectue un scroll.
        
        Args:
            x: Position X
            y: Position Y
            direction: Direction ("up", "down", "left", "right")
            amount: Quantité de scroll
            
        Returns:
            True si succès
        """
        pass
    
    @abstractmethod
    def get_mouse_position(self) -> Tuple[int, int]:
        """
        Retourne la position actuelle de la souris.
        
        Returns:
            Tuple (x, y)
        """
        pass
    
    # Contrôle du clavier
    
    @abstractmethod
    def type_text(self, text: str) -> bool:
        """
        Tape du texte.
        
        Args:
            text: Texte à taper
            
        Returns:
            True si succès
        """
        pass
    
    @abstractmethod
    def key_press(self, key: str) -> bool:
        """
        Appuie sur une touche.
        
        Args:
            key: Nom de la touche
            
        Returns:
            True si succès
        """
        pass
    
    @abstractmethod
    def key_release(self, key: str) -> bool:
        """
        Relâche une touche.
        
        Args:
            key: Nom de la touche
            
        Returns:
            True si succès
        """
        pass
    
    @abstractmethod
    def hotkey(self, *keys: str) -> bool:
        """
        Effectue une combinaison de touches.
        
        Args:
            *keys: Touches de la combinaison
            
        Returns:
            True si succès
        """
        pass
    
    # Gestion des fenêtres
    
    @abstractmethod
    def get_active_window(self) -> Optional[UiObject]:
        """
        Retourne la fenêtre active.
        
        Returns:
            Objet UI de la fenêtre active ou None
        """
        pass
    
    @abstractmethod
    def get_all_windows(self) -> List[UiObject]:
        """
        Retourne toutes les fenêtres.
        
        Returns:
            Liste des fenêtres
        """
        pass
    
    @abstractmethod
    def get_window_by_title(self, title: str, partial: bool = True) -> Optional[UiObject]:
        """
        Trouve une fenêtre par son titre.
        
        Args:
            title: Titre de la fenêtre
            partial: Correspondance partielle
            
        Returns:
            Fenêtre trouvée ou None
        """
        pass
    
    @abstractmethod
    def set_window_position(self, window_id: str, x: int, y: int) -> bool:
        """
        Définit la position d'une fenêtre.
        
        Args:
            window_id: ID de la fenêtre
            x: Position X
            y: Position Y
            
        Returns:
            True si succès
        """
        pass
    
    @abstractmethod
    def set_window_size(self, window_id: str, width: int, height: int) -> bool:
        """
        Définit la taille d'une fenêtre.
        
        Args:
            window_id: ID de la fenêtre
            width: Largeur
            height: Hauteur
            
        Returns:
            True si succès
        """
        pass
    
    @abstractmethod
    def minimize_window(self, window_id: str) -> bool:
        """
        Minimise une fenêtre.
        
        Args:
            window_id: ID de la fenêtre
            
        Returns:
            True si succès
        """
        pass
    
    @abstractmethod
    def maximize_window(self, window_id: str) -> bool:
        """
        Maximise une fenêtre.
        
        Args:
            window_id: ID de la fenêtre
            
        Returns:
            True si succès
        """
        pass
    
    # API d'accessibilité
    
    @abstractmethod
    def get_ui_elements(
        self,
        window_id: Optional[str] = None,
        recursive: bool = True
    ) -> List[UiObject]:
        """
        Retourne les éléments UI d'une fenêtre.
        
        Args:
            window_id: ID de la fenêtre (None pour fenêtre active)
            recursive: Parcours récursif
            
        Returns:
            Liste des éléments UI
        """
        pass
    
    @abstractmethod
    def find_element_by_name(
        self,
        name: str,
        window_id: Optional[str] = None,
        partial: bool = True
    ) -> Optional[UiObject]:
        """
        Trouve un élément par son nom.
        
        Args:
            name: Nom de l'élément
            window_id: ID de la fenêtre
            partial: Correspondance partielle
            
        Returns:
            Élément trouvé ou None
        """
        pass
    
    @abstractmethod
    def find_elements_by_role(
        self,
        role: str,
        window_id: Optional[str] = None
    ) -> List[UiObject]:
        """
        Trouve des éléments par leur rôle.
        
        Args:
            role: Rôle des éléments
            window_id: ID de la fenêtre
            
        Returns:
            Liste des éléments trouvés
        """
        pass
    
    @abstractmethod
    def click_element(self, element_id: str) -> bool:
        """
        Clique sur un élément UI.
        
        Args:
            element_id: ID de l'élément
            
        Returns:
            True si succès
        """
        pass
    
    @abstractmethod
    def set_element_text(self, element_id: str, text: str) -> bool:
        """
        Définit le texte d'un élément.
        
        Args:
            element_id: ID de l'élément
            text: Nouveau texte
            
        Returns:
            True si succès
        """
        pass
    
    # Gestion des fichiers
    
    @abstractmethod
    def open_file_dialog(self, dialog_type: str = "open") -> Optional[str]:
        """
        Ouvre un dialogue de fichier.
        
        Args:
            dialog_type: Type de dialogue ("open", "save")
            
        Returns:
            Chemin sélectionné ou None
        """
        pass
    
    @abstractmethod
    def get_default_app_for_file(self, file_path: str) -> Optional[str]:
        """
        Retourne l'application par défaut pour un type de fichier.
        
        Args:
            file_path: Chemin du fichier
            
        Returns:
            Nom de l'application par défaut
        """
        pass
    
    # Utilitaires
    
    @abstractmethod
    def take_screenshot(self, region: Optional[BoundingBox] = None) -> bytes:
        """
        Prend une capture d'écran.
        
        Args:
            region: Région à capturer (None pour tout l'écran)
            
        Returns:
            Données de l'image
        """
        pass
    
    @abstractmethod
    def wait_for_element(
        self,
        element_name: str,
        timeout: float = 10.0,
        window_id: Optional[str] = None
    ) -> Optional[UiObject]:
        """
        Attend qu'un élément apparaisse.
        
        Args:
            element_name: Nom de l'élément
            timeout: Timeout en secondes
            window_id: ID de la fenêtre
            
        Returns:
            Élément trouvé ou None si timeout
        """
        pass
    
    @abstractmethod
    def wait_for_window(
        self,
        window_title: str,
        timeout: float = 10.0
    ) -> Optional[UiObject]:
        """
        Attend qu'une fenêtre apparaisse.
        
        Args:
            window_title: Titre de la fenêtre
            timeout: Timeout en secondes
            
        Returns:
            Fenêtre trouvée ou None si timeout
        """
        pass