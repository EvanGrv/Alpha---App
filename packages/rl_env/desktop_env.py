"""Environnement Gymnasium pour l'agent desktop."""

import asyncio
import logging
import time
from typing import Dict, Any, Tuple, Optional
from pathlib import Path

import gymnasium as gym
import numpy as np
from pydantic import BaseModel

from packages.common.config import Config
from packages.common.models import Command, CommandSource, ExecutionSession
from packages.common.errors import DesktopAgentError
from .observation_space import ObservationSpace, ObservationConfig
from .action_space import ActionSpace, ActionConfig


class EnvironmentConfig(BaseModel):
    """Configuration de l'environnement RL."""
    max_steps: int = 100
    reward_success: float = 10.0
    reward_failure: float = -1.0
    reward_step: float = -0.01
    reward_progress: float = 1.0
    timeout_seconds: float = 300.0  # 5 minutes max par épisode
    
    # Critères de succès pour les tâches MVP
    success_keywords: Dict[str, list] = {
        'open_chrome': ['chrome', 'google', 'browser'],
        'write_file': ['fichier', 'texte', 'sauvegarde', 'bonjour']
    }


class DesktopAgentEnv(gym.Env):
    """Environnement Gymnasium pour l'entraînement de l'agent desktop."""
    
    metadata = {'render_modes': ['human', 'rgb_array'], 'render_fps': 1}
    
    def __init__(self, 
                 agent_service=None,
                 env_config: EnvironmentConfig = None,
                 obs_config: ObservationConfig = None,
                 action_config: ActionConfig = None):
        super().__init__()
        
        self.agent_service = agent_service
        self.env_config = env_config or EnvironmentConfig()
        
        # Espaces d'observation et d'action
        self.obs_space_manager = ObservationSpace(obs_config)
        self.action_space_manager = ActionSpace(action_config)
        
        self.observation_space = self.obs_space_manager.space
        self.action_space = self.action_space_manager.space
        
        # État de l'environnement
        self.current_session: Optional[ExecutionSession] = None
        self.step_count = 0
        self.episode_start_time = 0
        self.last_observation = None
        self.current_task = None
        
        # Logging
        self.logger = logging.getLogger(__name__)
        
        # Métriques
        self.episode_rewards = []
        self.episode_lengths = []
        self.success_count = 0
        self.total_episodes = 0
    
    def reset(self, seed: Optional[int] = None, options: Optional[dict] = None) -> Tuple[Dict, Dict]:
        """Remet l'environnement à zéro pour un nouvel épisode."""
        super().reset(seed=seed)
        
        if options is None:
            options = {}
        
        # Choisir une tâche
        self.current_task = options.get('task', self._sample_task())
        
        # Réinitialiser l'état
        self.step_count = 0
        self.episode_start_time = time.time()
        self.current_session = None
        
        # Obtenir l'observation initiale
        initial_obs = self._get_observation()
        
        info = {
            'task': self.current_task,
            'episode': self.total_episodes,
            'max_steps': self.env_config.max_steps
        }
        
        self.logger.info(f"Nouvel épisode démarré - Tâche: {self.current_task}")
        
        return initial_obs, info
    
    def step(self, action: Dict[str, np.ndarray]) -> Tuple[Dict, float, bool, bool, Dict]:
        """Exécute une action et retourne le nouvel état."""
        
        self.step_count += 1
        
        # Convertir l'action RL en action du domaine
        domain_action = self.action_space_manager.convert_to_domain_action(action)
        
        # Exécuter l'action
        reward, done, info = self._execute_action(domain_action)
        
        # Obtenir la nouvelle observation
        observation = self._get_observation()
        
        # Vérifier les conditions de fin
        truncated = self._check_truncation()
        
        # Mettre à jour les métriques
        info.update({
            'step': self.step_count,
            'action_type': self.action_space_manager.action_types[action['action_type']],
            'reward': reward,
            'task': self.current_task
        })
        
        if done or truncated:
            self._end_episode(reward, done, info)
        
        return observation, reward, done, truncated, info
    
    def _execute_action(self, action) -> Tuple[float, bool, Dict]:
        """Exécute l'action via l'agent service."""
        
        reward = self.env_config.reward_step  # Récompense de base négative
        done = False
        info = {'action_success': False, 'error': None}
        
        try:
            if self.agent_service:
                # Exécuter l'action via l'agent
                # Note: Dans un vrai environnement, ceci serait asynchrone
                # Pour la simulation, on peut utiliser une version synchrone
                
                result = asyncio.run(self._async_execute_action(action))
                
                if result and result.success:
                    reward += self.env_config.reward_progress
                    info['action_success'] = True
                    
                    # Vérifier si la tâche est accomplie
                    if self._check_task_completion(result):
                        reward += self.env_config.reward_success
                        done = True
                        info['task_completed'] = True
                        self.success_count += 1
                        
                else:
                    reward += self.env_config.reward_failure
                    info['error'] = getattr(result, 'error', 'Action failed')
                    
            else:
                # Mode simulation sans agent réel
                reward = self._simulate_action_reward(action)
                info['action_success'] = True
                
                # Chance aléatoire de compléter la tâche
                if np.random.random() < 0.1:  # 10% de chance
                    done = True
                    reward += self.env_config.reward_success
                    info['task_completed'] = True
                    
        except Exception as e:
            self.logger.error(f"Erreur lors de l'exécution de l'action: {e}")
            reward += self.env_config.reward_failure
            info['error'] = str(e)
        
        return reward, done, info
    
    async def _async_execute_action(self, action):
        """Exécute l'action de manière asynchrone."""
        # Convertir l'action en commande
        command_text = self._action_to_command_text(action)
        
        command = Command(
            source=CommandSource.SYSTEM,
            text=command_text,
            timestamp=time.time()
        )
        
        # Exécuter via l'agent service
        return await self.agent_service.execute_command(command)
    
    def _action_to_command_text(self, action) -> str:
        """Convertit une action en texte de commande."""
        action_type = action.type.value
        params = action.parameters
        
        if action_type == 'move_mouse':
            return f"Déplacer la souris à ({params.get('x', 0)}, {params.get('y', 0)})"
        elif action_type == 'click':
            return f"Cliquer à ({params.get('x', 0)}, {params.get('y', 0)})"
        elif action_type == 'type_text':
            return f"Taper le texte: {params.get('text', '')}"
        elif action_type == 'key_press':
            keys = params.get('keys', [])
            return f"Appuyer sur les touches: {'+'.join(keys)}"
        else:
            return f"Exécuter action: {action_type}"
    
    def _get_observation(self) -> Dict[str, np.ndarray]:
        """Obtient l'observation actuelle."""
        
        try:
            if self.agent_service:
                # Obtenir l'observation via l'agent
                domain_obs = asyncio.run(self.agent_service.get_current_observation())
                observation = self.obs_space_manager.convert_observation(domain_obs)
            else:
                # Mode simulation
                observation = self._simulate_observation()
            
            self.last_observation = observation
            return observation
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'obtention de l'observation: {e}")
            return self._get_empty_observation()
    
    def _simulate_observation(self) -> Dict[str, np.ndarray]:
        """Simule une observation pour l'entraînement sans agent réel."""
        
        # Dimensions réduites
        screen_h = int(1080 * 0.25)
        screen_w = int(1920 * 0.25)
        
        return {
            'screenshot': np.random.randint(0, 256, (screen_h, screen_w, 3), dtype=np.uint8),
            'ui_elements': np.random.random((50, 6)).astype(np.float32),
            'ocr_text': np.random.randint(0, 256, (1000,), dtype=np.uint8),
            'mouse_position': np.random.random(2).astype(np.float32),
            'active_window': np.random.randint(0, 256, (100,), dtype=np.uint8),
            'step_count': np.array([self.step_count], dtype=np.int32),
            'last_action_success': np.array([1], dtype=np.int32)
        }
    
    def _get_empty_observation(self) -> Dict[str, np.ndarray]:
        """Retourne une observation vide en cas d'erreur."""
        screen_h = int(1080 * 0.25)
        screen_w = int(1920 * 0.25)
        
        return {
            'screenshot': np.zeros((screen_h, screen_w, 3), dtype=np.uint8),
            'ui_elements': np.zeros((50, 6), dtype=np.float32),
            'ocr_text': np.zeros((1000,), dtype=np.uint8),
            'mouse_position': np.zeros(2, dtype=np.float32),
            'active_window': np.zeros((100,), dtype=np.uint8),
            'step_count': np.array([self.step_count], dtype=np.int32),
            'last_action_success': np.array([0], dtype=np.int32)
        }
    
    def _simulate_action_reward(self, action) -> float:
        """Simule une récompense pour une action."""
        # Récompense basique basée sur le type d'action
        action_rewards = {
            'click': 0.1,
            'type_text': 0.2,
            'move_mouse': 0.05,
            'key_press': 0.15,
            'no_op': -0.1
        }
        
        action_type = action.type.value
        return action_rewards.get(action_type, 0.0)
    
    def _check_task_completion(self, result) -> bool:
        """Vérifie si la tâche actuelle est accomplie."""
        if not self.current_task or not result:
            return False
        
        # Vérifier selon les mots-clés de succès
        result_text = str(result).lower()
        
        for task_type, keywords in self.env_config.success_keywords.items():
            if task_type in self.current_task.lower():
                return any(keyword in result_text for keyword in keywords)
        
        return False
    
    def _check_truncation(self) -> bool:
        """Vérifie les conditions de troncature."""
        
        # Limite de steps
        if self.step_count >= self.env_config.max_steps:
            return True
        
        # Timeout
        if time.time() - self.episode_start_time > self.env_config.timeout_seconds:
            return True
        
        return False
    
    def _sample_task(self) -> str:
        """Échantillonne une tâche aléatoire."""
        tasks = [
            "Ouvre Google Chrome",
            "Crée un fichier texte et écris Bonjour",
            "Recherche 'desktop automation' sur Google",
            "Ouvre le bloc-notes",
            "Sauvegarde le fichier actuel"
        ]
        
        return np.random.choice(tasks)
    
    def _end_episode(self, final_reward: float, success: bool, info: Dict):
        """Termine l'épisode et met à jour les métriques."""
        
        self.total_episodes += 1
        self.episode_lengths.append(self.step_count)
        
        # Calculer la récompense totale de l'épisode
        episode_reward = sum(getattr(self, '_episode_rewards', [final_reward]))
        self.episode_rewards.append(episode_reward)
        
        # Logging
        self.logger.info(
            f"Épisode {self.total_episodes} terminé - "
            f"Steps: {self.step_count}, "
            f"Reward: {episode_reward:.2f}, "
            f"Success: {success}, "
            f"Task: {self.current_task}"
        )
        
        # Statistiques
        if len(self.episode_rewards) >= 100:
            avg_reward = np.mean(self.episode_rewards[-100:])
            avg_length = np.mean(self.episode_lengths[-100:])
            success_rate = self.success_count / min(100, self.total_episodes)
            
            self.logger.info(
                f"Stats derniers 100 épisodes - "
                f"Reward moyen: {avg_reward:.2f}, "
                f"Longueur moyenne: {avg_length:.1f}, "
                f"Taux de succès: {success_rate:.2%}"
            )
    
    def render(self, mode='human'):
        """Rendu de l'environnement."""
        if mode == 'human':
            # Affichage console
            print(f"Step: {self.step_count}, Task: {self.current_task}")
            
        elif mode == 'rgb_array':
            # Retourner l'image de l'écran
            if self.last_observation and 'screenshot' in self.last_observation:
                return self.last_observation['screenshot']
            else:
                # Image vide
                return np.zeros((270, 480, 3), dtype=np.uint8)
    
    def close(self):
        """Ferme l'environnement."""
        if self.agent_service:
            # Nettoyer les ressources de l'agent
            try:
                asyncio.run(self.agent_service.cleanup())
            except:
                pass
        
        self.logger.info("Environnement fermé")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Retourne les métriques de performance."""
        
        if not self.episode_rewards:
            return {}
        
        return {
            'total_episodes': self.total_episodes,
            'success_count': self.success_count,
            'success_rate': self.success_count / max(1, self.total_episodes),
            'average_reward': np.mean(self.episode_rewards),
            'average_length': np.mean(self.episode_lengths),
            'last_10_rewards': self.episode_rewards[-10:] if len(self.episode_rewards) >= 10 else self.episode_rewards,
            'best_reward': max(self.episode_rewards),
            'worst_reward': min(self.episode_rewards)
        }