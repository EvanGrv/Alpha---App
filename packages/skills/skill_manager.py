"""
Gestionnaire de compétences pour Desktop Agent.

Coordonne l'enregistrement, la découverte et l'exécution des compétences.
"""

import asyncio
import inspect
from typing import Any, Dict, List, Optional, Type

from .base_skill import BaseSkill, SkillParameters, SkillResult
from .app_skills import OpenAppSkill, FocusAppSkill, CloseAppSkill
from .interaction_skills import ClickTextSkill, TypeTextSkill, HotkeySkill
from .file_skills import SaveFileSkill, WriteTextFileSkill

from ..common.errors import SkillError
from ..common.logging_utils import get_skill_logger

logger = get_skill_logger("manager")


class SkillManager:
    """Gestionnaire central des compétences."""
    
    def __init__(self):
        self._skills: Dict[str, BaseSkill] = {}
        self._skill_classes: Dict[str, Type[BaseSkill]] = {}
        
        # Enregistrer les compétences de base
        self._register_builtin_skills()
        
        logger.info(f"Gestionnaire de compétences initialisé avec {len(self._skills)} compétences")
    
    def _register_builtin_skills(self) -> None:
        """Enregistre les compétences intégrées."""
        builtin_skills = [
            OpenAppSkill,
            FocusAppSkill,
            CloseAppSkill,
            ClickTextSkill,
            TypeTextSkill,
            HotkeySkill,
            SaveFileSkill,
            WriteTextFileSkill
        ]
        
        for skill_class in builtin_skills:
            self.register_skill_class(skill_class)
    
    def register_skill_class(self, skill_class: Type[BaseSkill]) -> None:
        """
        Enregistre une classe de compétence.
        
        Args:
            skill_class: Classe de compétence à enregistrer
        """
        try:
            # Instancier la compétence
            skill_instance = skill_class()
            skill_name = skill_instance.name
            
            # Enregistrer
            self._skills[skill_name] = skill_instance
            self._skill_classes[skill_name] = skill_class
            
            logger.info(f"Compétence enregistrée: {skill_name}")
            
        except Exception as e:
            logger.error(f"Erreur enregistrement compétence {skill_class.__name__}: {e}")
    
    def register_skill_instance(self, skill: BaseSkill) -> None:
        """
        Enregistre une instance de compétence.
        
        Args:
            skill: Instance de compétence à enregistrer
        """
        skill_name = skill.name
        self._skills[skill_name] = skill
        self._skill_classes[skill_name] = type(skill)
        
        logger.info(f"Instance de compétence enregistrée: {skill_name}")
    
    def get_skill(self, name: str) -> Optional[BaseSkill]:
        """
        Récupère une compétence par nom.
        
        Args:
            name: Nom de la compétence
            
        Returns:
            Instance de compétence ou None
        """
        return self._skills.get(name)
    
    def list_skills(self) -> List[str]:
        """
        Liste les noms de toutes les compétences enregistrées.
        
        Returns:
            Liste des noms de compétences
        """
        return list(self._skills.keys())
    
    def get_skill_info(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Récupère les informations détaillées d'une compétence.
        
        Args:
            name: Nom de la compétence
            
        Returns:
            Informations de la compétence ou None
        """
        skill = self._skills.get(name)
        if not skill:
            return None
        
        return {
            "name": skill.name,
            "description": skill.get_description(),
            "parameter_schema": skill.get_parameter_schema(),
            "examples": skill.get_examples(),
            "stats": skill.get_stats(),
            "class_name": type(skill).__name__
        }
    
    def get_all_skills_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Récupère les informations de toutes les compétences.
        
        Returns:
            Dictionnaire des informations de compétences
        """
        return {
            name: self.get_skill_info(name)
            for name in self._skills.keys()
        }
    
    async def execute_skill(
        self,
        name: str,
        parameters: Dict[str, Any],
        skill_params: Optional[SkillParameters] = None
    ) -> SkillResult:
        """
        Exécute une compétence.
        
        Args:
            name: Nom de la compétence
            parameters: Paramètres de la compétence
            skill_params: Paramètres d'exécution
            
        Returns:
            Résultat de l'exécution
            
        Raises:
            SkillError: Si la compétence n'existe pas ou échoue
        """
        skill = self._skills.get(name)
        if not skill:
            raise SkillError(f"Compétence '{name}' non trouvée")
        
        logger.info(f"Exécution compétence: {name}", parameters=parameters)
        
        try:
            result = await skill._execute_with_monitoring(parameters, skill_params)
            
            logger.info(
                f"Compétence {name} terminée",
                success=result.success,
                duration=result.duration
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Erreur exécution compétence {name}: {e}")
            raise
    
    async def execute_skill_sequence(
        self,
        sequence: List[Dict[str, Any]],
        stop_on_error: bool = True,
        skill_params: Optional[SkillParameters] = None
    ) -> List[SkillResult]:
        """
        Exécute une séquence de compétences.
        
        Args:
            sequence: Liste de {skill_name, parameters}
            stop_on_error: Arrêter à la première erreur
            skill_params: Paramètres d'exécution globaux
            
        Returns:
            Liste des résultats
        """
        results = []
        
        logger.info(f"Démarrage séquence de {len(sequence)} compétences")
        
        for i, step in enumerate(sequence):
            skill_name = step.get("skill_name")
            parameters = step.get("parameters", {})
            step_skill_params = step.get("skill_params", skill_params)
            
            if not skill_name:
                logger.error(f"Étape {i}: skill_name manquant")
                if stop_on_error:
                    break
                continue
            
            try:
                result = await self.execute_skill(
                    skill_name, parameters, step_skill_params
                )
                results.append(result)
                
                if not result.success and stop_on_error:
                    logger.warning(f"Arrêt séquence à l'étape {i} (échec)")
                    break
                    
            except Exception as e:
                logger.error(f"Erreur étape {i} ({skill_name}): {e}")
                
                error_result = SkillResult(
                    skill_name=skill_name,
                    success=False,
                    message=f"Erreur: {e}",
                    duration=0.0,
                    error=str(e)
                )
                results.append(error_result)
                
                if stop_on_error:
                    break
        
        success_count = sum(1 for r in results if r.success)
        logger.info(
            f"Séquence terminée: {success_count}/{len(results)} réussies"
        )
        
        return results
    
    async def test_skill(self, name: str, test_parameters: Optional[Dict[str, Any]] = None) -> bool:
        """
        Teste une compétence avec des paramètres de test.
        
        Args:
            name: Nom de la compétence
            test_parameters: Paramètres de test (utilise les exemples si None)
            
        Returns:
            True si le test réussit
        """
        skill = self._skills.get(name)
        if not skill:
            logger.error(f"Compétence '{name}' non trouvée pour test")
            return False
        
        # Utiliser les exemples si pas de paramètres fournis
        if test_parameters is None:
            examples = skill.get_examples()
            if not examples:
                logger.warning(f"Pas d'exemples disponibles pour {name}")
                return False
            test_parameters = examples[0]
        
        logger.info(f"Test compétence: {name}")
        
        try:
            result = await skill.test_execution(test_parameters)
            logger.info(f"Test {name}: {'RÉUSSI' if result else 'ÉCHOUÉ'}")
            return result
            
        except Exception as e:
            logger.error(f"Erreur test {name}: {e}")
            return False
    
    async def test_all_skills(self) -> Dict[str, bool]:
        """
        Teste toutes les compétences enregistrées.
        
        Returns:
            Dictionnaire des résultats de test
        """
        results = {}
        
        logger.info("Démarrage tests de toutes les compétences")
        
        for skill_name in self._skills.keys():
            results[skill_name] = await self.test_skill(skill_name)
        
        success_count = sum(1 for result in results.values() if result)
        logger.info(f"Tests terminés: {success_count}/{len(results)} réussis")
        
        return results
    
    def validate_skill_parameters(self, name: str, parameters: Dict[str, Any]) -> bool:
        """
        Valide les paramètres d'une compétence.
        
        Args:
            name: Nom de la compétence
            parameters: Paramètres à valider
            
        Returns:
            True si les paramètres sont valides
        """
        skill = self._skills.get(name)
        if not skill:
            return False
        
        return skill.validate_parameters(parameters)
    
    def get_skill_suggestions(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Suggère des compétences basées sur une requête.
        
        Args:
            query: Requête de recherche
            limit: Nombre maximum de suggestions
            
        Returns:
            Liste des suggestions avec scores
        """
        from difflib import SequenceMatcher
        
        suggestions = []
        query_lower = query.lower()
        
        for skill_name, skill in self._skills.items():
            # Score basé sur le nom
            name_score = SequenceMatcher(None, query_lower, skill_name.lower()).ratio()
            
            # Score basé sur la description
            description = skill.get_description().lower()
            desc_score = SequenceMatcher(None, query_lower, description).ratio()
            
            # Score combiné
            combined_score = max(name_score, desc_score * 0.8)
            
            if combined_score > 0.3:  # Seuil minimum
                suggestions.append({
                    "skill_name": skill_name,
                    "description": skill.get_description(),
                    "score": combined_score,
                    "examples": skill.get_examples()[:2]  # 2 premiers exemples
                })
        
        # Trier par score décroissant
        suggestions.sort(key=lambda x: x["score"], reverse=True)
        
        return suggestions[:limit]
    
    def get_manager_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques du gestionnaire.
        
        Returns:
            Statistiques globales
        """
        total_executions = sum(skill.get_stats()["execution_count"] for skill in self._skills.values())
        total_successes = sum(skill.get_stats()["success_count"] for skill in self._skills.values())
        
        return {
            "total_skills": len(self._skills),
            "total_executions": total_executions,
            "total_successes": total_successes,
            "global_success_rate": total_successes / total_executions if total_executions > 0 else 0.0,
            "skill_stats": {name: skill.get_stats() for name, skill in self._skills.items()}
        }
    
    def reset_all_stats(self) -> None:
        """Remet à zéro les statistiques de toutes les compétences."""
        for skill in self._skills.values():
            skill.reset_stats()
        
        logger.info("Statistiques de toutes les compétences remises à zéro")
    
    def unregister_skill(self, name: str) -> bool:
        """
        Désenregistre une compétence.
        
        Args:
            name: Nom de la compétence
            
        Returns:
            True si désenregistrement réussi
        """
        if name in self._skills:
            del self._skills[name]
            if name in self._skill_classes:
                del self._skill_classes[name]
            
            logger.info(f"Compétence désenregistrée: {name}")
            return True
        
        return False