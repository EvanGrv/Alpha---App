#!/usr/bin/env python3
"""Script d'entraînement PPO."""

import argparse
import logging
from pathlib import Path

from packages.common.config import Config
from packages.policy.ppo_trainer import PPOTrainer, PPOConfig


def main():
    parser = argparse.ArgumentParser(description="Entraînement PPO")
    
    parser.add_argument("--log-dir", type=Path, default=Path("logs/ppo"),
                       help="Dossier de logs")
    parser.add_argument("--model-dir", type=Path, default=Path("data/models"),
                       help="Dossier de sauvegarde des modèles")
    parser.add_argument("--config", type=Path, help="Fichier de configuration")
    parser.add_argument("--pretrained", type=Path, help="Modèle pré-entraîné")
    
    # Hyperparamètres PPO
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--n-steps", type=int, default=2048)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--n-epochs", type=int, default=10)
    parser.add_argument("--total-timesteps", type=int, default=100000)
    parser.add_argument("--eval-freq", type=int, default=5000)
    parser.add_argument("--save-freq", type=int, default=10000)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    
    # Mode simulation (sans agent réel)
    parser.add_argument("--simulation", action="store_true",
                       help="Mode simulation sans agent réel")
    
    args = parser.parse_args()
    
    # Configuration
    config = Config(args.config) if args.config else Config()
    
    ppo_config = PPOConfig(
        learning_rate=args.learning_rate,
        n_steps=args.n_steps,
        batch_size=args.batch_size,
        n_epochs=args.n_epochs,
        total_timesteps=args.total_timesteps,
        eval_freq=args.eval_freq,
        save_freq=args.save_freq,
        device=args.device
    )
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger(__name__)
    
    try:
        # Créer le trainer
        trainer = PPOTrainer(config, ppo_config)
        
        # Agent service (None pour simulation)
        agent_service = None
        if not args.simulation:
            logger.warning("Mode agent réel non implémenté, utilisation de la simulation")
        
        # Entraînement
        logger.info("Démarrage de l'entraînement PPO")
        logger.info(f"Mode: {'Simulation' if args.simulation else 'Agent réel'}")
        logger.info(f"Logs: {args.log_dir}")
        logger.info(f"Modèles: {args.model_dir}")
        logger.info(f"Configuration: {ppo_config}")
        
        results = trainer.train(
            agent_service=agent_service,
            log_dir=args.log_dir,
            model_save_dir=args.model_dir,
            pretrained_model_path=args.pretrained
        )
        
        logger.info("Entraînement terminé avec succès!")
        logger.info(f"Résultats: {results}")
        
    except Exception as e:
        logger.error(f"Erreur lors de l'entraînement: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())