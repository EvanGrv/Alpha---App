"""
Service OCR pour Desktop Agent utilisant PaddleOCR.

Fournit des capacités de reconnaissance de texte avec recherche fuzzy.
"""

import re
import time
from difflib import SequenceMatcher
from typing import List, Optional, Tuple

try:
    import cv2
    import numpy as np
    from paddleocr import PaddleOCR
    from PIL import Image
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

from ..common.config import get_settings
from ..common.errors import OCRError, PerceptionError
from ..common.logging_utils import get_perception_logger
from ..common.models import BoundingBox, TextMatch
from ..common.retry import retry

logger = get_perception_logger()


class OCRService:
    """Service OCR avec PaddleOCR et capacités de recherche."""
    
    def __init__(self):
        if not CV2_AVAILABLE:
            raise OCRError("OpenCV and PaddleOCR libraries not available")
        
        self.settings = get_settings()
        
        # Initialiser PaddleOCR
        try:
            self.ocr = PaddleOCR(
                use_angle_cls=True,
                lang=self.settings.perception.ocr_language,
                show_log=False
            )
            logger.info(f"OCR initialisé avec langue: {self.settings.perception.ocr_language}")
        except Exception as e:
            raise OCRError(f"Erreur initialisation PaddleOCR: {e}")
        
        # Cache des résultats OCR
        self._ocr_cache = {}
        
    @retry(max_attempts=3, base_delay=0.5)
    def extract_text_from_image(
        self,
        image_data: bytes,
        confidence_threshold: Optional[float] = None
    ) -> List[TextMatch]:
        """
        Extrait le texte d'une image.
        
        Args:
            image_data: Données de l'image en bytes
            confidence_threshold: Seuil de confiance minimum
            
        Returns:
            Liste des correspondances de texte trouvées
        """
        try:
            start_time = time.time()
            
            if confidence_threshold is None:
                confidence_threshold = self.settings.perception.ocr_confidence_threshold
            
            # Convertir les bytes en image OpenCV
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                raise OCRError("Impossible de décoder l'image")
            
            # Vérifier le cache
            img_hash = str(hash(image_data.hex()))
            if img_hash in self._ocr_cache:
                logger.debug(f"Résultat OCR trouvé en cache: {img_hash[:8]}")
                return self._ocr_cache[img_hash]
            
            # Exécuter OCR
            result = self.ocr.ocr(img, cls=True)
            
            # Traiter les résultats
            text_matches = []
            
            if result and result[0]:
                for line in result[0]:
                    if len(line) >= 2:
                        bbox_coords = line[0]
                        text_info = line[1]
                        
                        if len(text_info) >= 2:
                            text = text_info[0]
                            confidence = float(text_info[1])
                            
                            # Filtrer par confiance
                            if confidence >= confidence_threshold:
                                # Convertir les coordonnées en BoundingBox
                                bbox = self._coords_to_bbox(bbox_coords)
                                
                                text_match = TextMatch(
                                    text=text,
                                    confidence=confidence,
                                    bounds=bbox
                                )
                                
                                text_matches.append(text_match)
            
            # Mettre en cache
            self._ocr_cache[img_hash] = text_matches
            
            # Limiter la taille du cache
            if len(self._ocr_cache) > 50:
                oldest_key = next(iter(self._ocr_cache))
                del self._ocr_cache[oldest_key]
            
            duration = time.time() - start_time
            logger.debug(
                f"OCR terminé en {duration:.3f}s, {len(text_matches)} textes trouvés",
                duration=duration,
                matches_count=len(text_matches)
            )
            
            return text_matches
            
        except Exception as e:
            logger.error(f"Erreur OCR: {e}")
            if isinstance(e, OCRError):
                raise
            raise OCRError(f"Échec extraction texte: {e}")
    
    def extract_text_from_file(
        self,
        file_path: str,
        confidence_threshold: Optional[float] = None
    ) -> List[TextMatch]:
        """
        Extrait le texte d'un fichier image.
        
        Args:
            file_path: Chemin vers le fichier image
            confidence_threshold: Seuil de confiance minimum
            
        Returns:
            Liste des correspondances de texte
        """
        try:
            with open(file_path, 'rb') as f:
                image_data = f.read()
            
            return self.extract_text_from_image(image_data, confidence_threshold)
            
        except FileNotFoundError:
            raise OCRError(f"Fichier non trouvé: {file_path}")
        except Exception as e:
            raise OCRError(f"Erreur lecture fichier {file_path}: {e}")
    
    def find_text_bounds(
        self,
        query: str,
        text_matches: List[TextMatch],
        fuzzy: bool = True,
        similarity_threshold: float = 0.6
    ) -> List[TextMatch]:
        """
        Trouve les occurrences d'un texte dans les résultats OCR.
        
        Args:
            query: Texte à rechercher
            text_matches: Résultats OCR où chercher
            fuzzy: Utiliser la recherche approximative
            similarity_threshold: Seuil de similarité pour fuzzy search
            
        Returns:
            Liste des correspondances trouvées
        """
        if not query.strip():
            return []
        
        matches = []
        query_lower = query.lower().strip()
        
        for text_match in text_matches:
            text_lower = text_match.text.lower().strip()
            
            # Recherche exacte d'abord
            if query_lower in text_lower:
                matches.append(text_match)
                continue
            
            # Recherche fuzzy si activée
            if fuzzy:
                similarity = SequenceMatcher(None, query_lower, text_lower).ratio()
                if similarity >= similarity_threshold:
                    # Créer une nouvelle correspondance avec confiance ajustée
                    fuzzy_match = TextMatch(
                        text=text_match.text,
                        confidence=text_match.confidence * similarity,
                        bounds=text_match.bounds
                    )
                    matches.append(fuzzy_match)
        
        # Trier par confiance décroissante
        matches.sort(key=lambda x: x.confidence, reverse=True)
        
        logger.debug(
            f"Recherche '{query}': {len(matches)} correspondances",
            query=query,
            matches_count=len(matches),
            fuzzy=fuzzy
        )
        
        return matches
    
    def find_text_by_pattern(
        self,
        pattern: str,
        text_matches: List[TextMatch],
        case_sensitive: bool = False
    ) -> List[TextMatch]:
        """
        Trouve le texte correspondant à un pattern regex.
        
        Args:
            pattern: Pattern regex
            text_matches: Résultats OCR où chercher
            case_sensitive: Recherche sensible à la casse
            
        Returns:
            Liste des correspondances
        """
        try:
            flags = 0 if case_sensitive else re.IGNORECASE
            regex = re.compile(pattern, flags)
            
            matches = []
            
            for text_match in text_matches:
                if regex.search(text_match.text):
                    matches.append(text_match)
            
            logger.debug(
                f"Pattern '{pattern}': {len(matches)} correspondances",
                pattern=pattern,
                matches_count=len(matches)
            )
            
            return matches
            
        except re.error as e:
            raise OCRError(f"Pattern regex invalide '{pattern}': {e}")
    
    def get_text_at_position(
        self,
        x: int,
        y: int,
        text_matches: List[TextMatch],
        tolerance: int = 5
    ) -> Optional[TextMatch]:
        """
        Trouve le texte à une position donnée.
        
        Args:
            x: Position X
            y: Position Y
            text_matches: Résultats OCR
            tolerance: Tolérance en pixels
            
        Returns:
            Correspondance trouvée ou None
        """
        for text_match in text_matches:
            bounds = text_match.bounds
            
            # Vérifier si le point est dans la boîte avec tolérance
            if (
                bounds.x - tolerance <= x <= bounds.x + bounds.width + tolerance and
                bounds.y - tolerance <= y <= bounds.y + bounds.height + tolerance
            ):
                return text_match
        
        return None
    
    def filter_by_font_size(
        self,
        text_matches: List[TextMatch],
        min_height: Optional[int] = None,
        max_height: Optional[int] = None
    ) -> List[TextMatch]:
        """
        Filtre les correspondances par taille de police (hauteur de boîte).
        
        Args:
            text_matches: Correspondances à filtrer
            min_height: Hauteur minimum
            max_height: Hauteur maximum
            
        Returns:
            Correspondances filtrées
        """
        filtered = []
        
        for text_match in text_matches:
            height = text_match.bounds.height
            
            if min_height is not None and height < min_height:
                continue
            
            if max_height is not None and height > max_height:
                continue
            
            filtered.append(text_match)
        
        return filtered
    
    def get_reading_order(self, text_matches: List[TextMatch]) -> List[TextMatch]:
        """
        Trie les correspondances dans l'ordre de lecture (haut->bas, gauche->droite).
        
        Args:
            text_matches: Correspondances à trier
            
        Returns:
            Correspondances triées
        """
        # Trier par position Y d'abord, puis par position X
        return sorted(
            text_matches,
            key=lambda match: (match.bounds.y, match.bounds.x)
        )
    
    def extract_numbers(self, text_matches: List[TextMatch]) -> List[Tuple[float, TextMatch]]:
        """
        Extrait les nombres des correspondances de texte.
        
        Args:
            text_matches: Correspondances à analyser
            
        Returns:
            Liste de tuples (nombre, correspondance)
        """
        numbers = []
        number_pattern = r'-?\d+(?:\.\d+)?'
        
        for text_match in text_matches:
            matches = re.findall(number_pattern, text_match.text)
            for match in matches:
                try:
                    number = float(match)
                    numbers.append((number, text_match))
                except ValueError:
                    continue
        
        return numbers
    
    def preprocess_image(self, img: np.ndarray) -> np.ndarray:
        """
        Préprocesse une image pour améliorer l'OCR.
        
        Args:
            img: Image OpenCV
            
        Returns:
            Image préprocessée
        """
        # Convertir en niveaux de gris
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img.copy()
        
        # Améliorer le contraste
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        # Débruitage
        denoised = cv2.medianBlur(enhanced, 3)
        
        # Binarisation adaptative
        binary = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        
        return binary
    
    def clear_cache(self) -> None:
        """Vide le cache OCR."""
        self._ocr_cache.clear()
        logger.info("Cache OCR vidé")
    
    def get_cache_stats(self) -> dict:
        """Retourne les statistiques du cache."""
        return {
            "size": len(self._ocr_cache),
            "max_size": 50
        }
    
    # Méthodes privées
    
    def _coords_to_bbox(self, coords: List[List[float]]) -> BoundingBox:
        """Convertit les coordonnées PaddleOCR en BoundingBox."""
        # coords est une liste de 4 points [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
        x_coords = [point[0] for point in coords]
        y_coords = [point[1] for point in coords]
        
        x_min = int(min(x_coords))
        y_min = int(min(y_coords))
        x_max = int(max(x_coords))
        y_max = int(max(y_coords))
        
        return BoundingBox(
            x=x_min,
            y=y_min,
            width=x_max - x_min,
            height=y_max - y_min
        )