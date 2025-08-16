"""Politique baseline scriptée pour les tâches MVP."""

import logging
import numpy as np
from typing import Dict, Any, List, Optional
from pathlib import Path

from packages.common.config import Config
from packages.rl_env.action_space import ActionSpace


class BaselinePolicy:
    """Politique baseline scriptée pour démontrer les tâches MVP."""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.action_space_manager = ActionSpace()
        
        # Scripts pour les tâches MVP
        self.task_scripts = {
            'open_chrome': self._open_chrome_script,
            'write_file': self._write_file_script,
            'web_search': self._web_search_script
        }
        
        # État interne
        self.current_task = None
        self.script_step = 0
        self.task_completed = False
        
    def predict(self, observation: Dict[str, np.ndarray], task: str = None) -> Dict[str, np.ndarray]:
        """Prédit l'action suivante selon la politique baseline."""
        
        if task and task != self.current_task:
            self._reset_for_task(task)
        
        # Exécuter le script de la tâche actuelle
        if self.current_task in self.task_scripts:
            action = self.task_scripts[self.current_task](observation)
        else:
            # Action par défaut : ne rien faire
            action = self._no_op_action()
        
        self.script_step += 1
        return action
    
    def _reset_for_task(self, task: str):
        """Remet à zéro pour une nouvelle tâche."""
        self.current_task = task.lower()
        self.script_step = 0
        self.task_completed = False
        self.logger.info(f"Démarrage de la tâche baseline: {task}")
    
    def _open_chrome_script(self, observation: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        """Script pour ouvrir Chrome."""
        
        if self.script_step == 0:
            # Étape 1: Appuyer sur Win+R pour ouvrir la boîte de dialogue Exécuter
            return self._key_press_action(['win', 'r'])
            
        elif self.script_step == 1:
            # Étape 2: Attendre un peu
            return self._wait_action(0.5)
            
        elif self.script_step == 2:
            # Étape 3: Taper "chrome"
            return self._type_text_action("chrome")
            
        elif self.script_step == 3:
            # Étape 4: Appuyer sur Entrée
            return self._key_press_action(['enter'])
            
        elif self.script_step == 4:
            # Étape 5: Attendre que Chrome s'ouvre
            return self._wait_action(3.0)
            
        else:
            # Tâche terminée
            self.task_completed = True
            return self._no_op_action()
    
    def _write_file_script(self, observation: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        """Script pour créer et écrire dans un fichier."""
        
        if self.script_step == 0:
            # Étape 1: Ouvrir le bloc-notes (Win+R, notepad)
            return self._key_press_action(['win', 'r'])
            
        elif self.script_step == 1:
            return self._wait_action(0.5)
            
        elif self.script_step == 2:
            return self._type_text_action("notepad")
            
        elif self.script_step == 3:
            return self._key_press_action(['enter'])
            
        elif self.script_step == 4:
            # Attendre que le bloc-notes s'ouvre
            return self._wait_action(2.0)
            
        elif self.script_step == 5:
            # Écrire "Bonjour"
            return self._type_text_action("Bonjour")
            
        elif self.script_step == 6:
            # Sauvegarder (Ctrl+S)
            return self._key_press_action(['ctrl', 's'])
            
        elif self.script_step == 7:
            # Attendre la boîte de dialogue
            return self._wait_action(1.0)
            
        elif self.script_step == 8:
            # Taper le nom du fichier
            return self._type_text_action("test_bonjour.txt")
            
        elif self.script_step == 9:
            # Appuyer sur Entrée pour sauvegarder
            return self._key_press_action(['enter'])
            
        elif self.script_step == 10:
            # Attendre la sauvegarde
            return self._wait_action(1.0)
            
        else:
            # Tâche terminée
            self.task_completed = True
            return self._no_op_action()
    
    def _web_search_script(self, observation: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        """Script pour effectuer une recherche web."""
        
        if self.script_step == 0:
            # Ouvrir Chrome d'abord
            return self._key_press_action(['win', 'r'])
            
        elif self.script_step == 1:
            return self._wait_action(0.5)
            
        elif self.script_step == 2:
            return self._type_text_action("chrome")
            
        elif self.script_step == 3:
            return self._key_press_action(['enter'])
            
        elif self.script_step == 4:
            return self._wait_action(3.0)
            
        elif self.script_step == 5:
            # Cliquer sur la barre d'adresse (approximativement au centre-haut)
            return self._click_action(0.5, 0.1)
            
        elif self.script_step == 6:
            return self._wait_action(0.5)
            
        elif self.script_step == 7:
            # Taper l'URL de Google
            return self._type_text_action("google.com")
            
        elif self.script_step == 8:
            return self._key_press_action(['enter'])
            
        elif self.script_step == 9:
            return self._wait_action(2.0)
            
        elif self.script_step == 10:
            # Cliquer sur la barre de recherche
            return self._click_action(0.5, 0.4)
            
        elif self.script_step == 11:
            return self._wait_action(0.5)
            
        elif self.script_step == 12:
            # Taper la recherche
            return self._type_text_action("desktop automation")
            
        elif self.script_step == 13:
            return self._key_press_action(['enter'])
            
        elif self.script_step == 14:
            return self._wait_action(2.0)
            
        else:
            self.task_completed = True
            return self._no_op_action()
    
    def _click_action(self, x_norm: float, y_norm: float) -> Dict[str, np.ndarray]:
        """Crée une action de clic."""
        return {
            'action_type': 1,  # click
            'coordinates': np.array([x_norm, y_norm], dtype=np.float32),
            'text': np.zeros(200, dtype=np.uint8),
            'modifiers': np.zeros(8, dtype=np.int8),
            'key': np.zeros(1, dtype=np.uint8),
            'scroll_direction': 1,  # none
            'wait_time': np.zeros(1, dtype=np.float32)
        }
    
    def _type_text_action(self, text: str) -> Dict[str, np.ndarray]:
        """Crée une action de saisie de texte."""
        text_encoded = np.zeros(200, dtype=np.uint8)
        text_bytes = text.encode('ascii', errors='ignore')[:200]
        text_encoded[:len(text_bytes)] = list(text_bytes)
        
        return {
            'action_type': 4,  # type_text
            'coordinates': np.zeros(2, dtype=np.float32),
            'text': text_encoded,
            'modifiers': np.zeros(8, dtype=np.int8),
            'key': np.zeros(1, dtype=np.uint8),
            'scroll_direction': 1,
            'wait_time': np.zeros(1, dtype=np.float32)
        }
    
    def _key_press_action(self, keys: List[str]) -> Dict[str, np.ndarray]:
        """Crée une action d'appui sur des touches."""
        modifiers = np.zeros(8, dtype=np.int8)
        key = np.zeros(1, dtype=np.uint8)
        
        modifier_map = {
            'ctrl': 0, 'alt': 1, 'shift': 2, 'win': 3,
            'fn': 4, 'meta': 5, 'cmd': 6, 'option': 7
        }
        
        for k in keys:
            k_lower = k.lower()
            if k_lower in modifier_map:
                modifiers[modifier_map[k_lower]] = 1
            elif k_lower == 'enter':
                key[0] = 13
            elif k_lower == 'space':
                key[0] = 32
            elif k_lower == 'tab':
                key[0] = 9
            elif len(k) == 1:
                key[0] = ord(k.upper())
        
        return {
            'action_type': 5,  # key_press
            'coordinates': np.zeros(2, dtype=np.float32),
            'text': np.zeros(200, dtype=np.uint8),
            'modifiers': modifiers,
            'key': key,
            'scroll_direction': 1,
            'wait_time': np.zeros(1, dtype=np.float32)
        }
    
    def _wait_action(self, duration: float) -> Dict[str, np.ndarray]:
        """Crée une action d'attente."""
        return {
            'action_type': 7,  # wait
            'coordinates': np.zeros(2, dtype=np.float32),
            'text': np.zeros(200, dtype=np.uint8),
            'modifiers': np.zeros(8, dtype=np.int8),
            'key': np.zeros(1, dtype=np.uint8),
            'scroll_direction': 1,
            'wait_time': np.array([min(1.0, duration / 5.0)], dtype=np.float32)
        }
    
    def _no_op_action(self) -> Dict[str, np.ndarray]:
        """Crée une action "ne rien faire"."""
        return {
            'action_type': 8,  # no_op
            'coordinates': np.zeros(2, dtype=np.float32),
            'text': np.zeros(200, dtype=np.uint8),
            'modifiers': np.zeros(8, dtype=np.int8),
            'key': np.zeros(1, dtype=np.uint8),
            'scroll_direction': 1,
            'wait_time': np.zeros(1, dtype=np.float32)
        }
    
    def is_task_completed(self) -> bool:
        """Retourne si la tâche actuelle est terminée."""
        return self.task_completed
    
    def get_available_tasks(self) -> List[str]:
        """Retourne la liste des tâches disponibles."""
        return list(self.task_scripts.keys())
    
    def reset(self):
        """Remet à zéro la politique."""
        self.current_task = None
        self.script_step = 0
        self.task_completed = False