#!/usr/bin/env python3
"""Script d'évaluation des modèles."""

import argparse
import logging
from pathlib import Path

from packages.common.config import Config
from packages.policy.ppo_trainer import PPOTrainer
from packages.policy.baseline_policy import BaselinePolicy


def evaluate_ppo_model(model_path: Path, config: Config, n_episodes: int = 10):
    """Évalue un modèle PPO."""
    
    trainer = PPOTrainer(config)
    
    results = trainer.evaluate(
        model_path=model_path,
        agent_service=None,  # Mode simulation
        n_eval_episodes=n_episodes
    )
    
    return results


def evaluate_baseline_policy(config: Config, tasks: list, n_episodes: int = 10):
    """Évalue la politique baseline."""
    
    policy = BaselinePolicy(config)
    
    results = {
        'tasks_evaluated': tasks,
        'n_episodes_per_task': n_episodes,
        'task_results': {}
    }
    
    for task in tasks:
        task_results = []
        
        for episode in range(n_episodes):
            policy.reset()
            policy._reset_for_task(task)
            
            steps = 0
            max_steps = 50
            
            while not policy.is_task_completed() and steps < max_steps:
                # Observation simulée
                obs = {
                    'screenshot': None,
                    'ui_elements': [],
                    'ocr_text': [],
                    'mouse_position': [0, 0],
                    'active_window': '',
                    'step_count': steps,
                    'last_action_success': True
                }
                
                action = policy.predict(obs, task)
                steps += 1
            
            success = policy.is_task_completed()
            task_results.append({
                'success': success,
                'steps': steps,
                'episode': episode
            })
        
        # Calculer les métriques pour cette tâche
        successes = sum(1 for r in task_results if r['success'])
        avg_steps = sum(r['steps'] for r in task_results) / len(task_results)
        
        results['task_results'][task] = {
            'success_rate': successes / n_episodes,
            'success_count': successes,
            'average_steps': avg_steps,
            'episodes': task_results
        }
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Évaluation des modèles")
    
    parser.add_argument("--model-type", choices=["ppo", "baseline"], required=True,
                       help="Type de modèle à évaluer")
    parser.add_argument("--model-path", type=Path,
                       help="Chemin vers le modèle (requis pour PPO)")
    parser.add_argument("--config", type=Path, help="Fichier de configuration")
    parser.add_argument("--n-episodes", type=int, default=10,
                       help="Nombre d'épisodes d'évaluation")
    parser.add_argument("--tasks", nargs="+", 
                       default=["open_chrome", "write_file", "web_search"],
                       help="Tâches à évaluer (pour baseline)")
    
    args = parser.parse_args()
    
    # Vérifications
    if args.model_type == "ppo" and not args.model_path:
        parser.error("--model-path requis pour l'évaluation PPO")
    
    if args.model_type == "ppo" and not args.model_path.exists():
        parser.error(f"Modèle non trouvé: {args.model_path}")
    
    # Configuration
    config = Config(args.config) if args.config else Config()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Évaluation du modèle {args.model_type}")
        
        if args.model_type == "ppo":
            logger.info(f"Modèle: {args.model_path}")
            results = evaluate_ppo_model(args.model_path, config, args.n_episodes)
            
        else:  # baseline
            logger.info(f"Tâches: {args.tasks}")
            results = evaluate_baseline_policy(config, args.tasks, args.n_episodes)
        
        # Afficher les résultats
        logger.info("Résultats de l'évaluation:")
        
        if args.model_type == "ppo":
            logger.info(f"  Reward moyen: {results['mean_reward']:.2f} ± {results['std_reward']:.2f}")
            logger.info(f"  Longueur moyenne: {results['mean_length']:.1f} ± {results['std_length']:.1f}")
            logger.info(f"  Taux de succès: {results['success_rate']:.2%}")
            logger.info(f"  Meilleur reward: {results['best_reward']:.2f}")
            
        else:  # baseline
            for task, task_results in results['task_results'].items():
                logger.info(f"  {task}:")
                logger.info(f"    Taux de succès: {task_results['success_rate']:.2%}")
                logger.info(f"    Steps moyens: {task_results['average_steps']:.1f}")
        
        logger.info("Évaluation terminée avec succès!")
        
    except Exception as e:
        logger.error(f"Erreur lors de l'évaluation: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())