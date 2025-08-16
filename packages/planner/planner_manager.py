"""
Gestionnaire de planification principal pour Desktop Agent.

Coordonne la génération de plans et l'application des guardrails.
"""

import time
from typing import Any, Dict, List, Optional

from ..common.config import get_settings
from ..common.errors import PlannerError, PlanValidationError
from ..common.logging_utils import get_planner_logger
from ..common.models import Intent, Plan
from ..skills import SkillManager
from .guardrails import GuardrailsEngine
from .plan_generator import PlanGenerator

logger = get_planner_logger()


class PlannerManager:
    """Gestionnaire principal de planification."""
    
    def __init__(self, skill_manager: SkillManager):
        self.settings = get_settings()
        self.skill_manager = skill_manager
        
        # Initialiser les composants
        self.plan_generator = PlanGenerator(skill_manager)
        self.guardrails = GuardrailsEngine()
        
        # Statistiques
        self._plans_generated = 0
        self._plans_approved = 0
        self._plans_rejected = 0
        self._plan_cache = {}
        
        logger.info("Gestionnaire de planification initialisé")
    
    def create_plan(
        self,
        intent: Intent,
        context: Optional[Dict[str, Any]] = None,
        optimize: bool = True
    ) -> Dict[str, Any]:
        """
        Crée un plan d'exécution complet avec vérifications de sécurité.
        
        Args:
            intent: Intention à planifier
            context: Contexte d'exécution
            optimize: Optimiser le plan généré
            
        Returns:
            Résultat complet de planification
        """
        try:
            start_time = time.time()
            self._plans_generated += 1
            
            logger.info(f"Création plan pour intention: {intent.type.value}")
            
            # Étape 1: Génération du plan initial
            plan = self.plan_generator.generate_plan(intent, context)
            
            # Étape 2: Optimisation si demandée
            if optimize:
                plan = self.plan_generator.optimize_plan(plan, context)
            
            # Étape 3: Validation du plan
            plan_validation = self.plan_generator.validate_plan(plan)
            
            # Étape 4: Vérifications de sécurité (guardrails)
            security_check = self.guardrails.check_plan(plan, context)
            
            # Étape 5: Décision finale
            final_decision = self._make_execution_decision(plan_validation, security_check)
            
            # Construire le résultat complet
            result = {
                "plan": {
                    "id": plan.id,
                    "intent_type": plan.intent.type.value,
                    "summary": plan.summary,
                    "actions_count": len(plan.actions),
                    "estimated_duration": plan.estimated_duration,
                    "risk_level": plan.risk_level,
                    "actions": [
                        {
                            "type": action.type.value if hasattr(action.type, 'value') else str(action.type),
                            "description": action.description,
                            "parameters": action.parameters
                        }
                        for action in plan.actions
                    ]
                },
                "validation": plan_validation,
                "security_check": security_check,
                "execution_decision": final_decision,
                "generation_time": time.time() - start_time
            }
            
            # Mettre à jour les statistiques
            if final_decision["approved"]:
                self._plans_approved += 1
            else:
                self._plans_rejected += 1
            
            # Cache le plan si approuvé
            if final_decision["approved"]:
                self._plan_cache[plan.id] = plan
            
            logger.info(
                f"Plan créé: {'APPROUVÉ' if final_decision['approved'] else 'REJETÉ'}",
                plan_id=plan.id,
                actions_count=len(plan.actions),
                duration=result["generation_time"],
                requires_confirmation=final_decision["requires_confirmation"]
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Erreur création plan: {e}")
            self._plans_rejected += 1
            raise PlannerError(f"Erreur planification: {e}")
    
    def get_plan_by_id(self, plan_id: str) -> Optional[Plan]:
        """
        Récupère un plan par son ID.
        
        Args:
            plan_id: ID du plan
            
        Returns:
            Plan trouvé ou None
        """
        return self._plan_cache.get(plan_id)
    
    def validate_intent_for_planning(self, intent: Intent) -> Dict[str, Any]:
        """
        Valide une intention avant planification.
        
        Args:
            intent: Intention à valider
            
        Returns:
            Résultat de validation
        """
        try:
            validation = {
                "valid": True,
                "errors": [],
                "warnings": [],
                "suggestions": []
            }
            
            # Vérifier la confiance de l'intention
            if intent.confidence < 0.5:
                validation["warnings"].append(
                    f"Confiance faible pour l'intention: {intent.confidence:.2f}"
                )
                validation["suggestions"].append(
                    "Reformulez votre demande pour améliorer la compréhension"
                )
            
            # Vérifier les slots requis selon le type d'intention
            required_slots = self._get_required_slots(intent.type)
            missing_slots = []
            
            for slot in required_slots:
                if slot not in intent.slots or not intent.slots[slot]:
                    missing_slots.append(slot)
            
            if missing_slots:
                validation["valid"] = False
                validation["errors"].append(
                    f"Paramètres manquants: {', '.join(missing_slots)}"
                )
                validation["suggestions"].extend(
                    self._get_slot_suggestions(intent.type, missing_slots)
                )
            
            # Simulation des guardrails
            if validation["valid"]:
                security_sim = self.guardrails.simulate_check(intent, intent.slots)
                
                if not security_sim["overall_passed"]:
                    validation["warnings"].extend([
                        error["message"] for error in security_sim.get("errors", [])
                    ])
                    
                    if not security_sim["can_execute"]:
                        validation["valid"] = False
                        validation["errors"].append("Plan bloqué par les guardrails de sécurité")
            
            return validation
            
        except Exception as e:
            logger.error(f"Erreur validation intention: {e}")
            return {
                "valid": False,
                "errors": [f"Erreur validation: {e}"],
                "warnings": [],
                "suggestions": []
            }
    
    def get_plan_suggestions(self, partial_intent: Intent) -> Dict[str, Any]:
        """
        Fournit des suggestions pour compléter un plan.
        
        Args:
            partial_intent: Intention partielle
            
        Returns:
            Suggestions de complétion
        """
        try:
            suggestions = {
                "completion_options": [],
                "similar_plans": [],
                "parameter_suggestions": {}
            }
            
            # Suggestions de paramètres manquants
            required_slots = self._get_required_slots(partial_intent.type)
            
            for slot in required_slots:
                if slot not in partial_intent.slots:
                    suggestions["parameter_suggestions"][slot] = (
                        self._get_parameter_suggestions(partial_intent.type, slot)
                    )
            
            # Suggestions basées sur des plans similaires précédents
            similar_plans = self._find_similar_plans(partial_intent)
            suggestions["similar_plans"] = [
                {
                    "plan_id": plan.id,
                    "summary": plan.summary,
                    "success_probability": 0.8  # Placeholder
                }
                for plan in similar_plans[:3]
            ]
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Erreur suggestions plan: {e}")
            return {"error": str(e)}
    
    def estimate_plan_complexity(self, intent: Intent) -> Dict[str, Any]:
        """
        Estime la complexité d'un plan avant génération.
        
        Args:
            intent: Intention à estimer
            
        Returns:
            Estimation de complexité
        """
        try:
            # Estimation basée sur le type d'intention
            complexity_map = {
                "open_app": {"level": "simple", "actions": 2, "duration": 3.0},
                "focus_app": {"level": "simple", "actions": 1, "duration": 1.0},
                "click_text": {"level": "simple", "actions": 2, "duration": 2.0},
                "type_text": {"level": "simple", "actions": 1, "duration": 2.0},
                "save_file": {"level": "medium", "actions": 2, "duration": 3.0},
                "web_search": {"level": "medium", "actions": 5, "duration": 8.0},
                "write_text_file": {"level": "complex", "actions": 4, "duration": 6.0}
            }
            
            base_complexity = complexity_map.get(
                intent.type.value,
                {"level": "unknown", "actions": 3, "duration": 5.0}
            )
            
            # Ajustements basés sur les paramètres
            adjustments = {"duration_multiplier": 1.0, "risk_increase": 0}
            
            if intent.type.value == "type_text":
                text_length = len(intent.slots.get("text", ""))
                adjustments["duration_multiplier"] = 1.0 + (text_length / 100)
            
            elif intent.type.value == "write_text_file":
                content_length = len(intent.slots.get("content", ""))
                adjustments["duration_multiplier"] = 1.0 + (content_length / 200)
                
                if intent.slots.get("path"):
                    adjustments["risk_increase"] = 1
            
            # Calcul final
            estimated_duration = base_complexity["duration"] * adjustments["duration_multiplier"]
            risk_level = "low"
            
            if adjustments["risk_increase"] > 0:
                risk_level = "medium"
            
            return {
                "complexity_level": base_complexity["level"],
                "estimated_actions": base_complexity["actions"],
                "estimated_duration": estimated_duration,
                "risk_level": risk_level,
                "confidence": intent.confidence,
                "likely_success": self._estimate_success_probability(intent)
            }
            
        except Exception as e:
            logger.error(f"Erreur estimation complexité: {e}")
            return {"error": str(e)}
    
    def get_planner_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques du planificateur.
        
        Returns:
            Statistiques détaillées
        """
        return {
            "plans_generated": self._plans_generated,
            "plans_approved": self._plans_approved,
            "plans_rejected": self._plans_rejected,
            "approval_rate": (
                self._plans_approved / self._plans_generated 
                if self._plans_generated > 0 else 0.0
            ),
            "cached_plans": len(self._plan_cache),
            "active_rules": len(self.guardrails._rules),
            "skill_manager_stats": self.skill_manager.get_manager_stats()
        }
    
    def clear_plan_cache(self) -> None:
        """Vide le cache des plans."""
        cleared_count = len(self._plan_cache)
        self._plan_cache.clear()
        logger.info(f"Cache des plans vidé: {cleared_count} plans supprimés")
    
    def reset_stats(self) -> None:
        """Remet à zéro les statistiques."""
        self._plans_generated = 0
        self._plans_approved = 0
        self._plans_rejected = 0
        logger.info("Statistiques du planificateur remises à zéro")
    
    # Méthodes privées
    
    def _make_execution_decision(
        self,
        plan_validation: Dict[str, Any],
        security_check: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Prend la décision finale d'exécution."""
        decision = {
            "approved": False,
            "requires_confirmation": False,
            "blocking_reasons": [],
            "warnings": [],
            "recommendations": []
        }
        
        # Vérifier la validation du plan
        if not plan_validation["valid"]:
            decision["blocking_reasons"].extend(plan_validation["errors"])
            decision["recommendations"].append("Corrigez les erreurs de plan")
        
        # Vérifier la sécurité
        if not security_check["can_execute"]:
            decision["blocking_reasons"].extend([
                error["message"] for error in security_check["errors"]
            ])
            decision["recommendations"].append("Vérifiez les paramètres de sécurité")
        
        # Ajouter les avertissements
        decision["warnings"].extend(plan_validation.get("warnings", []))
        decision["warnings"].extend([
            warning["message"] for warning in security_check.get("warnings", [])
        ])
        
        # Décision finale
        if not decision["blocking_reasons"]:
            decision["approved"] = True
            
            # Confirmation nécessaire si avertissements ou configuration
            decision["requires_confirmation"] = (
                security_check.get("requires_confirmation", False) or
                len(decision["warnings"]) > 0
            )
        
        return decision
    
    def _get_required_slots(self, intent_type) -> List[str]:
        """Retourne les slots requis pour un type d'intention."""
        required_map = {
            "open_app": ["app_name"],
            "focus_app": ["app_name"],
            "click_text": ["text"],
            "type_text": ["text"],
            "web_search": ["query"],
            "write_text_file": ["content"]
        }
        
        return required_map.get(intent_type.value, [])
    
    def _get_slot_suggestions(self, intent_type, missing_slots: List[str]) -> List[str]:
        """Génère des suggestions pour les slots manquants."""
        suggestions = []
        
        for slot in missing_slots:
            if slot == "app_name":
                suggestions.append("Spécifiez le nom de l'application (ex: Chrome, Notepad)")
            elif slot == "text":
                suggestions.append("Précisez le texte à utiliser")
            elif slot == "query":
                suggestions.append("Indiquez votre requête de recherche")
            elif slot == "content":
                suggestions.append("Spécifiez le contenu du fichier")
        
        return suggestions
    
    def _get_parameter_suggestions(self, intent_type, slot: str) -> List[str]:
        """Génère des suggestions de paramètres."""
        if slot == "app_name":
            return ["Google Chrome", "Notepad", "Calculator", "File Explorer"]
        elif slot == "text":
            return ["OK", "Cancel", "Save", "Open"]
        elif slot == "query":
            return ["weather", "news", "tutorials"]
        
        return []
    
    def _find_similar_plans(self, intent: Intent) -> List[Plan]:
        """Trouve des plans similaires dans le cache."""
        similar = []
        
        for plan in self._plan_cache.values():
            if plan.intent.type == intent.type:
                similar.append(plan)
        
        return similar[:5]  # Limiter à 5 résultats
    
    def _estimate_success_probability(self, intent: Intent) -> float:
        """Estime la probabilité de succès d'une intention."""
        base_probability = 0.8  # Probabilité de base
        
        # Ajuster selon la confiance
        confidence_factor = intent.confidence
        
        # Ajuster selon la complexité
        complexity_factor = 1.0
        if intent.type.value in ["web_search", "write_text_file"]:
            complexity_factor = 0.9
        
        return min(base_probability * confidence_factor * complexity_factor, 1.0)