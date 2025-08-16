#!/usr/bin/env python3
"""Script d'entraînement Behavior Cloning."""

import argparse
import logging
from pathlib import Path

from packages.common.config import Config
from packages.policy.bc_trainer import BehaviorCloningTrainer, BCConfig


def main():
    parser = argparse.ArgumentParser(description="Entraînement Behavior Cloning")
    
    parser.add_argument("--demo-dir", type=Path, required=True,
                       help="Dossier contenant les démonstrations")
    parser.add_argument("--model-dir", type=Path, default=Path("data/models"),
                       help="Dossier de sauvegarde du modèle")
    parser.add_argument("--config", type=Path, help="Fichier de configuration")
    
    # Hyperparamètres BC
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--hidden-size", type=int, default=512)
    parser.add_argument("--dropout", type=float, default=0.1)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    
    args = parser.parse_args()
    
    # Configuration
    config = Config(args.config) if args.config else Config()
    
    bc_config = BCConfig(
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        num_epochs=args.epochs,
        hidden_size=args.hidden_size,
        dropout=args.dropout,
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
        trainer = BehaviorCloningTrainer(config, bc_config)
        
        # Créer le dossier de sauvegarde
        args.model_dir.mkdir(parents=True, exist_ok=True)
        model_path = args.model_dir / "bc_model.pth"
        
        # Entraînement
        logger.info("Démarrage de l'entraînement Behavior Cloning")
        logger.info(f"Démonstrations: {args.demo_dir}")
        logger.info(f"Modèle: {model_path}")
        logger.info(f"Configuration: {bc_config}")
        
        results = trainer.train(args.demo_dir, model_path)
        
        logger.info("Entraînement terminé avec succès!")
        logger.info(f"Résultats: {results}")
        
    except Exception as e:
        logger.error(f"Erreur lors de l'entraînement: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())