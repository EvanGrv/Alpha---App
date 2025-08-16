"""
Système de guardrails pour Desktop Agent.

Fournit des vérifications de sécurité et des validations avant exécution.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from ..common.config import get_settings
from ..common.errors import SecurityError, UnsafeOperationError
from ..common.logging_utils import get_planner_logger
from ..common.models import Intent, IntentType, Plan

logger = get_planner_logger()


class GuardrailRule:
    """Règle de guardrail."""
    
    def __init__(
        self,
        name: str,
        description: str,
        severity: str = "warning",  # "info", "warning", "error", "critical"
        applies_to: Optional[List[IntentType]] = None
    ):
        self.name = name
        self.description = description
        self.severity = severity
        self.applies_to = applies_to or []
    
    def check(self, plan: Plan, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Vérifie la règle sur un plan.
        
        Args:
            plan: Plan à vérifier
            context: Contexte d'exécution
            
        Returns:
            Résultat de la vérification
        """
        return {
            "passed": True,
            "message": "",
            "details": {}
        }


class PathSecurityRule(GuardrailRule):
    """Règle de sécurité pour les chemins de fichiers."""
    
    def __init__(self):
        super().__init__(
            name="path_security",
            description="Vérifie la sécurité des chemins de fichiers",
            severity="error",
            applies_to=[IntentType.SAVE_FILE, IntentType.WRITE_TEXT_FILE]
        )
        self.settings = get_settings()
    
    def check(self, plan: Plan, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Vérifie la sécurité des chemins."""
        if plan.intent.type not in self.applies_to:
            return {"passed": True, "message": "Règle non applicable"}
        
        path = plan.intent.slots.get("path")
        if not path:
            return {"passed": True, "message": "Aucun chemin spécifié"}
        
        try:
            path_obj = Path(path).resolve()
            
            # Vérifier les chemins interdits
            forbidden_paths = [
                Path("C:/Windows"),
                Path("C:/Program Files"),
                Path("C:/Program Files (x86)"),
                Path("/System"),
                Path("/usr"),
                Path("/etc"),
                Path("/bin"),
                Path("/sbin")
            ]
            
            for forbidden in forbidden_paths:
                try:
                    path_obj.relative_to(forbidden.resolve())
                    return {
                        "passed": False,
                        "message": f"Écriture interdite dans {forbidden}",
                        "details": {"forbidden_path": str(forbidden)}
                    }
                except (ValueError, OSError):
                    continue
            
            # Vérifier les chemins autorisés
            allowed_paths = [
                Path(p).expanduser().resolve() 
                for p in self.settings.security.allowed_write_paths
            ]
            
            is_allowed = any(
                str(path_obj).startswith(str(allowed))
                for allowed in allowed_paths
            )
            
            if not is_allowed:
                return {
                    "passed": False,
                    "message": f"Chemin {path} non autorisé pour l'écriture",
                    "details": {
                        "path": str(path_obj),
                        "allowed_paths": [str(p) for p in allowed_paths]
                    }
                }
            
            return {"passed": True, "message": "Chemin autorisé"}
            
        except Exception as e:
            return {
                "passed": False,
                "message": f"Erreur validation chemin: {e}",
                "details": {"error": str(e)}
            }


class ApplicationSecurityRule(GuardrailRule):
    """Règle de sécurité pour les applications."""
    
    def __init__(self):
        super().__init__(
            name="application_security",
            description="Vérifie la sécurité des applications à lancer",
            severity="error",
            applies_to=[IntentType.OPEN_APP, IntentType.FOCUS_APP]
        )
        self.settings = get_settings()
    
    def check(self, plan: Plan, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Vérifie la sécurité des applications."""
        if plan.intent.type not in self.applies_to:
            return {"passed": True, "message": "Règle non applicable"}
        
        app_name = plan.intent.slots.get("app_name", "").lower()
        if not app_name:
            return {"passed": True, "message": "Aucune application spécifiée"}
        
        # Vérifier les applications bloquées
        blocked_apps = [app.lower() for app in self.settings.security.blocked_apps]
        
        for blocked in blocked_apps:
            if blocked in app_name:
                return {
                    "passed": False,
                    "message": f"Application '{app_name}' bloquée par la sécurité",
                    "details": {"blocked_app": blocked}
                }
        
        # Vérifier les applications système critiques
        critical_apps = [
            "regedit", "registry editor",
            "services.msc", "services",
            "msconfig", "system configuration",
            "gpedit.msc", "group policy",
            "secpol.msc", "security policy"
        ]
        
        for critical in critical_apps:
            if critical in app_name:
                return {
                    "passed": False,
                    "message": f"Application système critique '{app_name}' interdite",
                    "details": {"critical_app": critical}
                }
        
        return {"passed": True, "message": "Application autorisée"}


class ContentSecurityRule(GuardrailRule):
    """Règle de sécurité pour le contenu."""
    
    def __init__(self):
        super().__init__(
            name="content_security",
            description="Vérifie la sécurité du contenu à saisir",
            severity="warning",
            applies_to=[IntentType.TYPE_TEXT, IntentType.WRITE_TEXT_FILE]
        )
    
    def check(self, plan: Plan, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Vérifie la sécurité du contenu."""
        if plan.intent.type not in self.applies_to:
            return {"passed": True, "message": "Règle non applicable"}
        
        # Récupérer le contenu
        content = ""
        if plan.intent.type == IntentType.TYPE_TEXT:
            content = plan.intent.slots.get("text", "")
        elif plan.intent.type == IntentType.WRITE_TEXT_FILE:
            content = plan.intent.slots.get("content", "")
        
        if not content:
            return {"passed": True, "message": "Aucun contenu à vérifier"}
        
        warnings = []
        
        # Détecter les informations sensibles
        sensitive_patterns = {
            "password": r"(?i)password\s*[:=]\s*\S+",
            "api_key": r"(?i)(?:api[_-]?key|token)\s*[:=]\s*[a-zA-Z0-9]+",
            "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            "credit_card": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
            "ssn": r"\b\d{3}-\d{2}-\d{4}\b"
        }
        
        for pattern_name, pattern in sensitive_patterns.items():
            if re.search(pattern, content):
                warnings.append(f"Contenu potentiellement sensible détecté: {pattern_name}")
        
        # Détecter les commandes système
        system_commands = [
            "rm -rf", "del /f", "format", "fdisk",
            "shutdown", "reboot", "halt",
            "sudo", "su -", "chmod 777"
        ]
        
        content_lower = content.lower()
        for command in system_commands:
            if command in content_lower:
                warnings.append(f"Commande système potentiellement dangereuse: {command}")
        
        if warnings:
            return {
                "passed": False,
                "message": "Contenu potentiellement sensible ou dangereux détecté",
                "details": {"warnings": warnings}
            }
        
        return {"passed": True, "message": "Contenu sécurisé"}


class RateLimitRule(GuardrailRule):
    """Règle de limitation de taux."""
    
    def __init__(self):
        super().__init__(
            name="rate_limit",
            description="Vérifie les limites de taux d'exécution",
            severity="warning"
        )
        self.execution_history: List[float] = []
        self.max_executions_per_minute = 10
    
    def check(self, plan: Plan, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Vérifie les limites de taux."""
        import time
        
        current_time = time.time()
        
        # Nettoyer l'historique (garder seulement la dernière minute)
        self.execution_history = [
            timestamp for timestamp in self.execution_history
            if current_time - timestamp < 60
        ]
        
        # Vérifier la limite
        if len(self.execution_history) >= self.max_executions_per_minute:
            return {
                "passed": False,
                "message": f"Limite de taux dépassée: {len(self.execution_history)} exécutions dans la dernière minute",
                "details": {
                    "current_count": len(self.execution_history),
                    "limit": self.max_executions_per_minute
                }
            }
        
        # Ajouter l'exécution actuelle
        self.execution_history.append(current_time)
        
        return {"passed": True, "message": "Limite de taux respectée"}


class GuardrailsEngine:
    """Moteur de guardrails principal."""
    
    def __init__(self):
        self.settings = get_settings()
        self._rules: List[GuardrailRule] = []
        self._initialize_rules()
        
        logger.info(f"Moteur guardrails initialisé avec {len(self._rules)} règles")
    
    def _initialize_rules(self) -> None:
        """Initialise les règles de guardrails."""
        self._rules = [
            PathSecurityRule(),
            ApplicationSecurityRule(),
            ContentSecurityRule(),
            RateLimitRule()
        ]
    
    def check_plan(self, plan: Plan, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Vérifie un plan contre tous les guardrails.
        
        Args:
            plan: Plan à vérifier
            context: Contexte d'exécution
            
        Returns:
            Résultat complet des vérifications
        """
        try:
            logger.info(f"Vérification guardrails pour plan {plan.id}")
            
            results = {
                "overall_passed": True,
                "can_execute": True,
                "requires_confirmation": plan.requires_confirmation,
                "rule_results": [],
                "errors": [],
                "warnings": [],
                "info": []
            }
            
            # Vérifier chaque règle applicable
            for rule in self._rules:
                if self._is_rule_applicable(rule, plan):
                    try:
                        rule_result = rule.check(plan, context)
                        
                        rule_info = {
                            "rule_name": rule.name,
                            "description": rule.description,
                            "severity": rule.severity,
                            "passed": rule_result["passed"],
                            "message": rule_result["message"],
                            "details": rule_result.get("details", {})
                        }
                        
                        results["rule_results"].append(rule_info)
                        
                        # Catégoriser le résultat
                        if not rule_result["passed"]:
                            if rule.severity in ["error", "critical"]:
                                results["errors"].append(rule_info)
                                results["overall_passed"] = False
                                if rule.severity == "critical":
                                    results["can_execute"] = False
                            elif rule.severity == "warning":
                                results["warnings"].append(rule_info)
                                results["requires_confirmation"] = True
                            else:
                                results["info"].append(rule_info)
                        
                    except Exception as e:
                        logger.error(f"Erreur vérification règle {rule.name}: {e}")
                        error_info = {
                            "rule_name": rule.name,
                            "severity": "error",
                            "passed": False,
                            "message": f"Erreur vérification: {e}",
                            "details": {"exception": str(e)}
                        }
                        results["rule_results"].append(error_info)
                        results["errors"].append(error_info)
                        results["overall_passed"] = False
            
            # Résumé final
            logger.info(
                f"Guardrails: {'PASSÉ' if results['overall_passed'] else 'ÉCHOUÉ'}",
                errors=len(results["errors"]),
                warnings=len(results["warnings"]),
                can_execute=results["can_execute"]
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Erreur moteur guardrails: {e}")
            return {
                "overall_passed": False,
                "can_execute": False,
                "requires_confirmation": True,
                "rule_results": [],
                "errors": [{"message": f"Erreur moteur guardrails: {e}"}],
                "warnings": [],
                "info": []
            }
    
    def _is_rule_applicable(self, rule: GuardrailRule, plan: Plan) -> bool:
        """Vérifie si une règle s'applique à un plan."""
        if not rule.applies_to:
            return True  # Règle universelle
        
        return plan.intent.type in rule.applies_to
    
    def add_custom_rule(self, rule: GuardrailRule) -> None:
        """
        Ajoute une règle personnalisée.
        
        Args:
            rule: Règle à ajouter
        """
        self._rules.append(rule)
        logger.info(f"Règle personnalisée ajoutée: {rule.name}")
    
    def remove_rule(self, rule_name: str) -> bool:
        """
        Supprime une règle par nom.
        
        Args:
            rule_name: Nom de la règle à supprimer
            
        Returns:
            True si la règle a été supprimée
        """
        initial_count = len(self._rules)
        self._rules = [rule for rule in self._rules if rule.name != rule_name]
        
        removed = len(self._rules) < initial_count
        if removed:
            logger.info(f"Règle supprimée: {rule_name}")
        
        return removed
    
    def get_rules_info(self) -> List[Dict[str, Any]]:
        """
        Retourne les informations sur toutes les règles.
        
        Returns:
            Liste des informations de règles
        """
        return [
            {
                "name": rule.name,
                "description": rule.description,
                "severity": rule.severity,
                "applies_to": [intent.value for intent in rule.applies_to] if rule.applies_to else ["all"]
            }
            for rule in self._rules
        ]
    
    def simulate_check(self, intent: Intent, slots: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simule une vérification sans créer un plan complet.
        
        Args:
            intent: Intention à vérifier
            slots: Slots normalisés
            
        Returns:
            Résultat de simulation
        """
        # Créer un plan minimal pour la simulation
        from ..common.models import Plan, Action
        
        dummy_plan = Plan(
            intent=intent,
            actions=[],  # Plan vide pour simulation
            summary="Simulation",
            requires_confirmation=False,
            estimated_duration=0.0,
            risk_level="low"
        )
        
        # Mettre à jour les slots
        dummy_plan.intent.slots.update(slots)
        
        return self.check_plan(dummy_plan)
    
    def get_security_summary(self) -> Dict[str, Any]:
        """
        Retourne un résumé de la configuration de sécurité.
        
        Returns:
            Résumé de sécurité
        """
        return {
            "active_rules": len(self._rules),
            "security_config": {
                "require_confirmation_for_write": self.settings.security.require_confirmation_for_write,
                "require_confirmation_for_delete": self.settings.security.require_confirmation_for_delete,
                "allowed_write_paths": self.settings.security.allowed_write_paths,
                "blocked_apps": self.settings.security.blocked_apps,
                "max_execution_time": self.settings.security.max_execution_time
            },
            "rules_by_severity": {
                severity: len([r for r in self._rules if r.severity == severity])
                for severity in ["info", "warning", "error", "critical"]
            }
        }