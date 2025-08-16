"""Manager pour rejouer les sessions enregistrées."""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

from packages.common.config import Config
from packages.common.models import Action, ActionType
from packages.common.errors import ReplayError
from .session_logger import SessionLogger


class ReplayConfig:
    """Configuration pour le replay."""
    
    def __init__(self):
        self.playback_speed = 1.0  # Vitesse de lecture (1.0 = temps réel)
        self.pause_between_steps = 0.5  # Pause entre les étapes (secondes)
        self.show_screenshots = True  # Afficher les screenshots
        self.dry_run = True  # Mode dry-run (ne pas exécuter les actions)
        self.interactive = False  # Mode interactif (pause à chaque étape)


class ReplayManager:
    """Manager pour rejouer les sessions."""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Session logger pour accéder aux données
        self.session_logger = SessionLogger(config)
        
        # État du replay
        self.is_replaying = False
        self.current_session = None
        self.current_step = 0
        
        # Callbacks
        self.step_callback: Optional[Callable] = None
        self.screenshot_callback: Optional[Callable] = None
    
    async def initialize(self):
        """Initialise le replay manager."""
        await self.session_logger.initialize()
        self.logger.info("Replay Manager initialisé")
    
    def set_callbacks(self, 
                     step_callback: Optional[Callable] = None,
                     screenshot_callback: Optional[Callable] = None):
        """Configure les callbacks pour le replay."""
        self.step_callback = step_callback
        self.screenshot_callback = screenshot_callback
    
    async def replay_session(self, 
                           session_id: str, 
                           replay_config: ReplayConfig = None,
                           agent_service=None) -> Dict[str, Any]:
        """Rejoue une session complète."""
        
        if self.is_replaying:
            raise ReplayError("Replay déjà en cours")
        
        config = replay_config or ReplayConfig()
        
        # Récupérer l'historique de la session
        session_history = self.session_logger.get_session_history(session_id)
        
        if not session_history:
            raise ReplayError(f"Session non trouvée: {session_id}")
        
        self.logger.info(f"Début du replay de la session: {session_id}")
        self.logger.info(f"Commande: {session_history['command_text']}")
        self.logger.info(f"Steps: {len(session_history['steps'])}")
        self.logger.info(f"Mode: {'Dry-run' if config.dry_run else 'Exécution réelle'}")
        
        self.is_replaying = True
        self.current_session = session_history
        self.current_step = 0
        
        replay_results = {
            'session_id': session_id,
            'total_steps': len(session_history['steps']),
            'steps_replayed': 0,
            'errors': [],
            'start_time': time.time(),
            'end_time': None,
            'success': False
        }
        
        try:
            # Rejouer chaque étape
            for step_idx, step_data in enumerate(session_history['steps']):
                
                self.current_step = step_idx
                
                self.logger.info(f"Replay step {step_idx + 1}/{len(session_history['steps'])}")
                
                # Callback avant l'étape
                if self.step_callback:
                    await self.step_callback('before_step', step_idx, step_data)
                
                # Afficher le screenshot si disponible
                if config.show_screenshots and step_data['screenshot_path']:
                    await self._show_screenshot(step_data['screenshot_path'])
                
                # Mode interactif
                if config.interactive:
                    await self._wait_for_user_input(step_data)
                
                # Exécuter l'action
                try:
                    if not config.dry_run and agent_service:
                        await self._execute_action(step_data, agent_service)
                    else:
                        self._log_dry_run_action(step_data)
                    
                    replay_results['steps_replayed'] += 1
                    
                except Exception as e:
                    error_msg = f"Erreur step {step_idx}: {e}"
                    self.logger.error(error_msg)
                    replay_results['errors'].append(error_msg)
                
                # Callback après l'étape
                if self.step_callback:
                    await self.step_callback('after_step', step_idx, step_data)
                
                # Pause entre les étapes
                if config.pause_between_steps > 0:
                    await asyncio.sleep(config.pause_between_steps / config.playback_speed)
            
            replay_results['success'] = len(replay_results['errors']) == 0
            
        except Exception as e:
            self.logger.error(f"Erreur générale de replay: {e}")
            replay_results['errors'].append(f"Erreur générale: {e}")
            
        finally:
            self.is_replaying = False
            self.current_session = None
            self.current_step = 0
            replay_results['end_time'] = time.time()
        
        duration = replay_results['end_time'] - replay_results['start_time']
        self.logger.info(
            f"Replay terminé - "
            f"Steps: {replay_results['steps_replayed']}/{replay_results['total_steps']}, "
            f"Erreurs: {len(replay_results['errors'])}, "
            f"Durée: {duration:.1f}s"
        )
        
        return replay_results
    
    async def _execute_action(self, step_data: Dict[str, Any], agent_service):
        """Exécute une action lors du replay."""
        
        # Reconstruire l'action
        action = Action(
            type=ActionType(step_data['action_type']),
            parameters=step_data['action_params'],
            timestamp=time.time()
        )
        
        # Exécuter via l'agent service
        # Note: Ceci nécessiterait une méthode pour exécuter des actions individuelles
        self.logger.info(f"Exécution de l'action: {action.type.value}")
        
        # Pour l'instant, on simule l'exécution
        await asyncio.sleep(0.1)
    
    def _log_dry_run_action(self, step_data: Dict[str, Any]):
        """Affiche l'action en mode dry-run."""
        
        action_type = step_data['action_type']
        params = step_data['action_params']
        
        self.logger.info(f"[DRY-RUN] Action: {action_type}")
        
        if params:
            for key, value in params.items():
                self.logger.info(f"  {key}: {value}")
    
    async def _show_screenshot(self, screenshot_path: str):
        """Affiche un screenshot."""
        
        if self.screenshot_callback:
            await self.screenshot_callback(screenshot_path)
        else:
            self.logger.info(f"Screenshot: {screenshot_path}")
    
    async def _wait_for_user_input(self, step_data: Dict[str, Any]):
        """Attend l'input utilisateur en mode interactif."""
        
        print(f"\n--- Step {self.current_step + 1} ---")
        print(f"Action: {step_data['action_type']}")
        print(f"Paramètres: {step_data['action_params']}")
        print(f"Résultat attendu: {step_data['result_success']}")
        
        if step_data['screenshot_path']:
            print(f"Screenshot: {step_data['screenshot_path']}")
        
        response = input("\nAppuyez sur Entrée pour continuer, 's' pour passer, 'q' pour quitter: ")
        
        if response.lower() == 'q':
            raise ReplayError("Replay interrompu par l'utilisateur")
        elif response.lower() == 's':
            self.logger.info("Étape passée")
    
    async def compare_sessions(self, session_id1: str, session_id2: str) -> Dict[str, Any]:
        """Compare deux sessions."""
        
        session1 = self.session_logger.get_session_history(session_id1)
        session2 = self.session_logger.get_session_history(session_id2)
        
        if not session1 or not session2:
            raise ReplayError("Une ou plusieurs sessions non trouvées")
        
        comparison = {
            'session1_id': session_id1,
            'session2_id': session_id2,
            'commands_match': session1['command_text'] == session2['command_text'],
            'steps_count_match': len(session1['steps']) == len(session2['steps']),
            'success_match': session1['success'] == session2['success'],
            'step_differences': [],
            'summary': {}
        }
        
        # Comparer les étapes
        max_steps = max(len(session1['steps']), len(session2['steps']))
        
        for i in range(max_steps):
            step1 = session1['steps'][i] if i < len(session1['steps']) else None
            step2 = session2['steps'][i] if i < len(session2['steps']) else None
            
            if not step1:
                comparison['step_differences'].append({
                    'step': i,
                    'type': 'missing_in_session1',
                    'action2': step2['action_type'] if step2 else None
                })
            elif not step2:
                comparison['step_differences'].append({
                    'step': i,
                    'type': 'missing_in_session2',
                    'action1': step1['action_type']
                })
            elif step1['action_type'] != step2['action_type']:
                comparison['step_differences'].append({
                    'step': i,
                    'type': 'action_type_different',
                    'action1': step1['action_type'],
                    'action2': step2['action_type']
                })
        
        # Résumé
        comparison['summary'] = {
            'total_differences': len(comparison['step_differences']),
            'identical': len(comparison['step_differences']) == 0,
            'session1_steps': len(session1['steps']),
            'session2_steps': len(session2['steps'])
        }
        
        return comparison
    
    def list_available_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Liste les sessions disponibles pour replay."""
        
        return self.session_logger.list_sessions(limit=limit)
    
    async def export_session(self, session_id: str, export_path: Path) -> Path:
        """Exporte une session au format JSON."""
        
        session_history = self.session_logger.get_session_history(session_id)
        
        if not session_history:
            raise ReplayError(f"Session non trouvée: {session_id}")
        
        export_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(export_path, 'w', encoding='utf-8') as f:
            json.dump(session_history, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Session exportée: {export_path}")
        
        return export_path
    
    async def cleanup(self):
        """Nettoie les ressources."""
        
        if self.is_replaying:
            self.is_replaying = False
        
        await self.session_logger.cleanup()
        self.logger.info("Replay Manager nettoyé")