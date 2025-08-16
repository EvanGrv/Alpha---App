"""
Service de capture d'écran multi-moniteur pour Desktop Agent.

Utilise mss pour des captures rapides et efficaces.
"""

import hashlib
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

try:
    import mss
    import numpy as np
    from PIL import Image
    MSS_AVAILABLE = True
except ImportError:
    MSS_AVAILABLE = False

from ..common.config import get_settings
from ..common.errors import PerceptionError, ScreenCaptureError
from ..common.logging_utils import get_perception_logger
from ..common.models import BoundingBox, ScreenCapture
from ..common.retry import retry

logger = get_perception_logger()


class ScreenCaptureService:
    """Service de capture d'écran avec support multi-moniteur."""
    
    def __init__(self):
        if not MSS_AVAILABLE:
            raise ScreenCaptureError("mss library not available")
        
        self.settings = get_settings()
        self._sct = mss.mss()
        self._capture_cache = {}
        
        # Informations des moniteurs
        self.monitors = self._sct.monitors[1:]  # Exclure le moniteur "All"
        self.primary_monitor = self.monitors[0] if self.monitors else None
        
        logger.info(
            f"Service de capture initialisé avec {len(self.monitors)} moniteur(s)",
            monitors_count=len(self.monitors)
        )
    
    def get_monitors_info(self) -> List[dict]:
        """
        Retourne les informations des moniteurs.
        
        Returns:
            Liste des informations de moniteurs
        """
        monitors_info = []
        
        for i, monitor in enumerate(self.monitors):
            monitors_info.append({
                "id": i,
                "x": monitor["left"],
                "y": monitor["top"], 
                "width": monitor["width"],
                "height": monitor["height"],
                "is_primary": i == 0
            })
        
        return monitors_info
    
    @retry(max_attempts=3, base_delay=0.1)
    def capture_screen(
        self,
        monitor_id: int = 0,
        region: Optional[BoundingBox] = None,
        save_path: Optional[str] = None
    ) -> ScreenCapture:
        """
        Capture l'écran ou une région spécifique.
        
        Args:
            monitor_id: ID du moniteur à capturer
            region: Région spécifique à capturer
            save_path: Chemin pour sauvegarder l'image
            
        Returns:
            Métadonnées de la capture
        """
        try:
            start_time = time.time()
            
            # Valider le moniteur
            if monitor_id >= len(self.monitors):
                raise ScreenCaptureError(f"Moniteur {monitor_id} non disponible")
            
            monitor = self.monitors[monitor_id]
            
            # Définir la région de capture
            if region:
                capture_region = {
                    "left": monitor["left"] + region.x,
                    "top": monitor["top"] + region.y,
                    "width": region.width,
                    "height": region.height
                }
            else:
                capture_region = monitor
            
            # Effectuer la capture
            screenshot = self._sct.grab(capture_region)
            
            # Convertir en PIL Image
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            
            # Calculer le hash pour déduplication
            img_hash = self._calculate_image_hash(img)
            
            # Vérifier le cache si activé
            if self.settings.perception.cache_screenshots:
                if img_hash in self._capture_cache:
                    cached_capture = self._capture_cache[img_hash]
                    logger.debug(f"Capture trouvée en cache: {img_hash[:8]}")
                    return cached_capture
            
            # Sauvegarder si demandé
            if save_path:
                save_path_obj = Path(save_path)
                save_path_obj.parent.mkdir(parents=True, exist_ok=True)
                img.save(save_path, format=self.settings.perception.screenshot_compression.upper())
            
            # Créer l'objet ScreenCapture
            capture = ScreenCapture(
                timestamp=datetime.now(),
                width=capture_region["width"],
                height=capture_region["height"],
                monitor_id=monitor_id,
                file_path=save_path,
                hash=img_hash
            )
            
            # Mettre en cache si activé
            if self.settings.perception.cache_screenshots:
                self._capture_cache[img_hash] = capture
                
                # Limiter la taille du cache
                if len(self._capture_cache) > 100:
                    oldest_key = next(iter(self._capture_cache))
                    del self._capture_cache[oldest_key]
            
            duration = time.time() - start_time
            logger.debug(
                f"Capture réussie en {duration:.3f}s",
                monitor_id=monitor_id,
                width=capture.width,
                height=capture.height,
                duration=duration
            )
            
            return capture
            
        except Exception as e:
            logger.error(f"Erreur lors de la capture d'écran: {e}")
            if isinstance(e, ScreenCaptureError):
                raise
            raise ScreenCaptureError(f"Échec de la capture: {e}")
    
    def capture_all_monitors(
        self,
        save_dir: Optional[str] = None
    ) -> List[ScreenCapture]:
        """
        Capture tous les moniteurs.
        
        Args:
            save_dir: Répertoire pour sauvegarder les images
            
        Returns:
            Liste des captures
        """
        captures = []
        
        for i in range(len(self.monitors)):
            save_path = None
            if save_dir:
                save_path = f"{save_dir}/monitor_{i}_{int(time.time())}.png"
            
            try:
                capture = self.capture_screen(monitor_id=i, save_path=save_path)
                captures.append(capture)
            except Exception as e:
                logger.warning(f"Échec capture moniteur {i}: {e}")
        
        return captures
    
    def capture_region_around_point(
        self,
        x: int,
        y: int,
        width: int = 400,
        height: int = 300,
        monitor_id: Optional[int] = None
    ) -> ScreenCapture:
        """
        Capture une région autour d'un point.
        
        Args:
            x: Position X du centre
            y: Position Y du centre
            width: Largeur de la région
            height: Hauteur de la région
            monitor_id: ID du moniteur (auto-détecté si None)
            
        Returns:
            Capture de la région
        """
        # Auto-détecter le moniteur si non spécifié
        if monitor_id is None:
            monitor_id = self._find_monitor_for_point(x, y)
        
        # Calculer la région centrée sur le point
        region = BoundingBox(
            x=max(0, x - width // 2),
            y=max(0, y - height // 2),
            width=width,
            height=height
        )
        
        return self.capture_screen(monitor_id=monitor_id, region=region)
    
    def start_continuous_capture(
        self,
        interval: float = 1.0,
        save_dir: Optional[str] = None,
        max_captures: Optional[int] = None
    ) -> List[ScreenCapture]:
        """
        Démarre une capture continue.
        
        Args:
            interval: Intervalle entre captures en secondes
            save_dir: Répertoire de sauvegarde
            max_captures: Nombre maximum de captures
            
        Returns:
            Liste des captures effectuées
        """
        captures = []
        count = 0
        
        logger.info(f"Démarrage capture continue (intervalle: {interval}s)")
        
        try:
            while True:
                if max_captures and count >= max_captures:
                    break
                
                save_path = None
                if save_dir:
                    save_path = f"{save_dir}/capture_{count:04d}_{int(time.time())}.png"
                
                capture = self.capture_screen(save_path=save_path)
                captures.append(capture)
                count += 1
                
                if count % 10 == 0:
                    logger.info(f"Captures effectuées: {count}")
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            logger.info(f"Capture continue arrêtée après {count} captures")
        
        return captures
    
    def get_screen_dimensions(self, monitor_id: int = 0) -> Tuple[int, int]:
        """
        Retourne les dimensions d'un moniteur.
        
        Args:
            monitor_id: ID du moniteur
            
        Returns:
            Tuple (largeur, hauteur)
        """
        if monitor_id >= len(self.monitors):
            raise ScreenCaptureError(f"Moniteur {monitor_id} non disponible")
        
        monitor = self.monitors[monitor_id]
        return (monitor["width"], monitor["height"])
    
    def is_point_on_screen(self, x: int, y: int, monitor_id: int = 0) -> bool:
        """
        Vérifie si un point est sur l'écran.
        
        Args:
            x: Position X
            y: Position Y
            monitor_id: ID du moniteur
            
        Returns:
            True si le point est visible
        """
        if monitor_id >= len(self.monitors):
            return False
        
        monitor = self.monitors[monitor_id]
        return (
            monitor["left"] <= x < monitor["left"] + monitor["width"] and
            monitor["top"] <= y < monitor["top"] + monitor["height"]
        )
    
    def clear_cache(self) -> None:
        """Vide le cache des captures."""
        self._capture_cache.clear()
        logger.info("Cache des captures vidé")
    
    def get_cache_stats(self) -> dict:
        """Retourne les statistiques du cache."""
        return {
            "size": len(self._capture_cache),
            "max_size": 100,
            "hit_rate": getattr(self, "_cache_hits", 0) / max(getattr(self, "_cache_requests", 1), 1)
        }
    
    # Méthodes privées
    
    def _calculate_image_hash(self, img: Image.Image) -> str:
        """Calcule un hash MD5 de l'image."""
        img_bytes = img.tobytes()
        return hashlib.md5(img_bytes).hexdigest()
    
    def _find_monitor_for_point(self, x: int, y: int) -> int:
        """Trouve le moniteur contenant un point."""
        for i, monitor in enumerate(self.monitors):
            if (
                monitor["left"] <= x < monitor["left"] + monitor["width"] and
                monitor["top"] <= y < monitor["top"] + monitor["height"]
            ):
                return i
        
        # Retourner le moniteur principal par défaut
        return 0
    
    def __del__(self):
        """Nettoyage lors de la destruction."""
        if hasattr(self, '_sct'):
            try:
                self._sct.close()
            except:
                pass