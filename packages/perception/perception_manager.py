"""
Gestionnaire principal de perception pour Desktop Agent.

Coordonne la capture d'écran, l'OCR et la fusion d'accessibilité.
"""

import asyncio
import time
from pathlib import Path
from typing import List, Optional

from ..common.config import get_settings
from ..common.errors import PerceptionError
from ..common.logging_utils import get_perception_logger
from ..common.models import Observation, ScreenCapture, TextMatch, UiObject
from ..os_adapters import get_os_adapter
from .accessibility_fusion import AccessibilityFusion
from .ocr_service import OCRService
from .screen_capture import ScreenCaptureService

logger = get_perception_logger()


class PerceptionManager:
    """Gestionnaire principal coordonnant tous les services de perception."""
    
    def __init__(self):
        self.settings = get_settings()
        self.os_adapter = get_os_adapter()
        
        # Initialiser les services
        self.screen_capture = ScreenCaptureService()
        self.ocr_service = OCRService()
        self.accessibility_fusion = AccessibilityFusion()
        
        # État interne
        self._last_observation = None
        self._continuous_capture = False
        self._capture_task = None
        
        logger.info("Gestionnaire de perception initialisé")
    
    async def get_current_observation(
        self,
        save_screenshot: bool = False,
        screenshot_path: Optional[str] = None,
        include_ocr: bool = True,
        monitor_id: int = 0
    ) -> Observation:
        """
        Capture l'état actuel du bureau.
        
        Args:
            save_screenshot: Sauvegarder la capture d'écran
            screenshot_path: Chemin de sauvegarde personnalisé
            include_ocr: Inclure l'analyse OCR
            monitor_id: ID du moniteur à capturer
            
        Returns:
            Observation complète de l'état actuel
        """
        try:
            start_time = time.time()
            
            # Générer le chemin de sauvegarde si nécessaire
            if save_screenshot and not screenshot_path:
                timestamp = int(time.time())
                screenshot_path = str(
                    self.settings.data_dir / f"screenshots/observation_{timestamp}.png"
                )
            
            # Capture d'écran
            screenshot = self.screen_capture.capture_screen(
                monitor_id=monitor_id,
                save_path=screenshot_path
            )
            
            # OCR si demandé
            text_matches = []
            if include_ocr:
                if screenshot_path:
                    text_matches = self.ocr_service.extract_text_from_file(screenshot_path)
                else:
                    # Capturer les données d'image pour OCR
                    img_data = self.screen_capture.take_screenshot()
                    text_matches = self.ocr_service.extract_text_from_image(img_data)
            
            # Éléments UI unifiés
            ui_elements = self.accessibility_fusion.get_unified_ui_elements(
                include_ocr=include_ocr,
                ocr_text_matches=text_matches
            )
            
            # Fenêtre active
            active_window = self.os_adapter.get_active_window()
            
            # Position de la souris
            mouse_position = self.os_adapter.get_mouse_position()
            
            # Créer l'observation
            observation = Observation(
                screenshot=screenshot,
                ui_elements=ui_elements,
                text_matches=text_matches,
                active_window=active_window,
                mouse_position=mouse_position,
                platform=self.os_adapter.platform
            )
            
            self._last_observation = observation
            
            duration = time.time() - start_time
            logger.info(
                f"Observation capturée en {duration:.3f}s",
                duration=duration,
                ui_elements_count=len(ui_elements),
                text_matches_count=len(text_matches),
                monitor_id=monitor_id
            )
            
            return observation
            
        except Exception as e:
            logger.error(f"Erreur capture observation: {e}")
            raise PerceptionError(f"Échec capture observation: {e}")
    
    def get_last_observation(self) -> Optional[Observation]:
        """Retourne la dernière observation capturée."""
        return self._last_observation
    
    async def find_text_on_screen(
        self,
        query: str,
        fuzzy: bool = True,
        monitor_id: int = 0,
        confidence_threshold: Optional[float] = None
    ) -> List[TextMatch]:
        """
        Recherche du texte sur l'écran actuel.
        
        Args:
            query: Texte à rechercher
            fuzzy: Recherche approximative
            monitor_id: ID du moniteur
            confidence_threshold: Seuil de confiance OCR
            
        Returns:
            Liste des correspondances trouvées
        """
        try:
            # Capturer l'écran
            img_data = self.screen_capture.take_screenshot()
            
            # Extraire le texte
            text_matches = self.ocr_service.extract_text_from_image(
                img_data, confidence_threshold
            )
            
            # Rechercher le texte demandé
            matches = self.ocr_service.find_text_bounds(
                query, text_matches, fuzzy
            )
            
            logger.info(
                f"Recherche texte '{query}': {len(matches)} correspondances",
                query=query,
                matches_count=len(matches)
            )
            
            return matches
            
        except Exception as e:
            logger.error(f"Erreur recherche texte '{query}': {e}")
            return []
    
    async def find_ui_element(
        self,
        query: str,
        query_type: str = "text",
        fuzzy: bool = True
    ) -> Optional[UiObject]:
        """
        Recherche un élément UI par différents critères.
        
        Args:
            query: Critère de recherche
            query_type: Type de recherche ("text", "name", "role")
            fuzzy: Recherche approximative
            
        Returns:
            Élément trouvé ou None
        """
        try:
            element = self.accessibility_fusion.find_ui_element(
                query, query_type, fuzzy=fuzzy
            )
            
            if element:
                logger.info(
                    f"Élément trouvé: {element.name} ({element.role.value})",
                    query=query,
                    element_name=element.name,
                    element_role=element.role.value
                )
            else:
                logger.warning(f"Aucun élément trouvé pour '{query}'")
            
            return element
            
        except Exception as e:
            logger.error(f"Erreur recherche élément '{query}': {e}")
            return None
    
    async def get_clickable_elements(self) -> List[UiObject]:
        """Retourne tous les éléments cliquables visibles."""
        try:
            elements = self.accessibility_fusion.get_clickable_elements()
            
            logger.debug(f"{len(elements)} éléments cliquables trouvés")
            
            return elements
            
        except Exception as e:
            logger.error(f"Erreur récupération éléments cliquables: {e}")
            return []
    
    async def analyze_screen_layout(self) -> dict:
        """
        Analyse la disposition actuelle de l'écran.
        
        Returns:
            Analyse détaillée de la disposition
        """
        try:
            # Analyser la disposition UI
            ui_analysis = self.accessibility_fusion.analyze_ui_layout()
            
            # Ajouter des informations sur les moniteurs
            monitors_info = self.screen_capture.get_monitors_info()
            
            # Statistiques OCR si dernière observation disponible
            ocr_stats = {}
            if self._last_observation:
                ocr_stats = {
                    "text_elements": len(self._last_observation.text_matches),
                    "avg_confidence": sum(
                        match.confidence for match in self._last_observation.text_matches
                    ) / len(self._last_observation.text_matches) if self._last_observation.text_matches else 0
                }
            
            analysis = {
                "timestamp": time.time(),
                "monitors": monitors_info,
                "ui_layout": ui_analysis,
                "ocr_stats": ocr_stats,
                "active_window": self._last_observation.active_window.name if (
                    self._last_observation and self._last_observation.active_window
                ) else None
            }
            
            logger.info("Analyse de disposition terminée")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Erreur analyse disposition: {e}")
            return {"error": str(e)}
    
    async def start_continuous_observation(
        self,
        interval: float = 1.0,
        save_screenshots: bool = False,
        include_ocr: bool = True
    ) -> None:
        """
        Démarre l'observation continue du bureau.
        
        Args:
            interval: Intervalle entre observations (secondes)
            save_screenshots: Sauvegarder les captures
            include_ocr: Inclure l'analyse OCR
        """
        if self._continuous_capture:
            logger.warning("Observation continue déjà active")
            return
        
        self._continuous_capture = True
        
        logger.info(f"Démarrage observation continue (intervalle: {interval}s)")
        
        async def capture_loop():
            count = 0
            while self._continuous_capture:
                try:
                    await self.get_current_observation(
                        save_screenshot=save_screenshots,
                        include_ocr=include_ocr
                    )
                    count += 1
                    
                    if count % 10 == 0:
                        logger.info(f"Observations continues: {count}")
                    
                    await asyncio.sleep(interval)
                    
                except Exception as e:
                    logger.error(f"Erreur observation continue: {e}")
                    await asyncio.sleep(interval)
        
        self._capture_task = asyncio.create_task(capture_loop())
    
    async def stop_continuous_observation(self) -> None:
        """Arrête l'observation continue."""
        if not self._continuous_capture:
            return
        
        self._continuous_capture = False
        
        if self._capture_task:
            self._capture_task.cancel()
            try:
                await self._capture_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Observation continue arrêtée")
    
    def get_navigation_hints(
        self,
        current_element: Optional[UiObject] = None
    ) -> dict:
        """
        Fournit des indices de navigation pour l'élément actuel.
        
        Args:
            current_element: Élément actuellement sélectionné
            
        Returns:
            Indices de navigation
        """
        return self.accessibility_fusion.get_navigation_hints(current_element)
    
    def clear_all_caches(self) -> None:
        """Vide tous les caches de perception."""
        self.screen_capture.clear_cache()
        self.ocr_service.clear_cache()
        self.accessibility_fusion.clear_cache()
        
        logger.info("Tous les caches de perception vidés")
    
    def get_performance_stats(self) -> dict:
        """Retourne les statistiques de performance."""
        return {
            "screen_capture": {
                "cache": self.screen_capture.get_cache_stats(),
                "monitors": len(self.screen_capture.monitors)
            },
            "ocr": {
                "cache": self.ocr_service.get_cache_stats(),
                "language": self.settings.perception.ocr_language
            },
            "continuous_capture": self._continuous_capture,
            "last_observation_time": (
                self._last_observation.timestamp.isoformat()
                if self._last_observation else None
            )
        }
    
    async def __aenter__(self):
        """Support du context manager async."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Nettoyage lors de la sortie du context manager."""
        if self._continuous_capture:
            await self.stop_continuous_observation()
        
        self.clear_all_caches()