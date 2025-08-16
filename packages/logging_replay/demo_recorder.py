"""Enregistreur de démonstrations pour l'entraînement BC."""

import json
import pickle
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import numpy as np

from packages.common.config import Config
from packages.rl_env.observation_space import ObservationSpace
from packages.rl_env.action_space import ActionSpace
from .session_logger import SessionLogger


class DemoRecorder:
    """Enregistreur de démonstrations pour Behavior Cloning."""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Session logger pour accéder aux données
        self.session_logger = SessionLogger(config)
        
        # Convertisseurs RL
        self.obs_space = ObservationSpace()
        self.action_space = ActionSpace()
        
        # Dossier de sortie
        self.demo_output_dir = Path(config.get('demo.output_dir', 'data/demos'))
        self.demo_output_dir.mkdir(parents=True, exist_ok=True)
    
    async def initialize(self):
        """Initialise le demo recorder."""
        await self.session_logger.initialize()
        self.logger.info("Demo Recorder initialisé")
    
    async def convert_sessions_to_demos(self, 
                                      session_ids: List[str],
                                      output_filename: str = None,
                                      success_only: bool = True) -> Path:
        """Convertit des sessions en démonstrations pour BC."""
        
        if not session_ids:
            # Récupérer automatiquement les sessions réussies
            sessions_list = self.session_logger.list_sessions(limit=100, success_only=success_only)
            session_ids = [s['session_id'] for s in sessions_list]
            
            if not session_ids:
                raise ValueError("Aucune session trouvée")
        
        self.logger.info(f"Conversion de {len(session_ids)} sessions en démonstrations")
        
        demonstrations = {
            'metadata': {
                'created_at': str(np.datetime64('now')),
                'num_sessions': len(session_ids),
                'success_only': success_only,
                'observation_space_config': self.obs_space.config.dict(),
                'action_space_config': self.action_space.config.dict()
            },
            'episodes': []
        }
        
        converted_count = 0
        
        for session_id in session_ids:
            try:
                episode_data = await self._convert_session_to_episode(session_id)
                
                if episode_data and len(episode_data['steps']) > 0:
                    demonstrations['episodes'].append(episode_data)
                    converted_count += 1
                    
            except Exception as e:
                self.logger.warning(f"Erreur conversion session {session_id}: {e}")
        
        if converted_count == 0:
            raise ValueError("Aucune session convertie avec succès")
        
        # Sauvegarder
        if not output_filename:
            output_filename = f"demonstrations_{converted_count}_episodes.pkl"
        
        output_path = self.demo_output_dir / output_filename
        
        with open(output_path, 'wb') as f:
            pickle.dump(demonstrations, f)
        
        # Sauvegarder aussi en JSON pour inspection
        json_path = output_path.with_suffix('.json')
        with open(json_path, 'w') as f:
            # Convertir les numpy arrays en listes pour JSON
            json_data = self._prepare_for_json(demonstrations)
            json.dump(json_data, f, indent=2)
        
        self.logger.info(
            f"Démonstrations sauvegardées: {output_path} "
            f"({converted_count} épisodes, {sum(len(ep['steps']) for ep in demonstrations['episodes'])} steps)"
        )
        
        return output_path
    
    async def _convert_session_to_episode(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Convertit une session en épisode de démonstration."""
        
        session_history = self.session_logger.get_session_history(session_id)
        
        if not session_history:
            self.logger.warning(f"Session non trouvée: {session_id}")
            return None
        
        # Vérifier que la session est valide
        if not session_history.get('success', False):
            self.logger.debug(f"Session non réussie ignorée: {session_id}")
            return None
        
        if not session_history['steps']:
            self.logger.debug(f"Session sans steps ignorée: {session_id}")
            return None
        
        episode = {
            'session_id': session_id,
            'command_text': session_history['command_text'],
            'command_source': session_history['command_source'],
            'start_time': session_history['start_time'],
            'end_time': session_history['end_time'],
            'total_reward': 0.0,  # À calculer
            'steps': []
        }
        
        # Convertir chaque step
        for step_idx, step_data in enumerate(session_history['steps']):
            
            try:
                # Créer une observation simulée à partir des données disponibles
                observation = self._reconstruct_observation(step_data, step_idx)
                
                # Convertir l'observation au format RL
                rl_observation = self.obs_space.convert_observation(observation)
                
                # Reconstruire l'action
                action_dict = {
                    'action_type': self._get_action_type_id(step_data['action_type']),
                    'coordinates': self._extract_coordinates(step_data['action_params']),
                    'text': self._extract_text(step_data['action_params']),
                    'modifiers': self._extract_modifiers(step_data['action_params']),
                    'key': self._extract_key(step_data['action_params']),
                    'scroll_direction': 1,  # neutral par défaut
                    'wait_time': np.array([0.0], dtype=np.float32)
                }
                
                # Calculer une récompense simple
                reward = 1.0 if step_data.get('result_success', False) else -0.1
                episode['total_reward'] += reward
                
                step_demo = {
                    'step_number': step_idx,
                    'observation': rl_observation,
                    'action': action_dict,
                    'reward': reward,
                    'done': step_idx == len(session_history['steps']) - 1,
                    'info': {
                        'original_action_type': step_data['action_type'],
                        'result_success': step_data.get('result_success', False),
                        'timestamp': step_data['timestamp']
                    }
                }
                
                episode['steps'].append(step_demo)
                
            except Exception as e:
                self.logger.warning(f"Erreur conversion step {step_idx} de {session_id}: {e}")
        
        return episode if episode['steps'] else None
    
    def _reconstruct_observation(self, step_data: Dict[str, Any], step_idx: int):
        """Reconstruit une observation à partir des données de step."""
        
        from packages.common.models import Observation, UiObject, OCRResult
        
        # Observation basique - dans un vrai système, on aurait plus de données
        observation = Observation(
            timestamp=step_data['timestamp'],
            screenshot_path=step_data.get('screenshot_path'),
            ui_elements=[],  # Pas d'éléments UI stockés dans les logs basiques
            ocr_results=[],  # Pas de résultats OCR stockés
            active_window="unknown",
            mouse_position=[0, 0],  # Position inconnue
            step_count=step_idx,
            last_action_success=step_data.get('result_success', False)
        )
        
        return observation
    
    def _get_action_type_id(self, action_type: str) -> int:
        """Convertit le type d'action en ID."""
        
        type_mapping = {
            'move_mouse': 0,
            'click': 1,
            'double_click': 2,
            'right_click': 3,
            'type_text': 4,
            'key_press': 5,
            'scroll': 6,
            'wait': 7,
            'no_op': 8
        }
        
        return type_mapping.get(action_type, 8)  # no_op par défaut
    
    def _extract_coordinates(self, params: Dict[str, Any]) -> np.ndarray:
        """Extrait les coordonnées des paramètres d'action."""
        
        x = params.get('x', 0) / 1920.0  # Normaliser
        y = params.get('y', 0) / 1080.0
        
        return np.array([x, y], dtype=np.float32)
    
    def _extract_text(self, params: Dict[str, Any]) -> np.ndarray:
        """Extrait le texte des paramètres d'action."""
        
        text = params.get('text', '')
        encoded = np.zeros(200, dtype=np.uint8)
        
        text_bytes = text.encode('ascii', errors='ignore')[:200]
        encoded[:len(text_bytes)] = list(text_bytes)
        
        return encoded
    
    def _extract_modifiers(self, params: Dict[str, Any]) -> np.ndarray:
        """Extrait les modificateurs des paramètres d'action."""
        
        modifiers = np.zeros(8, dtype=np.int8)
        
        keys = params.get('keys', [])
        if isinstance(keys, list):
            modifier_map = {
                'ctrl': 0, 'alt': 1, 'shift': 2, 'win': 3,
                'fn': 4, 'meta': 5, 'cmd': 6, 'option': 7
            }
            
            for key in keys:
                if key.lower() in modifier_map:
                    modifiers[modifier_map[key.lower()]] = 1
        
        return modifiers
    
    def _extract_key(self, params: Dict[str, Any]) -> np.ndarray:
        """Extrait la touche principale des paramètres d'action."""
        
        key = np.zeros(1, dtype=np.uint8)
        
        keys = params.get('keys', [])
        key_param = params.get('key')
        
        if key_param and len(str(key_param)) == 1:
            key[0] = ord(str(key_param).upper())
        elif isinstance(keys, list):
            for k in keys:
                if len(k) == 1 and k.isalpha():
                    key[0] = ord(k.upper())
                    break
        
        return key
    
    def _prepare_for_json(self, data):
        """Prépare les données pour la sérialisation JSON."""
        
        if isinstance(data, dict):
            return {k: self._prepare_for_json(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._prepare_for_json(item) for item in data]
        elif isinstance(data, np.ndarray):
            return data.tolist()
        elif isinstance(data, (np.integer, np.floating)):
            return data.item()
        else:
            return data
    
    def get_demo_stats(self, demo_path: Path) -> Dict[str, Any]:
        """Analyse les statistiques d'un fichier de démonstration."""
        
        if not demo_path.exists():
            raise FileNotFoundError(f"Fichier de démonstration non trouvé: {demo_path}")
        
        with open(demo_path, 'rb') as f:
            demos = pickle.load(f)
        
        episodes = demos.get('episodes', [])
        
        if not episodes:
            return {'error': 'Aucun épisode trouvé'}
        
        # Calculer les statistiques
        total_steps = sum(len(ep['steps']) for ep in episodes)
        episode_lengths = [len(ep['steps']) for ep in episodes]
        episode_rewards = [ep.get('total_reward', 0) for ep in episodes]
        
        # Analyser les types d'actions
        action_types = {}
        for episode in episodes:
            for step in episode['steps']:
                action_type = step['info'].get('original_action_type', 'unknown')
                action_types[action_type] = action_types.get(action_type, 0) + 1
        
        # Analyser les commandes
        commands = {}
        for episode in episodes:
            cmd = episode.get('command_text', 'unknown')
            commands[cmd] = commands.get(cmd, 0) + 1
        
        stats = {
            'num_episodes': len(episodes),
            'total_steps': total_steps,
            'avg_episode_length': np.mean(episode_lengths),
            'min_episode_length': min(episode_lengths),
            'max_episode_length': max(episode_lengths),
            'avg_episode_reward': np.mean(episode_rewards),
            'action_type_distribution': action_types,
            'command_distribution': commands,
            'metadata': demos.get('metadata', {})
        }
        
        return stats
    
    async def cleanup(self):
        """Nettoie les ressources."""
        await self.session_logger.cleanup()
        self.logger.info("Demo Recorder nettoyé")