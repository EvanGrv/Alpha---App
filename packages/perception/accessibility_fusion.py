"""
Service de fusion d'accessibilité pour Desktop Agent.

Combine les informations d'accessibilité OS avec les données OCR pour une vision unifiée.
"""

import time
from typing import Dict, List, Optional, Set, Tuple

from ..common.config import get_settings
from ..common.errors import AccessibilityError, PerceptionError
from ..common.logging_utils import get_perception_logger
from ..common.models import BoundingBox, TextMatch, UiObject, UiElementRole
from ..os_adapters import get_os_adapter

logger = get_perception_logger()


class AccessibilityFusion:
    """Fusion des données d'accessibilité et OCR pour une perception unifiée."""
    
    def __init__(self):
        self.settings = get_settings()
        self.os_adapter = get_os_adapter()
        
        # Cache des éléments UI
        self._ui_cache = {}
        self._cache_timeout = 5.0  # 5 secondes
        
        logger.info("Service de fusion d'accessibilité initialisé")
    
    def get_unified_ui_elements(
        self,
        window_id: Optional[str] = None,
        include_ocr: bool = True,
        ocr_text_matches: Optional[List[TextMatch]] = None
    ) -> List[UiObject]:
        """
        Retourne une vue unifiée des éléments UI combinant accessibilité et OCR.
        
        Args:
            window_id: ID de la fenêtre (None pour fenêtre active)
            include_ocr: Inclure les éléments détectés par OCR
            ocr_text_matches: Résultats OCR existants (sinon récupérés)
            
        Returns:
            Liste unifiée des éléments UI
        """
        try:
            start_time = time.time()
            
            # Récupérer les éléments d'accessibilité
            accessibility_elements = self._get_accessibility_elements(window_id)
            
            # Créer la liste unifiée
            unified_elements = accessibility_elements.copy()
            
            # Ajouter les éléments OCR si demandé
            if include_ocr and ocr_text_matches:
                ocr_elements = self._convert_ocr_to_ui_objects(ocr_text_matches)
                
                # Fusionner en évitant les doublons
                unified_elements.extend(
                    self._merge_elements(accessibility_elements, ocr_elements)
                )
            
            # Enrichir avec des informations contextuelles
            unified_elements = self._enrich_elements(unified_elements)
            
            duration = time.time() - start_time
            logger.debug(
                f"Fusion UI terminée en {duration:.3f}s, {len(unified_elements)} éléments",
                duration=duration,
                elements_count=len(unified_elements),
                accessibility_count=len(accessibility_elements)
            )
            
            return unified_elements
            
        except Exception as e:
            logger.error(f"Erreur fusion accessibilité: {e}")
            raise AccessibilityError(f"Échec fusion UI: {e}")
    
    def find_ui_element(
        self,
        query: str,
        query_type: str = "text",
        window_id: Optional[str] = None,
        fuzzy: bool = True
    ) -> Optional[UiObject]:
        """
        Trouve un élément UI par différents critères.
        
        Args:
            query: Texte/critère de recherche
            query_type: Type de recherche ("text", "name", "role", "id")
            window_id: ID de la fenêtre
            fuzzy: Recherche approximative
            
        Returns:
            Élément trouvé ou None
        """
        try:
            elements = self.get_unified_ui_elements(window_id)
            
            if query_type == "text":
                return self._find_by_text(query, elements, fuzzy)
            elif query_type == "name":
                return self._find_by_name(query, elements, fuzzy)
            elif query_type == "role":
                return self._find_by_role(query, elements)
            elif query_type == "id":
                return self._find_by_id(query, elements)
            else:
                # Recherche générale
                return (
                    self._find_by_text(query, elements, fuzzy) or
                    self._find_by_name(query, elements, fuzzy)
                )
                
        except Exception as e:
            logger.error(f"Erreur recherche élément '{query}': {e}")
            return None
    
    def get_clickable_elements(
        self,
        window_id: Optional[str] = None
    ) -> List[UiObject]:
        """
        Retourne les éléments cliquables.
        
        Args:
            window_id: ID de la fenêtre
            
        Returns:
            Liste des éléments cliquables
        """
        elements = self.get_unified_ui_elements(window_id)
        
        clickable_roles = {
            UiElementRole.BUTTON,
            UiElementRole.LINK,
            UiElementRole.MENUITEM,
            UiElementRole.LISTITEM
        }
        
        clickable = []
        for element in elements:
            if (
                element.role in clickable_roles or
                element.enabled and element.visible
            ):
                clickable.append(element)
        
        return clickable
    
    def get_text_input_elements(
        self,
        window_id: Optional[str] = None
    ) -> List[UiObject]:
        """
        Retourne les éléments de saisie de texte.
        
        Args:
            window_id: ID de la fenêtre
            
        Returns:
            Liste des éléments de saisie
        """
        elements = self.get_unified_ui_elements(window_id)
        
        input_roles = {UiElementRole.TEXTBOX}
        
        return [
            element for element in elements
            if element.role in input_roles and element.enabled
        ]
    
    def analyze_ui_layout(
        self,
        window_id: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Analyse la disposition des éléments UI.
        
        Args:
            window_id: ID de la fenêtre
            
        Returns:
            Analyse de la disposition
        """
        elements = self.get_unified_ui_elements(window_id)
        
        if not elements:
            return {"error": "Aucun élément UI trouvé"}
        
        # Calculer les statistiques de position
        x_positions = [elem.bounds.x for elem in elements]
        y_positions = [elem.bounds.y for elem in elements]
        
        # Analyser la distribution des rôles
        role_distribution = {}
        for element in elements:
            role = element.role.value
            role_distribution[role] = role_distribution.get(role, 0) + 1
        
        # Détecter les groupes d'éléments
        groups = self._detect_element_groups(elements)
        
        return {
            "total_elements": len(elements),
            "bounds": {
                "min_x": min(x_positions) if x_positions else 0,
                "max_x": max(x_positions) if x_positions else 0,
                "min_y": min(y_positions) if y_positions else 0,
                "max_y": max(y_positions) if y_positions else 0
            },
            "role_distribution": role_distribution,
            "groups": len(groups),
            "clickable_count": len(self.get_clickable_elements(window_id)),
            "input_count": len(self.get_text_input_elements(window_id))
        }
    
    def get_navigation_hints(
        self,
        current_element: Optional[UiObject] = None,
        window_id: Optional[str] = None
    ) -> Dict[str, List[UiObject]]:
        """
        Fournit des indices de navigation basés sur la position actuelle.
        
        Args:
            current_element: Élément actuellement sélectionné
            window_id: ID de la fenêtre
            
        Returns:
            Dictionnaire des éléments dans chaque direction
        """
        elements = self.get_unified_ui_elements(window_id)
        
        if not current_element:
            # Retourner les éléments les plus proches du centre
            return self._get_center_elements(elements)
        
        current_center = current_element.bounds.center
        
        # Classifier les éléments par direction relative
        directions = {
            "up": [],
            "down": [],
            "left": [],
            "right": []
        }
        
        for element in elements:
            if element.id == current_element.id:
                continue
            
            element_center = element.bounds.center
            dx = element_center[0] - current_center[0]
            dy = element_center[1] - current_center[1]
            
            # Déterminer la direction principale
            if abs(dx) > abs(dy):
                if dx > 0:
                    directions["right"].append(element)
                else:
                    directions["left"].append(element)
            else:
                if dy > 0:
                    directions["down"].append(element)
                else:
                    directions["up"].append(element)
        
        # Trier par distance dans chaque direction
        for direction, elems in directions.items():
            elems.sort(
                key=lambda e: self._calculate_distance(current_center, e.bounds.center)
            )
        
        return directions
    
    def clear_cache(self) -> None:
        """Vide le cache des éléments UI."""
        self._ui_cache.clear()
        logger.info("Cache accessibilité vidé")
    
    # Méthodes privées
    
    def _get_accessibility_elements(self, window_id: Optional[str]) -> List[UiObject]:
        """Récupère les éléments d'accessibilité avec cache."""
        cache_key = f"accessibility_{window_id or 'active'}"
        current_time = time.time()
        
        # Vérifier le cache
        if cache_key in self._ui_cache:
            cached_time, cached_elements = self._ui_cache[cache_key]
            if current_time - cached_time < self._cache_timeout:
                return cached_elements
        
        # Récupérer les éléments frais
        try:
            elements = self.os_adapter.get_ui_elements(window_id, recursive=True)
            
            # Filtrer les éléments valides
            valid_elements = [
                elem for elem in elements
                if elem.bounds.width > 0 and elem.bounds.height > 0
            ]
            
            # Mettre en cache
            self._ui_cache[cache_key] = (current_time, valid_elements)
            
            return valid_elements
            
        except Exception as e:
            logger.warning(f"Erreur récupération éléments accessibilité: {e}")
            return []
    
    def _convert_ocr_to_ui_objects(self, text_matches: List[TextMatch]) -> List[UiObject]:
        """Convertit les résultats OCR en objets UI."""
        ui_objects = []
        
        for i, match in enumerate(text_matches):
            ui_obj = UiObject(
                id=f"ocr_text_{i}",
                name=match.text,
                role=UiElementRole.TEXT,
                bounds=match.bounds,
                text=match.text,
                visible=True,
                enabled=False,  # Le texte OCR n'est généralement pas interactif
                properties={
                    "ocr_confidence": match.confidence,
                    "source": "ocr"
                }
            )
            ui_objects.append(ui_obj)
        
        return ui_objects
    
    def _merge_elements(
        self,
        accessibility_elements: List[UiObject],
        ocr_elements: List[UiObject]
    ) -> List[UiObject]:
        """Fusionne les éléments en évitant les doublons."""
        merged = []
        
        for ocr_elem in ocr_elements:
            # Vérifier si un élément d'accessibilité couvre la même zone
            is_duplicate = False
            
            for acc_elem in accessibility_elements:
                if self._elements_overlap(ocr_elem, acc_elem):
                    # Enrichir l'élément d'accessibilité avec le texte OCR
                    if not acc_elem.text and ocr_elem.text:
                        acc_elem.text = ocr_elem.text
                        acc_elem.properties["ocr_text"] = ocr_elem.text
                        acc_elem.properties["ocr_confidence"] = ocr_elem.properties.get("ocr_confidence", 0)
                    is_duplicate = True
                    break
            
            # Ajouter seulement si pas de doublon
            if not is_duplicate:
                merged.append(ocr_elem)
        
        return merged
    
    def _elements_overlap(self, elem1: UiObject, elem2: UiObject, threshold: float = 0.5) -> bool:
        """Vérifie si deux éléments se chevauchent significativement."""
        bounds1 = elem1.bounds
        bounds2 = elem2.bounds
        
        # Calculer l'intersection
        x_overlap = max(0, min(bounds1.right, bounds2.right) - max(bounds1.x, bounds2.x))
        y_overlap = max(0, min(bounds1.bottom, bounds2.bottom) - max(bounds1.y, bounds2.y))
        
        if x_overlap == 0 or y_overlap == 0:
            return False
        
        intersection_area = x_overlap * y_overlap
        area1 = bounds1.width * bounds1.height
        area2 = bounds2.width * bounds2.height
        
        # Calculer le ratio de chevauchement
        overlap_ratio1 = intersection_area / area1 if area1 > 0 else 0
        overlap_ratio2 = intersection_area / area2 if area2 > 0 else 0
        
        return max(overlap_ratio1, overlap_ratio2) >= threshold
    
    def _enrich_elements(self, elements: List[UiObject]) -> List[UiObject]:
        """Enrichit les éléments avec des informations contextuelles."""
        for element in elements:
            # Ajouter des informations de position relative
            element.properties["center_x"] = element.bounds.center[0]
            element.properties["center_y"] = element.bounds.center[1]
            element.properties["area"] = element.bounds.width * element.bounds.height
            
            # Classifier par taille
            area = element.properties["area"]
            if area < 100:
                element.properties["size_class"] = "small"
            elif area < 10000:
                element.properties["size_class"] = "medium"
            else:
                element.properties["size_class"] = "large"
        
        return elements
    
    def _find_by_text(self, query: str, elements: List[UiObject], fuzzy: bool) -> Optional[UiObject]:
        """Recherche par contenu textuel."""
        query_lower = query.lower()
        
        # Recherche exacte d'abord
        for element in elements:
            if element.text and query_lower in element.text.lower():
                return element
        
        # Recherche fuzzy si activée
        if fuzzy:
            from difflib import SequenceMatcher
            best_match = None
            best_ratio = 0.6
            
            for element in elements:
                if element.text:
                    ratio = SequenceMatcher(None, query_lower, element.text.lower()).ratio()
                    if ratio > best_ratio:
                        best_match = element
                        best_ratio = ratio
            
            return best_match
        
        return None
    
    def _find_by_name(self, query: str, elements: List[UiObject], fuzzy: bool) -> Optional[UiObject]:
        """Recherche par nom d'élément."""
        query_lower = query.lower()
        
        # Recherche exacte
        for element in elements:
            if query_lower in element.name.lower():
                return element
        
        # Recherche fuzzy
        if fuzzy:
            from difflib import SequenceMatcher
            best_match = None
            best_ratio = 0.6
            
            for element in elements:
                ratio = SequenceMatcher(None, query_lower, element.name.lower()).ratio()
                if ratio > best_ratio:
                    best_match = element
                    best_ratio = ratio
            
            return best_match
        
        return None
    
    def _find_by_role(self, role: str, elements: List[UiObject]) -> Optional[UiObject]:
        """Recherche par rôle d'élément."""
        for element in elements:
            if element.role.value == role:
                return element
        return None
    
    def _find_by_id(self, element_id: str, elements: List[UiObject]) -> Optional[UiObject]:
        """Recherche par ID d'élément."""
        for element in elements:
            if element.id == element_id:
                return element
        return None
    
    def _detect_element_groups(self, elements: List[UiObject]) -> List[List[UiObject]]:
        """Détecte les groupes d'éléments basés sur la proximité."""
        if not elements:
            return []
        
        groups = []
        processed = set()
        
        for element in elements:
            if element.id in processed:
                continue
            
            # Créer un nouveau groupe avec cet élément
            group = [element]
            processed.add(element.id)
            
            # Trouver les éléments proches
            for other in elements:
                if other.id in processed:
                    continue
                
                if self._are_elements_close(element, other):
                    group.append(other)
                    processed.add(other.id)
            
            if len(group) > 1:
                groups.append(group)
        
        return groups
    
    def _are_elements_close(self, elem1: UiObject, elem2: UiObject, threshold: int = 50) -> bool:
        """Vérifie si deux éléments sont proches."""
        distance = self._calculate_distance(elem1.bounds.center, elem2.bounds.center)
        return distance <= threshold
    
    def _calculate_distance(self, point1: Tuple[int, int], point2: Tuple[int, int]) -> float:
        """Calcule la distance euclidienne entre deux points."""
        dx = point1[0] - point2[0]
        dy = point1[1] - point2[1]
        return (dx * dx + dy * dy) ** 0.5
    
    def _get_center_elements(self, elements: List[UiObject]) -> Dict[str, List[UiObject]]:
        """Retourne les éléments les plus proches du centre de l'écran."""
        if not elements:
            return {"center": []}
        
        # Estimer le centre de l'écran
        x_coords = [elem.bounds.center[0] for elem in elements]
        y_coords = [elem.bounds.center[1] for elem in elements]
        
        center_x = sum(x_coords) / len(x_coords)
        center_y = sum(y_coords) / len(y_coords)
        
        # Trier par distance au centre
        center_elements = sorted(
            elements,
            key=lambda e: self._calculate_distance((center_x, center_y), e.bounds.center)
        )
        
        return {"center": center_elements[:10]}  # Top 10 éléments centraux