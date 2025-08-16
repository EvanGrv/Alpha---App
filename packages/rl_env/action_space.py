"""Espace d'action pour l'environnement RL."""

import numpy as np
from typing import Dict, Any, Tuple, List
from gymnasium import spaces
from pydantic import BaseModel

from packages.common.models import Action, ActionType


class ActionConfig(BaseModel):
    """Configuration de l'espace d'action."""
    screen_width: int = 1920
    screen_height: int = 1080
    max_text_length: int = 200
    max_key_combo: int = 5


class ActionSpace:
    """Gestionnaire de l'espace d'action pour RL."""
    
    def __init__(self, config: ActionConfig = None):
        self.config = config or ActionConfig()
        self.space = self._create_action_space()
        
        # Mapping des types d'actions
        self.action_types = [
            'move_mouse',
            'click',
            'double_click',
            'right_click',
            'type_text',
            'key_press',
            'scroll',
            'wait',
            'no_op'
        ]
    
    def _create_action_space(self) -> spaces.Dict:
        """Crée l'espace d'action Gymnasium."""
        
        return spaces.Dict({
            # Type d'action
            'action_type': spaces.Discrete(len(self.action_types)),
            
            # Coordonnées (normalisées 0-1)
            'coordinates': spaces.Box(
                low=0.0, high=1.0,
                shape=(2,),
                dtype=np.float32
            ),
            
            # Texte à taper (encodé)
            'text': spaces.Box(
                low=0, high=255,
                shape=(self.config.max_text_length,),
                dtype=np.uint8
            ),
            
            # Touches spéciales (ctrl, alt, shift, etc.)
            'modifiers': spaces.MultiBinary(8),  # 8 modificateurs possibles
            
            # Touche principale (pour les raccourcis)
            'key': spaces.Box(
                low=0, high=255,
                shape=(1,),
                dtype=np.uint8
            ),
            
            # Direction de scroll (-1, 0, 1)
            'scroll_direction': spaces.Discrete(3),  # up, none, down
            
            # Durée d'attente (en secondes, normalisée)
            'wait_time': spaces.Box(
                low=0.0, high=1.0,
                shape=(1,),
                dtype=np.float32
            )
        })
    
    def convert_to_domain_action(self, rl_action: Dict[str, np.ndarray]) -> Action:
        """Convertit une action RL en action du domaine."""
        
        action_type_id = int(rl_action['action_type'])
        action_type_name = self.action_types[action_type_id]
        
        # Dénormaliser les coordonnées
        coords = rl_action['coordinates']
        x = int(coords[0] * self.config.screen_width)
        y = int(coords[1] * self.config.screen_height)
        
        # Décoder le texte
        text = self._decode_text(rl_action['text'])
        
        # Traiter les modificateurs
        modifiers = self._process_modifiers(rl_action['modifiers'])
        
        # Touche principale
        key = chr(int(rl_action['key'][0])) if rl_action['key'][0] > 0 else None
        
        # Direction de scroll
        scroll_map = {0: -1, 1: 0, 2: 1}  # up, none, down
        scroll_direction = scroll_map[int(rl_action['scroll_direction'])]
        
        # Temps d'attente
        wait_time = float(rl_action['wait_time'][0]) * 5.0  # Max 5 secondes
        
        # Créer l'action selon le type
        parameters = {}
        
        if action_type_name in ['move_mouse', 'click', 'double_click', 'right_click']:
            parameters['x'] = x
            parameters['y'] = y
            
        elif action_type_name == 'type_text':
            parameters['text'] = text
            
        elif action_type_name == 'key_press':
            if key and modifiers:
                # Combinaison de touches
                combo = modifiers + [key] if key else modifiers
                parameters['keys'] = combo
            elif key:
                parameters['key'] = key
                
        elif action_type_name == 'scroll':
            parameters['x'] = x
            parameters['y'] = y
            parameters['direction'] = 'up' if scroll_direction < 0 else 'down'
            parameters['clicks'] = abs(scroll_direction) if scroll_direction != 0 else 1
            
        elif action_type_name == 'wait':
            parameters['duration'] = wait_time
        
        return Action(
            type=ActionType(action_type_name),
            parameters=parameters,
            timestamp=0  # Sera défini lors de l'exécution
        )
    
    def convert_from_domain_action(self, action: Action) -> Dict[str, np.ndarray]:
        """Convertit une action du domaine en action RL."""
        
        # Type d'action
        try:
            action_type_id = self.action_types.index(action.type.value)
        except ValueError:
            action_type_id = len(self.action_types) - 1  # no_op par défaut
        
        # Coordonnées normalisées
        x = action.parameters.get('x', 0)
        y = action.parameters.get('y', 0)
        coords = np.array([
            x / self.config.screen_width,
            y / self.config.screen_height
        ], dtype=np.float32)
        
        # Texte
        text = self._encode_text(action.parameters.get('text', ''))
        
        # Modificateurs et touche
        keys = action.parameters.get('keys', [])
        modifiers, key = self._encode_keys(keys)
        
        # Scroll
        direction = action.parameters.get('direction', 'none')
        scroll_direction = {'up': 0, 'none': 1, 'down': 2}.get(direction, 1)
        
        # Temps d'attente
        wait_time = np.array([
            min(1.0, action.parameters.get('duration', 0) / 5.0)
        ], dtype=np.float32)
        
        return {
            'action_type': action_type_id,
            'coordinates': coords,
            'text': text,
            'modifiers': modifiers,
            'key': key,
            'scroll_direction': scroll_direction,
            'wait_time': wait_time
        }
    
    def _decode_text(self, encoded_text: np.ndarray) -> str:
        """Décode le texte depuis l'array numpy."""
        # Retirer les zéros de padding
        non_zero = encoded_text[encoded_text > 0]
        
        try:
            return bytes(non_zero).decode('ascii', errors='ignore')
        except:
            return ""
    
    def _encode_text(self, text: str) -> np.ndarray:
        """Encode le texte en array numpy."""
        encoded = np.zeros(self.config.max_text_length, dtype=np.uint8)
        
        text_bytes = text.encode('ascii', errors='ignore')[:self.config.max_text_length]
        encoded[:len(text_bytes)] = list(text_bytes)
        
        return encoded
    
    def _process_modifiers(self, modifier_bits: np.ndarray) -> List[str]:
        """Convertit les bits de modificateurs en liste de touches."""
        modifier_names = ['ctrl', 'alt', 'shift', 'win', 'fn', 'meta', 'cmd', 'option']
        
        return [name for i, name in enumerate(modifier_names) if modifier_bits[i]]
    
    def _encode_keys(self, keys: List[str]) -> Tuple[np.ndarray, np.ndarray]:
        """Encode les touches en modificateurs et touche principale."""
        modifiers = np.zeros(8, dtype=np.int8)
        key = np.zeros(1, dtype=np.uint8)
        
        modifier_map = {
            'ctrl': 0, 'alt': 1, 'shift': 2, 'win': 3,
            'fn': 4, 'meta': 5, 'cmd': 6, 'option': 7
        }
        
        for k in keys:
            if k.lower() in modifier_map:
                modifiers[modifier_map[k.lower()]] = 1
            elif len(k) == 1:
                key[0] = ord(k.upper())
        
        return modifiers, key
    
    def sample_action(self) -> Dict[str, np.ndarray]:
        """Échantillonne une action aléatoire."""
        return {
            'action_type': np.random.randint(0, len(self.action_types)),
            'coordinates': np.random.random(2).astype(np.float32),
            'text': np.random.randint(0, 256, self.config.max_text_length, dtype=np.uint8),
            'modifiers': np.random.randint(0, 2, 8, dtype=np.int8),
            'key': np.random.randint(0, 256, 1, dtype=np.uint8),
            'scroll_direction': np.random.randint(0, 3),
            'wait_time': np.random.random(1).astype(np.float32)
        }
    
    def get_action_mask(self, observation: Dict[str, np.ndarray]) -> np.ndarray:
        """Retourne un masque des actions valides pour l'observation donnée."""
        # Par défaut, toutes les actions sont valides
        # Dans une implémentation plus sophistiquée, on pourrait restreindre
        # certaines actions selon le contexte
        return np.ones(len(self.action_types), dtype=bool)