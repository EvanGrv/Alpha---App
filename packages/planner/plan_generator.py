"""
Générateur de plans pour Desktop Agent.

Convertit les intentions en séquences d'actions exécutables.
"""

from typing import Any, Dict, List, Optional
from uuid import uuid4

from ..common.config import get_settings
from ..common.errors import PlanGenerationError, PlannerError
from ..common.logging_utils import get_planner_logger
from ..common.models import Action, ActionType, Intent, IntentType, Plan
from ..skills import SkillManager

logger = get_planner_logger()


class PlanTemplate:
    """Template pour générer un plan à partir d'une intention."""
    
    def __init__(
        self,
        intent_type: IntentType,
        actions: List[Dict[str, Any]],
        requires_confirmation: bool = False,
        estimated_duration: float = 5.0,
        risk_level: str = "low"
    ):
        self.intent_type = intent_type
        self.actions = actions
        self.requires_confirmation = requires_confirmation
        self.estimated_duration = estimated_duration
        self.risk_level = risk_level


class PlanGenerator:
    """Générateur de plans d'exécution."""
    
    def __init__(self, skill_manager: SkillManager):
        self.settings = get_settings()
        self.skill_manager = skill_manager
        self._templates = self._initialize_templates()
        
        logger.info("Générateur de plans initialisé")
    
    def _initialize_templates(self) -> Dict[IntentType, PlanTemplate]:
        """Initialise les templates de plans."""
        templates = {}
        
        # Template pour ouvrir une application
        templates[IntentType.OPEN_APP] = PlanTemplate(
            intent_type=IntentType.OPEN_APP,
            actions=[
                {
                    "type": ActionType.SCREENSHOT,
                    "description": "Capture d'état initial"
                },
                {
                    "skill": "open_app",
                    "description": "Ouverture de l'application {app_name}"
                },
                {
                    "type": ActionType.WAIT,
                    "parameters": {"duration": 2.0},
                    "description": "Attente du lancement de l'application"
                }
            ],
            estimated_duration=5.0,
            risk_level="low"
        )
        
        # Template pour mettre le focus
        templates[IntentType.FOCUS_APP] = PlanTemplate(
            intent_type=IntentType.FOCUS_APP,
            actions=[
                {
                    "skill": "focus_app",
                    "description": "Focus sur l'application {app_name}"
                }
            ],
            estimated_duration=2.0,
            risk_level="low"
        )
        
        # Template pour cliquer sur du texte
        templates[IntentType.CLICK_TEXT] = PlanTemplate(
            intent_type=IntentType.CLICK_TEXT,
            actions=[
                {
                    "type": ActionType.SCREENSHOT,
                    "description": "Capture pour localiser le texte"
                },
                {
                    "skill": "click_text",
                    "description": "Clic sur '{text}'"
                }
            ],
            estimated_duration=3.0,
            risk_level="low"
        )
        
        # Template pour saisir du texte
        templates[IntentType.TYPE_TEXT] = PlanTemplate(
            intent_type=IntentType.TYPE_TEXT,
            actions=[
                {
                    "skill": "type_text",
                    "description": "Saisie du texte"
                }
            ],
            estimated_duration=2.0,
            risk_level="low"
        )
        
        # Template pour sauvegarder un fichier
        templates[IntentType.SAVE_FILE] = PlanTemplate(
            intent_type=IntentType.SAVE_FILE,
            actions=[
                {
                    "skill": "save_file",
                    "description": "Sauvegarde du fichier"
                }
            ],
            estimated_duration=3.0,
            risk_level="medium",
            requires_confirmation=True
        )
        
        # Template pour recherche web
        templates[IntentType.WEB_SEARCH] = PlanTemplate(
            intent_type=IntentType.WEB_SEARCH,
            actions=[
                {
                    "skill": "open_app",
                    "parameters": {"app_name": "Google Chrome"},
                    "description": "Ouverture du navigateur"
                },
                {
                    "type": ActionType.WAIT,
                    "parameters": {"duration": 3.0},
                    "description": "Attente du chargement du navigateur"
                },
                {
                    "skill": "click_text",
                    "parameters": {"text": "address bar", "fuzzy": True},
                    "description": "Clic sur la barre d'adresse"
                },
                {
                    "skill": "type_text",
                    "parameters": {"text": "https://www.google.com/search?q={query}"},
                    "description": "Saisie de l'URL de recherche"
                },
                {
                    "type": ActionType.KEY_PRESS,
                    "parameters": {"key": "enter"},
                    "description": "Validation de la recherche"
                }
            ],
            estimated_duration=8.0,
            risk_level="low"
        )
        
        # Template pour créer un fichier texte
        templates[IntentType.WRITE_TEXT_FILE] = PlanTemplate(
            intent_type=IntentType.WRITE_TEXT_FILE,
            actions=[
                {
                    "skill": "write_text_file",
                    "description": "Création et écriture du fichier texte"
                }
            ],
            estimated_duration=5.0,
            risk_level="medium",
            requires_confirmation=True
        )
        
        return templates
    
    def generate_plan(self, intent: Intent, context: Optional[Dict[str, Any]] = None) -> Plan:
        """
        Génère un plan d'exécution à partir d'une intention.
        
        Args:
            intent: Intention à planifier
            context: Contexte d'exécution optionnel
            
        Returns:
            Plan d'exécution
            
        Raises:
            PlanGenerationError: Si le plan ne peut pas être généré
        """
        try:
            logger.info(f"Génération plan pour intention: {intent.type.value}")
            
            # Récupérer le template approprié
            template = self._templates.get(intent.type)
            if not template:
                raise PlanGenerationError(f"Pas de template pour {intent.type.value}")
            
            # Générer les actions à partir du template
            actions = self._generate_actions_from_template(template, intent.slots, context)
            
            # Créer le résumé du plan
            summary = self._generate_plan_summary(intent, actions)
            
            # Déterminer si confirmation nécessaire
            requires_confirmation = self._should_require_confirmation(template, intent.slots)
            
            # Ajuster la durée estimée
            estimated_duration = self._estimate_duration(template, intent.slots)
            
            # Créer le plan
            plan = Plan(
                intent=intent,
                actions=actions,
                summary=summary,
                requires_confirmation=requires_confirmation,
                estimated_duration=estimated_duration,
                risk_level=template.risk_level
            )
            
            logger.info(
                f"Plan généré: {len(actions)} actions, durée estimée: {estimated_duration:.1f}s",
                actions_count=len(actions),
                estimated_duration=estimated_duration,
                requires_confirmation=requires_confirmation
            )
            
            return plan
            
        except Exception as e:
            logger.error(f"Erreur génération plan pour {intent.type.value}: {e}")
            raise PlanGenerationError(f"Erreur génération plan: {e}")
    
    def _generate_actions_from_template(
        self,
        template: PlanTemplate,
        slots: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> List[Action]:
        """Génère les actions à partir d'un template."""
        actions = []
        
        for i, action_def in enumerate(template.actions):
            try:
                # Substituer les paramètres avec les slots
                processed_action = self._process_action_definition(action_def, slots, context)
                
                # Créer l'objet Action
                if "skill" in processed_action:
                    # Action basée sur une compétence
                    action = Action(
                        type=ActionType.SCREENSHOT,  # Placeholder, sera déterminé par le skill
                        parameters={
                            "skill_name": processed_action["skill"],
                            "skill_parameters": processed_action.get("parameters", {})
                        },
                        description=processed_action["description"]
                    )
                else:
                    # Action primitive
                    action = Action(
                        type=ActionType(processed_action["type"]),
                        parameters=processed_action.get("parameters", {}),
                        description=processed_action["description"]
                    )
                
                actions.append(action)
                
            except Exception as e:
                logger.warning(f"Erreur traitement action {i}: {e}")
                continue
        
        return actions
    
    def _process_action_definition(
        self,
        action_def: Dict[str, Any],
        slots: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Traite une définition d'action en substituant les paramètres."""
        processed = action_def.copy()
        
        # Substituer dans la description
        if "description" in processed:
            description = processed["description"]
            for key, value in slots.items():
                placeholder = f"{{{key}}}"
                if placeholder in description:
                    description = description.replace(placeholder, str(value))
            processed["description"] = description
        
        # Substituer dans les paramètres
        if "parameters" in processed:
            parameters = processed["parameters"].copy()
            for param_key, param_value in parameters.items():
                if isinstance(param_value, str):
                    for slot_key, slot_value in slots.items():
                        placeholder = f"{{{slot_key}}}"
                        if placeholder in param_value:
                            param_value = param_value.replace(placeholder, str(slot_value))
                    parameters[param_key] = param_value
            processed["parameters"] = parameters
        
        # Ajouter les slots comme paramètres si c'est une compétence
        if "skill" in processed:
            if "parameters" not in processed:
                processed["parameters"] = {}
            
            # Mapper les slots aux paramètres de compétence
            skill_name = processed["skill"]
            skill_info = self.skill_manager.get_skill_info(skill_name)
            
            if skill_info:
                # Ajouter les slots pertinents
                for slot_key, slot_value in slots.items():
                    processed["parameters"][slot_key] = slot_value
        
        return processed
    
    def _generate_plan_summary(self, intent: Intent, actions: List[Action]) -> str:
        """Génère un résumé lisible du plan."""
        summaries = {
            IntentType.OPEN_APP: f"Ouvrir l'application {intent.slots.get('app_name', 'inconnue')}",
            IntentType.FOCUS_APP: f"Mettre le focus sur {intent.slots.get('app_name', 'inconnue')}",
            IntentType.CLICK_TEXT: f"Cliquer sur '{intent.slots.get('text', 'texte')}'",
            IntentType.TYPE_TEXT: f"Saisir le texte: {intent.slots.get('text', '')[:50]}...",
            IntentType.SAVE_FILE: "Sauvegarder le fichier actuel",
            IntentType.WEB_SEARCH: f"Rechercher '{intent.slots.get('query', 'requête')}' sur Google",
            IntentType.WRITE_TEXT_FILE: f"Créer un fichier texte avec le contenu spécifié"
        }
        
        base_summary = summaries.get(intent.type, f"Exécuter {intent.type.value}")
        
        # Ajouter le nombre d'étapes
        if len(actions) > 1:
            base_summary += f" (en {len(actions)} étapes)"
        
        return base_summary
    
    def _should_require_confirmation(self, template: PlanTemplate, slots: Dict[str, Any]) -> bool:
        """Détermine si le plan nécessite une confirmation."""
        # Confirmation basée sur le template
        if template.requires_confirmation:
            return True
        
        # Confirmation basée sur la configuration de sécurité
        security_config = self.settings.security
        
        # Vérifier les opérations d'écriture
        if template.intent_type in [IntentType.SAVE_FILE, IntentType.WRITE_TEXT_FILE]:
            if security_config.require_confirmation_for_write:
                return True
            
            # Vérifier le chemin de destination
            path = slots.get("path", "")
            if path:
                # Confirmation si écriture hors des chemins autorisés
                from pathlib import Path
                try:
                    path_obj = Path(path).resolve()
                    allowed_paths = [Path(p).expanduser().resolve() for p in security_config.allowed_write_paths]
                    
                    is_allowed = any(
                        str(path_obj).startswith(str(allowed_path))
                        for allowed_path in allowed_paths
                    )
                    
                    if not is_allowed:
                        return True
                        
                except Exception:
                    # En cas d'erreur de chemin, demander confirmation
                    return True
        
        return False
    
    def _estimate_duration(self, template: PlanTemplate, slots: Dict[str, Any]) -> float:
        """Estime la durée d'exécution du plan."""
        base_duration = template.estimated_duration
        
        # Ajustements selon les slots
        if template.intent_type == IntentType.TYPE_TEXT:
            text = slots.get("text", "")
            # Ajouter du temps proportionnel à la longueur du texte
            base_duration += len(text) * 0.01  # 10ms par caractère
        
        elif template.intent_type == IntentType.WRITE_TEXT_FILE:
            content = slots.get("content", "")
            base_duration += len(content) * 0.01
            
            # Temps supplémentaire si sauvegarde
            if slots.get("path"):
                base_duration += 2.0
        
        return base_duration
    
    def optimize_plan(self, plan: Plan, context: Optional[Dict[str, Any]] = None) -> Plan:
        """
        Optimise un plan existant.
        
        Args:
            plan: Plan à optimiser
            context: Contexte d'optimisation
            
        Returns:
            Plan optimisé
        """
        try:
            optimized_actions = []
            
            # Supprimer les actions redondantes
            for action in plan.actions:
                # Éviter les captures d'écran consécutives
                if (action.type == ActionType.SCREENSHOT and 
                    optimized_actions and 
                    optimized_actions[-1].type == ActionType.SCREENSHOT):
                    continue
                
                optimized_actions.append(action)
            
            # Fusionner les actions de même type si possible
            merged_actions = self._merge_similar_actions(optimized_actions)
            
            # Créer le plan optimisé
            optimized_plan = Plan(
                id=plan.id,
                intent=plan.intent,
                actions=merged_actions,
                summary=plan.summary,
                requires_confirmation=plan.requires_confirmation,
                estimated_duration=self._recalculate_duration(merged_actions),
                risk_level=plan.risk_level
            )
            
            logger.info(
                f"Plan optimisé: {len(plan.actions)} -> {len(merged_actions)} actions",
                original_count=len(plan.actions),
                optimized_count=len(merged_actions)
            )
            
            return optimized_plan
            
        except Exception as e:
            logger.warning(f"Erreur optimisation plan: {e}")
            return plan
    
    def _merge_similar_actions(self, actions: List[Action]) -> List[Action]:
        """Fusionne les actions similaires."""
        if len(actions) <= 1:
            return actions
        
        merged = []
        i = 0
        
        while i < len(actions):
            current_action = actions[i]
            
            # Chercher des actions similaires consécutives
            if (i + 1 < len(actions) and 
                current_action.type == ActionType.TYPE_TEXT and
                actions[i + 1].type == ActionType.TYPE_TEXT):
                
                # Fusionner les actions de saisie de texte
                combined_text = (
                    current_action.parameters.get("text", "") + 
                    actions[i + 1].parameters.get("text", "")
                )
                
                merged_action = Action(
                    type=ActionType.TYPE_TEXT,
                    parameters={"text": combined_text},
                    description=f"Saisie combinée de texte ({len(combined_text)} caractères)"
                )
                
                merged.append(merged_action)
                i += 2  # Ignorer l'action suivante
            else:
                merged.append(current_action)
                i += 1
        
        return merged
    
    def _recalculate_duration(self, actions: List[Action]) -> float:
        """Recalcule la durée estimée d'une liste d'actions."""
        total_duration = 0.0
        
        for action in actions:
            if action.type == ActionType.WAIT:
                total_duration += action.parameters.get("duration", 1.0)
            elif action.type == ActionType.TYPE_TEXT:
                text = action.parameters.get("text", "")
                total_duration += max(1.0, len(text) * 0.01)
            else:
                total_duration += 1.0  # Durée par défaut
        
        return total_duration
    
    def validate_plan(self, plan: Plan) -> Dict[str, Any]:
        """
        Valide un plan avant exécution.
        
        Args:
            plan: Plan à valider
            
        Returns:
            Résultat de validation
        """
        validation = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        try:
            # Vérifier que le plan a des actions
            if not plan.actions:
                validation["errors"].append("Plan vide - aucune action définie")
                validation["valid"] = False
            
            # Vérifier chaque action
            for i, action in enumerate(plan.actions):
                action_validation = self._validate_action(action)
                
                if not action_validation["valid"]:
                    validation["errors"].extend([
                        f"Action {i}: {error}" for error in action_validation["errors"]
                    ])
                    validation["valid"] = False
                
                validation["warnings"].extend([
                    f"Action {i}: {warning}" for warning in action_validation["warnings"]
                ])
            
            # Vérifier la cohérence du plan
            coherence_check = self._check_plan_coherence(plan)
            validation["warnings"].extend(coherence_check)
            
            logger.debug(
                f"Validation plan: {'VALIDE' if validation['valid'] else 'INVALIDE'}",
                errors_count=len(validation["errors"]),
                warnings_count=len(validation["warnings"])
            )
            
        except Exception as e:
            validation["valid"] = False
            validation["errors"].append(f"Erreur validation: {e}")
        
        return validation
    
    def _validate_action(self, action: Action) -> Dict[str, Any]:
        """Valide une action individuelle."""
        validation = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        # Vérifier que l'action a une description
        if not action.description:
            validation["warnings"].append("Description d'action manquante")
        
        # Validation selon le type d'action
        if action.type == ActionType.TYPE_TEXT:
            text = action.parameters.get("text", "")
            if not text:
                validation["errors"].append("Texte à saisir manquant")
                validation["valid"] = False
        
        # Vérifier les compétences si applicable
        if "skill_name" in action.parameters:
            skill_name = action.parameters["skill_name"]
            skill = self.skill_manager.get_skill(skill_name)
            
            if not skill:
                validation["errors"].append(f"Compétence '{skill_name}' non trouvée")
                validation["valid"] = False
            else:
                # Valider les paramètres de la compétence
                skill_params = action.parameters.get("skill_parameters", {})
                if not skill.validate_parameters(skill_params):
                    validation["errors"].append(f"Paramètres invalides pour '{skill_name}'")
                    validation["valid"] = False
        
        return validation
    
    def _check_plan_coherence(self, plan: Plan) -> List[str]:
        """Vérifie la cohérence globale du plan."""
        warnings = []
        
        # Vérifier l'ordre logique des actions
        action_types = [action.type for action in plan.actions]
        
        # Avertir si sauvegarde sans saisie préalable
        if (ActionType.SCREENSHOT in action_types and 
            action_types.count(ActionType.SCREENSHOT) > 3):
            warnings.append("Nombreuses captures d'écran - plan potentiellement inefficace")
        
        return warnings