"""Entraîneur PPO pour l'apprentissage par renforcement."""

import logging
from pathlib import Path
from typing import Dict, Any, Optional
import numpy as np
from pydantic import BaseModel

try:
    from stable_baselines3 import PPO
    from stable_baselines3.common.env_util import make_vec_env
    from stable_baselines3.common.callbacks import CheckpointCallback, EvalCallback
    from stable_baselines3.common.monitor import Monitor
    from stable_baselines3.common.vec_env import DummyVecEnv
    HAS_SB3 = True
except ImportError:
    HAS_SB3 = False

from packages.common.config import Config
from packages.common.errors import TrainingError
from packages.rl_env import DesktopAgentEnv


class PPOConfig(BaseModel):
    """Configuration pour PPO."""
    learning_rate: float = 3e-4
    n_steps: int = 2048
    batch_size: int = 64
    n_epochs: int = 10
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_range: float = 0.2
    ent_coef: float = 0.0
    vf_coef: float = 0.5
    max_grad_norm: float = 0.5
    total_timesteps: int = 100000
    eval_freq: int = 5000
    save_freq: int = 10000
    device: str = "auto"


class PPOTrainer:
    """Entraîneur PPO pour l'agent desktop."""
    
    def __init__(self, config: Config, ppo_config: PPOConfig = None):
        if not HAS_SB3:
            raise TrainingError("Stable-Baselines3 requis: pip install stable-baselines3")
        
        self.config = config
        self.ppo_config = ppo_config or PPOConfig()
        self.logger = logging.getLogger(__name__)
        
        # Modèle PPO
        self.model = None
        self.env = None
        self.eval_env = None
        
        # Métriques
        self.training_metrics = []
    
    def create_environment(self, agent_service=None, n_envs: int = 1) -> DummyVecEnv:
        """Crée l'environnement d'entraînement."""
        
        def make_env():
            env = DesktopAgentEnv(agent_service=agent_service)
            env = Monitor(env)  # Pour le logging des métriques
            return env
        
        if n_envs == 1:
            env = DummyVecEnv([make_env])
        else:
            env = make_vec_env(make_env, n_envs=n_envs)
        
        return env
    
    def initialize_model(self, env, model_path: Optional[Path] = None):
        """Initialise le modèle PPO."""
        
        if model_path and model_path.exists():
            # Charger un modèle existant
            self.logger.info(f"Chargement du modèle depuis {model_path}")
            self.model = PPO.load(str(model_path), env=env)
        else:
            # Créer un nouveau modèle
            self.logger.info("Création d'un nouveau modèle PPO")
            self.model = PPO(
                "MultiInputPolicy",  # Pour les observations Dict
                env,
                learning_rate=self.ppo_config.learning_rate,
                n_steps=self.ppo_config.n_steps,
                batch_size=self.ppo_config.batch_size,
                n_epochs=self.ppo_config.n_epochs,
                gamma=self.ppo_config.gamma,
                gae_lambda=self.ppo_config.gae_lambda,
                clip_range=self.ppo_config.clip_range,
                ent_coef=self.ppo_config.ent_coef,
                vf_coef=self.ppo_config.vf_coef,
                max_grad_norm=self.ppo_config.max_grad_norm,
                device=self.ppo_config.device,
                verbose=1
            )
    
    def setup_callbacks(self, log_dir: Path, model_save_dir: Path):
        """Configure les callbacks d'entraînement."""
        
        callbacks = []
        
        # Callback de sauvegarde
        checkpoint_callback = CheckpointCallback(
            save_freq=self.ppo_config.save_freq,
            save_path=str(model_save_dir),
            name_prefix="ppo_desktop_agent"
        )
        callbacks.append(checkpoint_callback)
        
        # Callback d'évaluation
        if self.eval_env:
            eval_callback = EvalCallback(
                self.eval_env,
                best_model_save_path=str(model_save_dir / "best_model"),
                log_path=str(log_dir),
                eval_freq=self.ppo_config.eval_freq,
                deterministic=True,
                render=False
            )
            callbacks.append(eval_callback)
        
        return callbacks
    
    def train(self, 
              agent_service=None,
              log_dir: Path = None,
              model_save_dir: Path = None,
              pretrained_model_path: Optional[Path] = None) -> Dict[str, Any]:
        """Entraîne le modèle PPO."""
        
        # Créer les dossiers
        if log_dir:
            log_dir.mkdir(parents=True, exist_ok=True)
        if model_save_dir:
            model_save_dir.mkdir(parents=True, exist_ok=True)
        
        # Créer les environnements
        self.env = self.create_environment(agent_service, n_envs=1)
        self.eval_env = self.create_environment(agent_service, n_envs=1)
        
        # Initialiser le modèle
        self.initialize_model(self.env, pretrained_model_path)
        
        # Configurer les callbacks
        callbacks = self.setup_callbacks(log_dir, model_save_dir) if log_dir and model_save_dir else []
        
        # Entraînement
        self.logger.info(f"Début de l'entraînement PPO - {self.ppo_config.total_timesteps} timesteps")
        
        try:
            self.model.learn(
                total_timesteps=self.ppo_config.total_timesteps,
                callback=callbacks,
                progress_bar=True
            )
            
            # Sauvegarder le modèle final
            if model_save_dir:
                final_model_path = model_save_dir / "final_model"
                self.model.save(str(final_model_path))
                self.logger.info(f"Modèle final sauvegardé: {final_model_path}")
            
            # Métriques finales
            results = {
                'total_timesteps': self.ppo_config.total_timesteps,
                'model_path': str(final_model_path) if model_save_dir else None,
                'training_completed': True
            }
            
            self.logger.info("Entraînement PPO terminé avec succès")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'entraînement: {e}")
            raise TrainingError(f"Échec de l'entraînement PPO: {e}")
        
        finally:
            # Nettoyer les environnements
            if self.env:
                self.env.close()
            if self.eval_env:
                self.eval_env.close()
    
    def evaluate(self, 
                 model_path: Path,
                 agent_service=None,
                 n_eval_episodes: int = 10) -> Dict[str, Any]:
        """Évalue un modèle entraîné."""
        
        if not model_path.exists():
            raise TrainingError(f"Modèle non trouvé: {model_path}")
        
        # Créer l'environnement d'évaluation
        eval_env = self.create_environment(agent_service, n_envs=1)
        
        # Charger le modèle
        model = PPO.load(str(model_path))
        
        # Évaluation
        episode_rewards = []
        episode_lengths = []
        success_count = 0
        
        for episode in range(n_eval_episodes):
            obs = eval_env.reset()
            episode_reward = 0
            episode_length = 0
            done = False
            
            while not done:
                action, _ = model.predict(obs, deterministic=True)
                obs, reward, done, info = eval_env.step(action)
                
                episode_reward += reward[0]
                episode_length += 1
                
                # Vérifier le succès
                if info[0].get('task_completed', False):
                    success_count += 1
            
            episode_rewards.append(episode_reward)
            episode_lengths.append(episode_length)
            
            self.logger.info(f"Épisode {episode+1}: Reward={episode_reward:.2f}, Length={episode_length}")
        
        # Calculer les métriques
        results = {
            'n_episodes': n_eval_episodes,
            'mean_reward': np.mean(episode_rewards),
            'std_reward': np.std(episode_rewards),
            'mean_length': np.mean(episode_lengths),
            'std_length': np.std(episode_lengths),
            'success_rate': success_count / n_eval_episodes,
            'success_count': success_count,
            'best_reward': max(episode_rewards),
            'worst_reward': min(episode_rewards)
        }
        
        self.logger.info(
            f"Évaluation terminée - "
            f"Reward moyen: {results['mean_reward']:.2f} ± {results['std_reward']:.2f}, "
            f"Taux de succès: {results['success_rate']:.2%}"
        )
        
        eval_env.close()
        
        return results
    
    def load_model(self, model_path: Path, env=None):
        """Charge un modèle pour l'inférence."""
        
        if not model_path.exists():
            raise TrainingError(f"Modèle non trouvé: {model_path}")
        
        self.model = PPO.load(str(model_path), env=env)
        self.logger.info(f"Modèle chargé: {model_path}")
    
    def predict(self, observation, deterministic: bool = True):
        """Prédit une action."""
        
        if self.model is None:
            raise TrainingError("Modèle non chargé")
        
        return self.model.predict(observation, deterministic=deterministic)
    
    def get_training_config(self) -> Dict[str, Any]:
        """Retourne la configuration d'entraînement."""
        return self.ppo_config.dict()