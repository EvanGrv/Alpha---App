"""
Gestionnaire NLU principal pour Desktop Agent.

Coordonne l'analyse d'intentions et l'extraction de slots.
"""

from typing import Any, Dict, List, Optional

from ..common.config import get_settings
from ..common.errors import NLUError
from ..common.logging_utils import get_nlu_logger
from ..common.models import Intent, IntentType
from .intent_parser import IntentParser
from .slot_extractor import SlotExtractor

logger = get_nlu_logger()


class NLUManager:
    """Gestionnaire principal des capacités NLU."""
    
    def __init__(self):
        self.settings = get_settings()
        
        # Initialiser les composants
        self.intent_parser = IntentParser()
        self.slot_extractor = SlotExtractor()
        
        # Statistiques
        self._processed_count = 0
        self._success_count = 0
        self._intent_stats = {}
        
        logger.info("Gestionnaire NLU initialisé")
    
    def understand(self, text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Analyse complète du langage naturel.
        
        Args:
            text: Texte à analyser
            context: Contexte optionnel (état de l'application, etc.)
            
        Returns:
            Résultat complet de l'analyse NLU
        """
        try:
            self._processed_count += 1
            
            logger.info(f"Analyse NLU: '{text}'")
            
            # Étape 1: Analyse d'intention
            intent = self.intent_parser.parse_intent(text)
            
            # Étape 2: Extraction et normalisation des slots
            normalized_slots = self.slot_extractor.extract_and_normalize_slots(intent)
            
            # Étape 3: Validation des slots
            validation = self.slot_extractor.validate_slots(intent.type, normalized_slots)
            
            # Étape 4: Enrichissement contextuel
            enriched_result = self._enrich_with_context(intent, normalized_slots, context)
            
            # Étape 5: Suggestions si nécessaire
            suggestions = self._get_completion_suggestions(intent, normalized_slots)
            
            # Construire le résultat final
            result = {
                "intent": {
                    "type": intent.type.value,
                    "confidence": intent.confidence,
                    "original_text": intent.original_text,
                    "normalized_text": intent.normalized_text
                },
                "slots": normalized_slots,
                "validation": validation,
                "suggestions": suggestions,
                "context_enrichment": enriched_result,
                "ready_for_execution": validation["valid"] and intent.confidence > 0.5
            }
            
            # Mettre à jour les statistiques
            self._update_stats(intent.type, validation["valid"])
            
            if result["ready_for_execution"]:
                self._success_count += 1
                logger.info(
                    f"NLU réussi: {intent.type.value} (confiance: {intent.confidence:.2f})",
                    intent_type=intent.type.value,
                    confidence=intent.confidence,
                    slots_count=len(normalized_slots)
                )
            else:
                logger.warning(
                    f"NLU incomplet: {intent.type.value}",
                    validation_errors=validation.get("errors", []),
                    confidence=intent.confidence
                )
            
            return result
            
        except Exception as e:
            logger.error(f"Erreur analyse NLU '{text}': {e}")
            raise NLUError(f"Erreur NLU: {e}")
    
    def get_intent_suggestions(self, text: str, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Retourne plusieurs suggestions d'intentions possibles.
        
        Args:
            text: Texte à analyser
            limit: Nombre maximum de suggestions
            
        Returns:
            Liste des suggestions d'intentions
        """
        try:
            intent_suggestions = self.intent_parser.get_intent_suggestions(text, limit)
            
            suggestions = []
            for intent in intent_suggestions:
                normalized_slots = self.slot_extractor.extract_and_normalize_slots(intent)
                validation = self.slot_extractor.validate_slots(intent.type, normalized_slots)
                
                suggestions.append({
                    "intent_type": intent.type.value,
                    "confidence": intent.confidence,
                    "slots": normalized_slots,
                    "valid": validation["valid"],
                    "description": self._get_intent_description(intent.type)
                })
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Erreur suggestions intentions '{text}': {e}")
            return []
    
    def complete_intent(self, partial_text: str, intent_type: IntentType) -> Dict[str, Any]:
        """
        Aide à compléter une intention partiellement exprimée.
        
        Args:
            partial_text: Texte partiel
            intent_type: Type d'intention ciblé
            
        Returns:
            Suggestions de complétion
        """
        try:
            # Analyser ce qui est déjà présent
            intent = self.intent_parser.parse_intent(partial_text)
            partial_slots = self.slot_extractor.extract_and_normalize_slots(intent)
            
            # Obtenir les suggestions de slots manquants
            slot_suggestions = self.slot_extractor.get_slot_suggestions(intent_type, partial_slots)
            
            # Générer des exemples complets
            examples = self._generate_completion_examples(intent_type, partial_slots)
            
            return {
                "current_slots": partial_slots,
                "missing_slots": slot_suggestions,
                "completion_examples": examples,
                "intent_description": self._get_intent_description(intent_type)
            }
            
        except Exception as e:
            logger.error(f"Erreur complétion intention: {e}")
            return {}
    
    def validate_command(self, text: str) -> Dict[str, Any]:
        """
        Valide une commande avant exécution.
        
        Args:
            text: Commande à valider
            
        Returns:
            Résultat de validation détaillé
        """
        try:
            # Analyse complète
            nlu_result = self.understand(text)
            
            # Vérifications de sécurité supplémentaires
            security_check = self._perform_security_checks(nlu_result)
            
            return {
                "nlu_result": nlu_result,
                "security_check": security_check,
                "safe_to_execute": (
                    nlu_result["ready_for_execution"] and 
                    security_check["safe"]
                ),
                "execution_plan": self._generate_execution_plan(nlu_result) if nlu_result["ready_for_execution"] else None
            }
            
        except Exception as e:
            logger.error(f"Erreur validation commande '{text}': {e}")
            return {
                "safe_to_execute": False,
                "error": str(e)
            }
    
    def get_supported_commands(self) -> List[Dict[str, Any]]:
        """
        Retourne la liste des commandes supportées.
        
        Returns:
            Liste des commandes avec exemples
        """
        intents_info = self.intent_parser.get_supported_intents()
        
        commands = []
        for intent_info in intents_info:
            commands.append({
                "intent_type": intent_info["type"],
                "description": self._get_intent_description(IntentType(intent_info["type"])),
                "keywords": intent_info["keywords"],
                "examples": intent_info["examples"],
                "required_parameters": intent_info["required_slots"]
            })
        
        return commands
    
    def get_nlu_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques NLU.
        
        Returns:
            Statistiques détaillées
        """
        return {
            "processed_count": self._processed_count,
            "success_count": self._success_count,
            "success_rate": self._success_count / self._processed_count if self._processed_count > 0 else 0.0,
            "intent_distribution": self._intent_stats,
            "supported_intents": len(self.intent_parser.get_supported_intents())
        }
    
    def reset_stats(self) -> None:
        """Remet à zéro les statistiques."""
        self._processed_count = 0
        self._success_count = 0
        self._intent_stats = {}
        logger.info("Statistiques NLU remises à zéro")
    
    # Méthodes privées
    
    def _enrich_with_context(
        self,
        intent: Intent,
        slots: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Enrichit le résultat avec le contexte."""
        enrichment = {}
        
        if not context:
            return enrichment
        
        # Enrichissement selon le type d'intention
        if intent.type in [IntentType.OPEN_APP, IntentType.FOCUS_APP]:
            # Vérifier si l'app est déjà ouverte
            running_apps = context.get("running_apps", [])
            app_name = slots.get("app_name", "")
            
            is_running = any(
                app_name.lower() in app.get("name", "").lower()
                for app in running_apps
            )
            
            enrichment["app_already_running"] = is_running
            if is_running and intent.type == IntentType.OPEN_APP:
                enrichment["suggestion"] = "L'application est déjà ouverte. Voulez-vous la mettre au premier plan?"
        
        elif intent.type == IntentType.SAVE_FILE:
            # Vérifier l'application active
            active_app = context.get("active_window", {}).get("name", "")
            enrichment["active_app"] = active_app
            
            # Suggérer un chemin basé sur l'app active
            if "notepad" in active_app.lower():
                enrichment["suggested_extension"] = ".txt"
            elif "word" in active_app.lower():
                enrichment["suggested_extension"] = ".docx"
        
        return enrichment
    
    def _get_completion_suggestions(self, intent: Intent, slots: Dict[str, Any]) -> Dict[str, Any]:
        """Génère des suggestions de complétion."""
        suggestions = {}
        
        # Suggestions selon le type d'intention
        if intent.type == IntentType.WRITE_TEXT_FILE:
            if "content" in slots and not slots.get("path"):
                suggestions["save_location"] = [
                    "Documents",
                    "Bureau", 
                    "Téléchargements"
                ]
                suggestions["filename"] = slots.get("default_filename", "nouveau_fichier.txt")
        
        elif intent.type == IntentType.WEB_SEARCH:
            query = slots.get("query", "")
            if len(query.split()) == 1:  # Un seul mot
                suggestions["search_type"] = [
                    f"définition de {query}",
                    f"tutoriel {query}",
                    f"{query} en français"
                ]
        
        return suggestions
    
    def _perform_security_checks(self, nlu_result: Dict[str, Any]) -> Dict[str, Any]:
        """Effectue des vérifications de sécurité."""
        security_result = {
            "safe": True,
            "warnings": [],
            "blocked_reasons": []
        }
        
        intent_type = nlu_result["intent"]["type"]
        slots = nlu_result["slots"]
        
        # Vérifications selon le type d'intention
        if intent_type == "save_file" or intent_type == "write_text_file":
            path = slots.get("path", "")
            if path:
                # Vérifier les chemins sensibles
                sensitive_paths = ["C:\\Windows", "C:\\Program Files", "/System", "/usr"]
                if any(sensitive in path for sensitive in sensitive_paths):
                    security_result["safe"] = False
                    security_result["blocked_reasons"].append("Écriture dans un répertoire système interdite")
        
        # Vérifier les applications bloquées
        if intent_type in ["open_app", "focus_app"]:
            app_name = slots.get("app_name", "").lower()
            blocked_apps = self.settings.security.blocked_apps
            if any(blocked in app_name for blocked in blocked_apps):
                security_result["safe"] = False
                security_result["blocked_reasons"].append(f"Application {app_name} bloquée par la sécurité")
        
        return security_result
    
    def _generate_execution_plan(self, nlu_result: Dict[str, Any]) -> Dict[str, Any]:
        """Génère un plan d'exécution."""
        intent_type = nlu_result["intent"]["type"]
        slots = nlu_result["slots"]
        
        plan = {
            "steps": [],
            "estimated_duration": 0.0,
            "requires_confirmation": False
        }
        
        # Plan selon le type d'intention
        if intent_type == "open_app":
            plan["steps"] = [
                {"action": "open_app", "parameters": {"app_name": slots["app_name"]}}
            ]
            plan["estimated_duration"] = 3.0
        
        elif intent_type == "click_text":
            plan["steps"] = [
                {"action": "find_text", "parameters": {"text": slots["text"]}},
                {"action": "click", "parameters": {"text": slots["text"]}}
            ]
            plan["estimated_duration"] = 2.0
        
        elif intent_type == "write_text_file":
            steps = [
                {"action": "open_app", "parameters": {"app_name": "notepad"}},
                {"action": "type_text", "parameters": {"text": slots["content"]}}
            ]
            
            if slots.get("path"):
                steps.append({"action": "save_file", "parameters": {"path": slots["path"]}})
                plan["requires_confirmation"] = True
            
            plan["steps"] = steps
            plan["estimated_duration"] = 5.0 + len(slots.get("content", "")) * 0.01
        
        return plan
    
    def _get_intent_description(self, intent_type: IntentType) -> str:
        """Retourne une description de l'intention."""
        descriptions = {
            IntentType.OPEN_APP: "Ouvre une application",
            IntentType.FOCUS_APP: "Met le focus sur une application",
            IntentType.CLICK_TEXT: "Clique sur du texte à l'écran",
            IntentType.TYPE_TEXT: "Saisit du texte",
            IntentType.SAVE_FILE: "Sauvegarde le fichier actuel",
            IntentType.WEB_SEARCH: "Effectue une recherche web",
            IntentType.WRITE_TEXT_FILE: "Crée un nouveau fichier texte",
            IntentType.UNKNOWN: "Intention non reconnue"
        }
        
        return descriptions.get(intent_type, "Description non disponible")
    
    def _generate_completion_examples(
        self,
        intent_type: IntentType,
        partial_slots: Dict[str, Any]
    ) -> List[str]:
        """Génère des exemples de complétion."""
        examples = []
        
        if intent_type == IntentType.OPEN_APP:
            if "app_name" not in partial_slots:
                examples = [
                    "Ouvre Google Chrome",
                    "Lance Notepad",
                    "Démarre Calculator"
                ]
        
        elif intent_type == IntentType.WRITE_TEXT_FILE:
            if "content" not in partial_slots:
                examples = [
                    "Crée un fichier et écris Bonjour monde",
                    "Nouveau fichier avec ma liste de courses",
                    "Crée un fichier texte avec mes notes"
                ]
        
        return examples
    
    def _update_stats(self, intent_type: IntentType, valid: bool) -> None:
        """Met à jour les statistiques."""
        intent_key = intent_type.value
        
        if intent_key not in self._intent_stats:
            self._intent_stats[intent_key] = {
                "count": 0,
                "valid_count": 0
            }
        
        self._intent_stats[intent_key]["count"] += 1
        if valid:
            self._intent_stats[intent_key]["valid_count"] += 1