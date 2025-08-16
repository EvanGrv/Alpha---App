"""Entraîneur Behavior Cloning pour apprendre à partir des démonstrations."""

import logging
import pickle
from pathlib import Path
from typing import List, Dict, Any, Tuple
import numpy as np
from pydantic import BaseModel

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import Dataset, DataLoader
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

from packages.common.config import Config
from packages.common.errors import TrainingError
from packages.rl_env.observation_space import ObservationSpace
from packages.rl_env.action_space import ActionSpace


class BCConfig(BaseModel):
    """Configuration pour Behavior Cloning."""
    batch_size: int = 32
    learning_rate: float = 0.001
    num_epochs: int = 100
    validation_split: float = 0.2
    hidden_size: int = 512
    dropout: float = 0.1
    device: str = "auto"  # auto, cpu, cuda


class DemonstrationDataset(Dataset):
    """Dataset pour les démonstrations."""
    
    def __init__(self, demonstrations: List[Dict[str, Any]]):
        self.demonstrations = demonstrations
        
    def __len__(self):
        return len(self.demonstrations)
    
    def __getitem__(self, idx):
        demo = self.demonstrations[idx]
        
        # Convertir l'observation en tensor
        obs_tensor = self._observation_to_tensor(demo['observation'])
        
        # Convertir l'action en tensor
        action_tensor = self._action_to_tensor(demo['action'])
        
        return obs_tensor, action_tensor
    
    def _observation_to_tensor(self, obs: Dict[str, np.ndarray]) -> torch.Tensor:
        """Convertit une observation en tensor."""
        # Aplatir toutes les observations en un seul vecteur
        features = []
        
        # Screenshot (réduire drastiquement la dimensionnalité)
        if 'screenshot' in obs:
            screenshot = obs['screenshot']
            if len(screenshot.shape) == 3:
                # Moyenner les canaux et sous-échantillonner
                gray = np.mean(screenshot, axis=2)
                downsampled = gray[::8, ::8]  # Sous-échantillonner par 8
                features.append(downsampled.flatten())
        
        # UI elements
        if 'ui_elements' in obs:
            features.append(obs['ui_elements'].flatten())
        
        # OCR text (prendre seulement les premiers caractères)
        if 'ocr_text' in obs:
            features.append(obs['ocr_text'][:100])  # Limiter à 100 caractères
        
        # Mouse position
        if 'mouse_position' in obs:
            features.append(obs['mouse_position'])
        
        # Active window (premiers caractères)
        if 'active_window' in obs:
            features.append(obs['active_window'][:50])
        
        # Step count et last action success
        if 'step_count' in obs:
            features.append(obs['step_count'])
        if 'last_action_success' in obs:
            features.append(obs['last_action_success'])
        
        # Concaténer toutes les features
        combined = np.concatenate(features)
        
        return torch.FloatTensor(combined)
    
    def _action_to_tensor(self, action: Dict[str, np.ndarray]) -> torch.Tensor:
        """Convertit une action en tensor."""
        features = []
        
        # Action type (one-hot encoding)
        action_type = np.zeros(9)  # 9 types d'actions
        action_type[int(action['action_type'])] = 1.0
        features.append(action_type)
        
        # Coordinates
        features.append(action['coordinates'])
        
        # Text (premiers caractères)
        features.append(action['text'][:50])
        
        # Modifiers
        features.append(action['modifiers'].astype(np.float32))
        
        # Key
        features.append(action['key'].astype(np.float32))
        
        # Scroll direction (one-hot)
        scroll = np.zeros(3)
        scroll[int(action['scroll_direction'])] = 1.0
        features.append(scroll)
        
        # Wait time
        features.append(action['wait_time'])
        
        combined = np.concatenate(features)
        return torch.FloatTensor(combined)


class BCNetwork(nn.Module):
    """Réseau de neurones pour Behavior Cloning."""
    
    def __init__(self, input_size: int, output_size: int, hidden_size: int = 512, dropout: float = 0.1):
        super().__init__()
        
        self.network = nn.Sequential(
            nn.Linear(input_size, hidden_size),
            nn.ReLU(),
            nn.Dropout(dropout),
            
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),
            nn.Dropout(dropout),
            
            nn.Linear(hidden_size, hidden_size // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            
            nn.Linear(hidden_size // 2, output_size)
        )
    
    def forward(self, x):
        return self.network(x)


class BehaviorCloningTrainer:
    """Entraîneur pour l'apprentissage par imitation."""
    
    def __init__(self, config: Config, bc_config: BCConfig = None):
        if not HAS_TORCH:
            raise TrainingError("PyTorch requis pour BC: pip install torch")
        
        self.config = config
        self.bc_config = bc_config or BCConfig()
        self.logger = logging.getLogger(__name__)
        
        # Device
        if self.bc_config.device == "auto":
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(self.bc_config.device)
        
        self.logger.info(f"Utilisation du device: {self.device}")
        
        # Réseau et optimiseur
        self.network = None
        self.optimizer = None
        self.criterion = nn.MSELoss()
        
        # Métriques
        self.training_losses = []
        self.validation_losses = []
    
    def load_demonstrations(self, demo_dir: Path) -> List[Dict[str, Any]]:
        """Charge les démonstrations depuis un dossier."""
        
        demo_files = list(demo_dir.glob("*.pkl"))
        
        if not demo_files:
            raise TrainingError(f"Aucune démonstration trouvée dans {demo_dir}")
        
        demonstrations = []
        
        for demo_file in demo_files:
            try:
                with open(demo_file, 'rb') as f:
                    demo_data = pickle.load(f)
                
                # Vérifier le format
                if 'episodes' in demo_data:
                    for episode in demo_data['episodes']:
                        for step in episode['steps']:
                            if 'observation' in step and 'action' in step:
                                demonstrations.append({
                                    'observation': step['observation'],
                                    'action': step['action'],
                                    'reward': step.get('reward', 0.0)
                                })
                
                self.logger.info(f"Chargé {len(demo_data.get('episodes', []))} épisodes de {demo_file}")
                
            except Exception as e:
                self.logger.warning(f"Erreur lors du chargement de {demo_file}: {e}")
        
        self.logger.info(f"Total: {len(demonstrations)} démonstrations chargées")
        
        if not demonstrations:
            raise TrainingError("Aucune démonstration valide trouvée")
        
        return demonstrations
    
    def prepare_data(self, demonstrations: List[Dict[str, Any]]) -> Tuple[DataLoader, DataLoader]:
        """Prépare les données d'entraînement et de validation."""
        
        # Mélanger les démonstrations
        np.random.shuffle(demonstrations)
        
        # Diviser en train/validation
        split_idx = int(len(demonstrations) * (1 - self.bc_config.validation_split))
        train_demos = demonstrations[:split_idx]
        val_demos = demonstrations[split_idx:]
        
        # Créer les datasets
        train_dataset = DemonstrationDataset(train_demos)
        val_dataset = DemonstrationDataset(val_demos)
        
        # Créer les dataloaders
        train_loader = DataLoader(
            train_dataset,
            batch_size=self.bc_config.batch_size,
            shuffle=True,
            num_workers=0  # Éviter les problèmes de multiprocessing
        )
        
        val_loader = DataLoader(
            val_dataset,
            batch_size=self.bc_config.batch_size,
            shuffle=False,
            num_workers=0
        )
        
        self.logger.info(f"Données préparées: {len(train_demos)} train, {len(val_demos)} validation")
        
        return train_loader, val_loader
    
    def initialize_network(self, input_size: int, output_size: int):
        """Initialise le réseau de neurones."""
        
        self.network = BCNetwork(
            input_size=input_size,
            output_size=output_size,
            hidden_size=self.bc_config.hidden_size,
            dropout=self.bc_config.dropout
        ).to(self.device)
        
        self.optimizer = optim.Adam(
            self.network.parameters(),
            lr=self.bc_config.learning_rate
        )
        
        self.logger.info(f"Réseau initialisé: {input_size} -> {output_size}")
    
    def train(self, demo_dir: Path, model_save_path: Path = None) -> Dict[str, Any]:
        """Entraîne le modèle BC."""
        
        # Charger les démonstrations
        demonstrations = self.load_demonstrations(demo_dir)
        
        # Préparer les données
        train_loader, val_loader = self.prepare_data(demonstrations)
        
        # Déterminer les tailles d'entrée et de sortie
        sample_obs, sample_action = train_loader.dataset[0]
        input_size = sample_obs.shape[0]
        output_size = sample_action.shape[0]
        
        # Initialiser le réseau
        self.initialize_network(input_size, output_size)
        
        # Entraînement
        best_val_loss = float('inf')
        
        for epoch in range(self.bc_config.num_epochs):
            
            # Phase d'entraînement
            train_loss = self._train_epoch(train_loader)
            
            # Phase de validation
            val_loss = self._validate_epoch(val_loader)
            
            # Enregistrer les métriques
            self.training_losses.append(train_loss)
            self.validation_losses.append(val_loss)
            
            # Sauvegarder le meilleur modèle
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                if model_save_path:
                    self._save_model(model_save_path)
            
            # Logging
            if epoch % 10 == 0 or epoch == self.bc_config.num_epochs - 1:
                self.logger.info(
                    f"Epoch {epoch+1}/{self.bc_config.num_epochs} - "
                    f"Train Loss: {train_loss:.4f}, Val Loss: {val_loss:.4f}"
                )
        
        # Résultats finaux
        results = {
            'final_train_loss': self.training_losses[-1],
            'final_val_loss': self.validation_losses[-1],
            'best_val_loss': best_val_loss,
            'num_epochs': self.bc_config.num_epochs,
            'num_demonstrations': len(demonstrations)
        }
        
        self.logger.info(f"Entraînement terminé. Meilleure loss validation: {best_val_loss:.4f}")
        
        return results
    
    def _train_epoch(self, train_loader: DataLoader) -> float:
        """Entraîne une époque."""
        
        self.network.train()
        total_loss = 0.0
        num_batches = 0
        
        for observations, actions in train_loader:
            observations = observations.to(self.device)
            actions = actions.to(self.device)
            
            # Forward pass
            predicted_actions = self.network(observations)
            loss = self.criterion(predicted_actions, actions)
            
            # Backward pass
            self.optimizer.zero_grad()
            loss.backward()
            self.optimizer.step()
            
            total_loss += loss.item()
            num_batches += 1
        
        return total_loss / num_batches
    
    def _validate_epoch(self, val_loader: DataLoader) -> float:
        """Valide une époque."""
        
        self.network.eval()
        total_loss = 0.0
        num_batches = 0
        
        with torch.no_grad():
            for observations, actions in val_loader:
                observations = observations.to(self.device)
                actions = actions.to(self.device)
                
                predicted_actions = self.network(observations)
                loss = self.criterion(predicted_actions, actions)
                
                total_loss += loss.item()
                num_batches += 1
        
        return total_loss / num_batches
    
    def _save_model(self, save_path: Path):
        """Sauvegarde le modèle."""
        
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        torch.save({
            'model_state_dict': self.network.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'config': self.bc_config,
            'training_losses': self.training_losses,
            'validation_losses': self.validation_losses
        }, save_path)
        
        self.logger.info(f"Modèle sauvegardé: {save_path}")
    
    def load_model(self, model_path: Path):
        """Charge un modèle sauvegardé."""
        
        if not model_path.exists():
            raise TrainingError(f"Modèle non trouvé: {model_path}")
        
        checkpoint = torch.load(model_path, map_location=self.device)
        
        # Recréer le réseau avec la bonne architecture
        # Note: Il faudrait sauvegarder les tailles aussi
        self.network.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        
        self.training_losses = checkpoint.get('training_losses', [])
        self.validation_losses = checkpoint.get('validation_losses', [])
        
        self.logger.info(f"Modèle chargé: {model_path}")
    
    def predict(self, observation: torch.Tensor) -> torch.Tensor:
        """Prédit une action à partir d'une observation."""
        
        if self.network is None:
            raise TrainingError("Modèle non initialisé")
        
        self.network.eval()
        
        with torch.no_grad():
            observation = observation.to(self.device)
            if len(observation.shape) == 1:
                observation = observation.unsqueeze(0)  # Ajouter batch dimension
            
            predicted_action = self.network(observation)
            
            return predicted_action.cpu()