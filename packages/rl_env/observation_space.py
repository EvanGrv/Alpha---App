"""Espace d'observation pour l'environnement RL."""

import numpy as np
from typing import Dict, Any, Tuple
from gymnasium import spaces
from pydantic import BaseModel

from packages.common.models import Observation


class ObservationConfig(BaseModel):
    """Configuration de l'espace d'observation."""
    screen_width: int = 1920
    screen_height: int = 1080
    max_ui_elements: int = 50
    max_text_length: int = 1000
    include_screenshot: bool = True
    screenshot_scale: float = 0.25  # Réduire la taille pour l'efficacité


class ObservationSpace:
    """Gestionnaire de l'espace d'observation pour RL."""
    
    def __init__(self, config: ObservationConfig = None):
        self.config = config or ObservationConfig()
        self.space = self._create_observation_space()
    
    def _create_observation_space(self) -> spaces.Dict:
        """Crée l'espace d'observation Gymnasium."""
        
        # Dimensions de l'écran réduit
        screen_h = int(self.config.screen_height * self.config.screenshot_scale)
        screen_w = int(self.config.screen_width * self.config.screenshot_scale)
        
        observation_space = {
            # Screenshot (RGB, réduit)
            'screenshot': spaces.Box(
                low=0, high=255, 
                shape=(screen_h, screen_w, 3), 
                dtype=np.uint8
            ) if self.config.include_screenshot else spaces.Box(low=0, high=1, shape=(1,)),
            
            # Éléments UI détectés (positions normalisées)
            'ui_elements': spaces.Box(
                low=0.0, high=1.0,
                shape=(self.config.max_ui_elements, 6),  # x, y, w, h, type_id, confidence
                dtype=np.float32
            ),
            
            # Texte OCR détecté
            'ocr_text': spaces.Box(
                low=0, high=255,
                shape=(self.config.max_text_length,),
                dtype=np.uint8  # Encodage des caractères
            ),
            
            # Position de la souris (normalisée)
            'mouse_position': spaces.Box(
                low=0.0, high=1.0,
                shape=(2,),
                dtype=np.float32
            ),
            
            # Fenêtre active
            'active_window': spaces.Box(
                low=0, high=255,
                shape=(100,),  # Nom de l'application encodé
                dtype=np.uint8
            ),
            
            # Métadonnées temporelles
            'step_count': spaces.Box(
                low=0, high=np.inf,
                shape=(1,),
                dtype=np.int32
            ),
            
            # État de l'action précédente
            'last_action_success': spaces.Box(
                low=0, high=1,
                shape=(1,),
                dtype=np.int32
            )
        }
        
        return spaces.Dict(observation_space)
    
    def convert_observation(self, obs: Observation) -> Dict[str, np.ndarray]:
        """Convertit une observation du domaine en observation RL."""
        
        # Screenshot
        screenshot = self._process_screenshot(obs.screenshot_path) if obs.screenshot_path else np.zeros((1,))
        
        # UI Elements
        ui_elements = self._process_ui_elements(obs.ui_elements)
        
        # OCR Text
        ocr_text = self._process_ocr_text(obs.ocr_results)
        
        # Mouse position (normalisée)
        mouse_pos = np.array([
            obs.mouse_position[0] / self.config.screen_width,
            obs.mouse_position[1] / self.config.screen_height
        ], dtype=np.float32)
        
        # Active window
        active_window = self._encode_text(obs.active_window or "", 100)
        
        return {
            'screenshot': screenshot,
            'ui_elements': ui_elements,
            'ocr_text': ocr_text,
            'mouse_position': mouse_pos,
            'active_window': active_window,
            'step_count': np.array([obs.step_count], dtype=np.int32),
            'last_action_success': np.array([1 if obs.last_action_success else 0], dtype=np.int32)
        }
    
    def _process_screenshot(self, screenshot_path: str) -> np.ndarray:
        """Traite le screenshot pour l'observation."""
        try:
            from PIL import Image
            import numpy as np
            
            # Charger et redimensionner l'image
            img = Image.open(screenshot_path).convert('RGB')
            
            if self.config.include_screenshot:
                # Redimensionner
                new_size = (
                    int(self.config.screen_width * self.config.screenshot_scale),
                    int(self.config.screen_height * self.config.screenshot_scale)
                )
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                
                return np.array(img, dtype=np.uint8)
            else:
                return np.zeros((1,), dtype=np.uint8)
                
        except Exception:
            # Retourner une image vide en cas d'erreur
            if self.config.include_screenshot:
                screen_h = int(self.config.screen_height * self.config.screenshot_scale)
                screen_w = int(self.config.screen_width * self.config.screenshot_scale)
                return np.zeros((screen_h, screen_w, 3), dtype=np.uint8)
            else:
                return np.zeros((1,), dtype=np.uint8)
    
    def _process_ui_elements(self, ui_elements: list) -> np.ndarray:
        """Traite les éléments UI pour l'observation."""
        result = np.zeros((self.config.max_ui_elements, 6), dtype=np.float32)
        
        for i, element in enumerate(ui_elements[:self.config.max_ui_elements]):
            # Normaliser les coordonnées
            x = element.bounds[0] / self.config.screen_width
            y = element.bounds[1] / self.config.screen_height
            w = element.bounds[2] / self.config.screen_width
            h = element.bounds[3] / self.config.screen_height
            
            # Type d'élément (simplifié)
            type_id = self._get_element_type_id(element.role)
            
            # Confiance (si disponible)
            confidence = getattr(element, 'confidence', 1.0)
            
            result[i] = [x, y, w, h, type_id, confidence]
        
        return result
    
    def _process_ocr_text(self, ocr_results: list) -> np.ndarray:
        """Traite le texte OCR pour l'observation."""
        # Combiner tout le texte OCR
        all_text = " ".join([result.text for result in ocr_results])
        
        return self._encode_text(all_text, self.config.max_text_length)
    
    def _encode_text(self, text: str, max_length: int) -> np.ndarray:
        """Encode le texte en array numpy."""
        # Encodage simple : ASCII avec troncature/padding
        encoded = np.zeros(max_length, dtype=np.uint8)
        
        text_bytes = text.encode('ascii', errors='ignore')[:max_length]
        encoded[:len(text_bytes)] = list(text_bytes)
        
        return encoded
    
    def _get_element_type_id(self, role: str) -> float:
        """Convertit le rôle d'élément en ID numérique."""
        role_map = {
            'button': 1.0,
            'text': 2.0,
            'textbox': 3.0,
            'link': 4.0,
            'menu': 5.0,
            'window': 6.0,
            'dialog': 7.0,
            'list': 8.0,
            'image': 9.0,
            'unknown': 0.0
        }
        
        return role_map.get(role.lower(), 0.0)