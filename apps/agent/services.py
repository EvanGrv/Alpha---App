"""
Services principaux pour l'agent Desktop Agent.

Coordonne tous les composants de l'agent.
"""

import asyncio
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from packages.common.config import get_settings
from packages.common.errors import DesktopAgentError
from packages.common.logging_utils import get_agent_logger
from packages.common.models import Command, CommandSource, ExecutionSession, Plan, StepStatus
from packages.nlu import NLUManager
from packages.perception import PerceptionManager
from packages.planner import PlannerManager
from packages.skills import SkillManager
from packages.voice import VoiceManager

logger = get_agent_logger()


class AgentService:
    """Service principal de l'agent Desktop Agent."""
    
    def __init__(
        self,
        skill_manager: SkillManager,
        nlu_manager: NLUManager,
        planner_manager: PlannerManager,
        perception_manager: PerceptionManager
    ):
        self.settings = get_settings()
        
        # Composants principaux
        self.skill_manager = skill_manager
        self.nlu_manager = nlu_manager
        self.planner_manager = planner_manager
        self.perception_manager = perception_manager
        
        # État du service
        self._running = False
        self._start_time = None
        self._active_sessions: Dict[str, ExecutionSession] = {}
        self._event_subscribers: List[asyncio.Queue] = []
        
        # Statistiques
        self._commands_processed = 0
        self._commands_successful = 0
        
        logger.info("Service agent initialisé")
    
    async def start(self) -> None:
        """Démarre le service agent."""
        try:
            if self._running:
                logger.warning("Service agent déjà en cours d'exécution")
                return
            
            self._running = True
            self._start_time = datetime.now()
            
            # Démarrer l'observation continue si configuré
            if self.settings.perception.screenshot_interval > 0:
                await self.perception_manager.start_continuous_observation(
                    interval=self.settings.perception.screenshot_interval,
                    save_screenshots=False,
                    include_ocr=True
                )
            
            await self._broadcast_event({
                "type": "service_started",
                "timestamp": datetime.now().isoformat(),
                "message": "Service agent démarré"
            })
            
            logger.info("Service agent démarré")
            
        except Exception as e:
            logger.error(f"Erreur démarrage service: {e}")
            raise
    
    async def stop(self) -> None:
        """Arrête le service agent."""
        try:
            if not self._running:
                return
            
            self._running = False
            
            # Arrêter l'observation continue
            await self.perception_manager.stop_continuous_observation()
            
            # Annuler les sessions actives
            for session in self._active_sessions.values():
                if session.status == StepStatus.RUNNING:
                    session.status = StepStatus.FAILED
                    session.end_time = datetime.now()
            
            await self._broadcast_event({
                "type": "service_stopped",
                "timestamp": datetime.now().isoformat(),
                "message": "Service agent arrêté"
            })
            
            logger.info("Service agent arrêté")
            
        except Exception as e:
            logger.error(f"Erreur arrêt service: {e}")
    
    async def process_command(
        self,
        command: Command,
        require_confirmation: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Traite une commande utilisateur complète.
        
        Args:
            command: Commande à traiter
            require_confirmation: Forcer la confirmation (override)
            
        Returns:
            Résultat complet du traitement
        """
        try:
            start_time = time.time()
            self._commands_processed += 1
            
            logger.info(f"Traitement commande: '{command.text}'")
            
            await self._broadcast_event({
                "type": "command_received",
                "command_id": command.id,
                "text": command.text,
                "source": command.source.value,
                "timestamp": command.timestamp.isoformat()
            })
            
            # Étape 1: Analyse NLU
            nlu_result = self.nlu_manager.understand(command.text)
            
            if not nlu_result["ready_for_execution"]:
                return {
                    "success": False,
                    "stage": "nlu",
                    "message": "Commande non comprise ou incomplète",
                    "nlu_result": nlu_result,
                    "suggestions": nlu_result.get("suggestions", {})
                }
            
            # Étape 2: Planification
            plan_result = self.planner_manager.create_plan(
                intent=nlu_result["intent"],
                context=await self._get_execution_context()
            )
            
            if not plan_result["execution_decision"]["approved"]:
                return {
                    "success": False,
                    "stage": "planning",
                    "message": "Plan rejeté par les guardrails de sécurité",
                    "plan_result": plan_result,
                    "blocking_reasons": plan_result["execution_decision"]["blocking_reasons"]
                }
            
            # Vérifier la confirmation
            needs_confirmation = (
                require_confirmation or
                plan_result["execution_decision"]["requires_confirmation"] or
                command.require_confirmation
            )
            
            if needs_confirmation:
                # Retourner le plan pour confirmation
                return {
                    "success": True,
                    "stage": "confirmation_required",
                    "message": "Confirmation requise avant exécution",
                    "plan_summary": plan_result["plan"]["summary"],
                    "plan_id": plan_result["plan"]["id"],
                    "estimated_duration": plan_result["plan"]["estimated_duration"],
                    "warnings": plan_result["execution_decision"]["warnings"],
                    "nlu_result": nlu_result,
                    "plan_result": plan_result
                }
            
            # Étape 3: Exécution
            execution_result = await self._execute_plan(
                plan_result["plan"]["id"],
                command.id
            )
            
            # Résultat final
            success = execution_result["success"]
            if success:
                self._commands_successful += 1
            
            duration = time.time() - start_time
            
            result = {
                "success": success,
                "stage": "completed",
                "message": execution_result["message"],
                "duration": duration,
                "session_id": execution_result.get("session_id"),
                "nlu_result": nlu_result,
                "plan_result": plan_result,
                "execution_result": execution_result
            }
            
            await self._broadcast_event({
                "type": "command_completed",
                "command_id": command.id,
                "success": success,
                "duration": duration,
                "message": result["message"]
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Erreur traitement commande '{command.text}': {e}")
            
            await self._broadcast_event({
                "type": "command_error",
                "command_id": command.id,
                "error": str(e)
            })
            
            return {
                "success": False,
                "stage": "error",
                "message": f"Erreur traitement: {e}",
                "error": str(e)
            }
    
    async def execute_plan_by_id(
        self,
        plan_id: str,
        command_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Exécute un plan par son ID (après confirmation).
        
        Args:
            plan_id: ID du plan à exécuter
            command_id: ID de la commande d'origine
            
        Returns:
            Résultat de l'exécution
        """
        try:
            logger.info(f"Exécution plan: {plan_id}")
            
            # Récupérer le plan
            plan = self.planner_manager.get_plan_by_id(plan_id)
            if not plan:
                raise DesktopAgentError(f"Plan {plan_id} non trouvé")
            
            return await self._execute_plan(plan_id, command_id)
            
        except Exception as e:
            logger.error(f"Erreur exécution plan {plan_id}: {e}")
            return {
                "success": False,
                "message": f"Erreur exécution: {e}",
                "error": str(e)
            }
    
    async def get_current_observation(self) -> Dict[str, Any]:
        """
        Retourne l'observation actuelle du bureau.
        
        Returns:
            Observation formatée pour l'API
        """
        try:
            observation = await self.perception_manager.get_current_observation()
            
            return {
                "timestamp": observation.timestamp.isoformat(),
                "screenshot": {
                    "width": observation.screenshot.width,
                    "height": observation.screenshot.height,
                    "monitor_id": observation.screenshot.monitor_id,
                    "file_path": observation.screenshot.file_path
                },
                "ui_elements_count": len(observation.ui_elements),
                "text_matches_count": len(observation.text_matches),
                "active_window": {
                    "name": observation.active_window.name,
                    "bounds": observation.active_window.bounds.model_dump()
                } if observation.active_window else None,
                "mouse_position": observation.mouse_position,
                "platform": observation.platform.value
            }
            
        except Exception as e:
            logger.error(f"Erreur récupération observation: {e}")
            return {"error": str(e)}
    
    async def get_system_status(self) -> Dict[str, Any]:
        """
        Retourne le statut complet du système.
        
        Returns:
            Statut détaillé
        """
        try:
            return {
                "service": {
                    "running": self._running,
                    "uptime": (
                        (datetime.now() - self._start_time).total_seconds()
                        if self._start_time else 0
                    ),
                    "commands_processed": self._commands_processed,
                    "commands_successful": self._commands_successful,
                    "success_rate": (
                        self._commands_successful / self._commands_processed
                        if self._commands_processed > 0 else 0.0
                    )
                },
                "active_sessions": len(self._active_sessions),
                "components": {
                    "nlu": self.nlu_manager.get_nlu_stats(),
                    "planner": self.planner_manager.get_planner_stats(),
                    "skills": self.skill_manager.get_manager_stats(),
                    "perception": self.perception_manager.get_performance_stats()
                },
                "system": {
                    "platform": self.settings.platform.value,
                    "debug": self.settings.debug
                }
            }
            
        except Exception as e:
            logger.error(f"Erreur récupération statut: {e}")
            return {"error": str(e)}
    
    async def get_health_status(self) -> Dict[str, Any]:
        """
        Retourne le statut de santé pour le health check.
        
        Returns:
            Statut de santé
        """
        try:
            services_health = {}
            overall_healthy = True
            
            # Vérifier chaque composant
            try:
                nlu_stats = self.nlu_manager.get_nlu_stats()
                services_health["nlu"] = {"status": "healthy", "processed": nlu_stats["processed_count"]}
            except Exception as e:
                services_health["nlu"] = {"status": "unhealthy", "error": str(e)}
                overall_healthy = False
            
            try:
                planner_stats = self.planner_manager.get_planner_stats()
                services_health["planner"] = {"status": "healthy", "plans": planner_stats["plans_generated"]}
            except Exception as e:
                services_health["planner"] = {"status": "unhealthy", "error": str(e)}
                overall_healthy = False
            
            try:
                skill_stats = self.skill_manager.get_manager_stats()
                services_health["skills"] = {"status": "healthy", "total_skills": skill_stats["total_skills"]}
            except Exception as e:
                services_health["skills"] = {"status": "unhealthy", "error": str(e)}
                overall_healthy = False
            
            try:
                perception_stats = self.perception_manager.get_performance_stats()
                services_health["perception"] = {
                    "status": "healthy",
                    "continuous_capture": perception_stats["continuous_capture"]
                }
            except Exception as e:
                services_health["perception"] = {"status": "unhealthy", "error": str(e)}
                overall_healthy = False
            
            return {
                "healthy": overall_healthy and self._running,
                "timestamp": datetime.now().isoformat(),
                "uptime": (
                    (datetime.now() - self._start_time).total_seconds()
                    if self._start_time else 0
                ),
                "services": services_health
            }
            
        except Exception as e:
            return {
                "healthy": False,
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
    
    def subscribe_to_events(self) -> asyncio.Queue:
        """
        S'abonne aux événements du service.
        
        Returns:
            Queue pour recevoir les événements
        """
        event_queue = asyncio.Queue()
        self._event_subscribers.append(event_queue)
        return event_queue
    
    def unsubscribe_from_events(self, event_queue: asyncio.Queue) -> None:
        """
        Se désabonne des événements.
        
        Args:
            event_queue: Queue à supprimer
        """
        if event_queue in self._event_subscribers:
            self._event_subscribers.remove(event_queue)
    
    # Méthodes privées
    
    async def _execute_plan(self, plan_id: str, command_id: Optional[str] = None) -> Dict[str, Any]:
        """Exécute un plan complet."""
        plan = self.planner_manager.get_plan_by_id(plan_id)
        if not plan:
            raise DesktopAgentError(f"Plan {plan_id} non trouvé")
        
        # Créer une session d'exécution
        session = ExecutionSession(
            plan=plan,
            status=StepStatus.RUNNING,
            initial_observation=await self.perception_manager.get_current_observation()
        )
        
        self._active_sessions[session.id] = session
        
        try:
            await self._broadcast_event({
                "type": "execution_started",
                "session_id": session.id,
                "plan_id": plan_id,
                "command_id": command_id,
                "actions_count": len(plan.actions)
            })
            
            # Exécuter chaque action
            for i, action in enumerate(plan.actions):
                step_result = await self._execute_action(action, session.id, i)
                session.step_results.append(step_result)
                
                await self._broadcast_event({
                    "type": "step_completed",
                    "session_id": session.id,
                    "step_index": i,
                    "step_result": {
                        "status": step_result.status.value,
                        "message": step_result.error_message or "Succès",
                        "duration": step_result.duration
                    }
                })
                
                # Arrêter si échec critique
                if step_result.status == StepStatus.FAILED:
                    break
            
            # Finaliser la session
            session.status = StepStatus.SUCCESS if session.success_rate > 0.8 else StepStatus.FAILED
            session.end_time = datetime.now()
            session.final_observation = await self.perception_manager.get_current_observation()
            
            success = session.status == StepStatus.SUCCESS
            
            await self._broadcast_event({
                "type": "execution_completed",
                "session_id": session.id,
                "success": success,
                "duration": session.duration,
                "success_rate": session.success_rate
            })
            
            return {
                "success": success,
                "session_id": session.id,
                "message": f"Exécution {'réussie' if success else 'échouée'}",
                "duration": session.duration,
                "success_rate": session.success_rate,
                "steps_completed": len(session.step_results)
            }
            
        except Exception as e:
            session.status = StepStatus.FAILED
            session.end_time = datetime.now()
            
            await self._broadcast_event({
                "type": "execution_error",
                "session_id": session.id,
                "error": str(e)
            })
            
            raise
        
        finally:
            # Nettoyer la session après un délai
            asyncio.create_task(self._cleanup_session(session.id, delay=300))  # 5 minutes
    
    async def _execute_action(self, action, session_id: str, step_index: int):
        """Exécute une action individuelle."""
        from packages.common.models import StepResult
        
        step_result = StepResult(
            step_id=f"{session_id}_{step_index}",
            status=StepStatus.RUNNING
        )
        
        try:
            # Vérifier si c'est une compétence
            if "skill_name" in action.parameters:
                skill_name = action.parameters["skill_name"]
                skill_params = action.parameters.get("skill_parameters", {})
                
                # Exécuter la compétence
                result = await self.skill_manager.execute_skill(
                    skill_name,
                    skill_params,
                    SkillParameters(
                        timeout=action.timeout,
                        screenshot_before=True,
                        screenshot_after=True
                    )
                )
                
                step_result.status = StepStatus.SUCCESS if result.success else StepStatus.FAILED
                step_result.error_message = result.error
                step_result.output = result.data
                
            else:
                # Action primitive (non implémentée pour l'instant)
                step_result.status = StepStatus.SKIPPED
                step_result.error_message = "Actions primitives non implémentées"
            
        except Exception as e:
            step_result.status = StepStatus.FAILED
            step_result.error_message = str(e)
        
        finally:
            step_result.end_time = datetime.now()
        
        return step_result
    
    async def _get_execution_context(self) -> Dict[str, Any]:
        """Récupère le contexte d'exécution actuel."""
        try:
            observation = await self.perception_manager.get_current_observation()
            
            return {
                "active_window": {
                    "name": observation.active_window.name,
                    "bounds": observation.active_window.bounds.model_dump()
                } if observation.active_window else None,
                "running_apps": [
                    {"name": elem.name, "role": elem.role.value}
                    for elem in observation.ui_elements
                    if elem.role.value == "window"
                ],
                "mouse_position": observation.mouse_position,
                "timestamp": observation.timestamp.isoformat()
            }
        except Exception as e:
            logger.warning(f"Erreur récupération contexte: {e}")
            return {}
    
    async def _broadcast_event(self, event: Dict[str, Any]) -> None:
        """Diffuse un événement à tous les abonnés."""
        if not self._event_subscribers:
            return
        
        # Supprimer les queues fermées
        active_subscribers = []
        for queue in self._event_subscribers:
            try:
                queue.put_nowait(event)
                active_subscribers.append(queue)
            except asyncio.QueueFull:
                logger.warning("Queue d'événements pleine, abandon")
            except Exception:
                # Queue fermée ou invalide
                pass
        
        self._event_subscribers = active_subscribers
    
    async def _cleanup_session(self, session_id: str, delay: float = 300) -> None:
        """Nettoie une session après un délai."""
        await asyncio.sleep(delay)
        if session_id in self._active_sessions:
            del self._active_sessions[session_id]
            logger.debug(f"Session {session_id} nettoyée")