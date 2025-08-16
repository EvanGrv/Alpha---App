"""
Classe de base pour les compétences (skills) de Desktop Agent.

Définit l'interface commune et les mécanismes de base pour toutes les compétences.
"""

import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ..common.config import get_settings
from ..common.errors import SkillError, TimeoutError as AgentTimeoutError
from ..common.logging_utils import get_skill_logger
from ..common.models import Action, StepResult, StepStatus
from ..os_adapters import get_os_adapter
from ..perception import PerceptionManager


class SkillParameters(BaseModel):
    """Paramètres de base pour les compétences."""
    timeout: float = Field(default=10.0, ge=0.0, description="Timeout en secondes")
    retry_count: int = Field(default=3, ge=0, description="Nombre de tentatives")
    wait_after: float = Field(default=0.5, ge=0.0, description="Attente après exécution")
    screenshot_before: bool = Field(default=False, description="Capture avant exécution")
    screenshot_after: bool = Field(default=False, description="Capture après exécution")


class SkillResult(BaseModel):
    """Résultat d'exécution d'une compétence."""
    skill_name: str = Field(..., description="Nom de la compétence")
    success: bool = Field(..., description="Succès de l'exécution")
    message: str = Field(..., description="Message de résultat")
    duration: float = Field(..., description="Durée d'exécution en secondes")
    data: Dict[str, Any] = Field(default_factory=dict, description="Données de résultat")
    error: Optional[str] = Field(None, description="Message d'erreur si échec")
    screenshot_before: Optional[str] = Field(None, description="Capture avant")
    screenshot_after: Optional[str] = Field(None, description="Capture après")


class BaseSkill(ABC):
    """Classe de base abstraite pour toutes les compétences."""
    
    def __init__(self, name: str):
        self.name = name
        self.settings = get_settings()
        self.os_adapter = get_os_adapter()
        self.perception = PerceptionManager()
        self.logger = get_skill_logger(name)
        
        # Statistiques d'exécution
        self._execution_count = 0
        self._success_count = 0
        self._total_duration = 0.0
    
    @abstractmethod
    async def execute(
        self,
        parameters: Dict[str, Any],
        skill_params: Optional[SkillParameters] = None
    ) -> SkillResult:
        """
        Exécute la compétence avec les paramètres donnés.
        
        Args:
            parameters: Paramètres spécifiques à la compétence
            skill_params: Paramètres généraux d'exécution
            
        Returns:
            Résultat de l'exécution
        """
        pass
    
    @abstractmethod
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """
        Valide les paramètres avant exécution.
        
        Args:
            parameters: Paramètres à valider
            
        Returns:
            True si les paramètres sont valides
        """
        pass
    
    @abstractmethod
    def get_parameter_schema(self) -> Dict[str, Any]:
        """
        Retourne le schéma des paramètres attendus.
        
        Returns:
            Schéma JSON des paramètres
        """
        pass
    
    def get_description(self) -> str:
        """
        Retourne une description de la compétence.
        
        Returns:
            Description textuelle
        """
        return f"Compétence: {self.name}"
    
    def get_examples(self) -> List[Dict[str, Any]]:
        """
        Retourne des exemples d'utilisation.
        
        Returns:
            Liste d'exemples avec paramètres
        """
        return []
    
    async def _execute_with_monitoring(
        self,
        parameters: Dict[str, Any],
        skill_params: Optional[SkillParameters] = None
    ) -> SkillResult:
        """
        Wrapper d'exécution avec monitoring et gestion d'erreurs.
        
        Args:
            parameters: Paramètres de la compétence
            skill_params: Paramètres d'exécution
            
        Returns:
            Résultat avec monitoring
        """
        if skill_params is None:
            skill_params = SkillParameters()
        
        start_time = time.time()
        screenshot_before = None
        screenshot_after = None
        
        try:
            # Validation des paramètres
            if not self.validate_parameters(parameters):
                raise SkillError(f"Paramètres invalides pour {self.name}")
            
            # Capture avant si demandée
            if skill_params.screenshot_before:
                screenshot_before = await self._take_screenshot("before")
            
            self.logger.info(
                f"Démarrage exécution {self.name}",
                parameters=parameters,
                timeout=skill_params.timeout
            )
            
            # Exécution avec timeout
            result = await self._execute_with_timeout(
                parameters, skill_params
            )
            
            # Capture après si demandée
            if skill_params.screenshot_after:
                screenshot_after = await self._take_screenshot("after")
            
            # Attendre si spécifié
            if skill_params.wait_after > 0:
                await self._async_sleep(skill_params.wait_after)
            
            # Mettre à jour les statistiques
            duration = time.time() - start_time
            self._update_stats(success=result.success, duration=duration)
            
            # Enrichir le résultat
            result.duration = duration
            result.screenshot_before = screenshot_before
            result.screenshot_after = screenshot_after
            
            self.logger.info(
                f"Exécution {self.name} terminée",
                success=result.success,
                duration=duration,
                message=result.message
            )
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            self._update_stats(success=False, duration=duration)
            
            error_msg = str(e)
            self.logger.error(
                f"Erreur exécution {self.name}: {error_msg}",
                duration=duration,
                error=error_msg
            )
            
            return SkillResult(
                skill_name=self.name,
                success=False,
                message=f"Erreur: {error_msg}",
                duration=duration,
                error=error_msg,
                screenshot_before=screenshot_before,
                screenshot_after=screenshot_after
            )
    
    async def _execute_with_timeout(
        self,
        parameters: Dict[str, Any],
        skill_params: SkillParameters
    ) -> SkillResult:
        """
        Exécute avec timeout.
        
        Args:
            parameters: Paramètres de la compétence
            skill_params: Paramètres d'exécution
            
        Returns:
            Résultat de l'exécution
            
        Raises:
            AgentTimeoutError: Si timeout dépassé
        """
        import asyncio
        
        try:
            return await asyncio.wait_for(
                self.execute(parameters, skill_params),
                timeout=skill_params.timeout
            )
        except asyncio.TimeoutError:
            raise AgentTimeoutError(
                f"Timeout de {skill_params.timeout}s dépassé pour {self.name}"
            )
    
    async def _take_screenshot(self, suffix: str = "") -> Optional[str]:
        """
        Prend une capture d'écran.
        
        Args:
            suffix: Suffixe pour le nom de fichier
            
        Returns:
            Chemin du fichier de capture ou None
        """
        try:
            timestamp = int(time.time())
            filename = f"{self.name}_{suffix}_{timestamp}.png"
            filepath = str(self.settings.data_dir / "screenshots" / filename)
            
            await self.perception.get_current_observation(
                save_screenshot=True,
                screenshot_path=filepath
            )
            
            return filepath
            
        except Exception as e:
            self.logger.warning(f"Erreur capture d'écran: {e}")
            return None
    
    async def _async_sleep(self, duration: float) -> None:
        """Attente asynchrone."""
        import asyncio
        await asyncio.sleep(duration)
    
    def _update_stats(self, success: bool, duration: float) -> None:
        """Met à jour les statistiques d'exécution."""
        self._execution_count += 1
        if success:
            self._success_count += 1
        self._total_duration += duration
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Retourne les statistiques de la compétence.
        
        Returns:
            Dictionnaire des statistiques
        """
        return {
            "name": self.name,
            "execution_count": self._execution_count,
            "success_count": self._success_count,
            "success_rate": (
                self._success_count / self._execution_count 
                if self._execution_count > 0 else 0.0
            ),
            "total_duration": self._total_duration,
            "average_duration": (
                self._total_duration / self._execution_count 
                if self._execution_count > 0 else 0.0
            )
        }
    
    def reset_stats(self) -> None:
        """Remet à zéro les statistiques."""
        self._execution_count = 0
        self._success_count = 0
        self._total_duration = 0.0
    
    async def test_execution(self, test_parameters: Dict[str, Any]) -> bool:
        """
        Test d'exécution avec paramètres de test.
        
        Args:
            test_parameters: Paramètres de test
            
        Returns:
            True si le test réussit
        """
        try:
            result = await self._execute_with_monitoring(test_parameters)
            return result.success
        except Exception as e:
            self.logger.error(f"Erreur test {self.name}: {e}")
            return False
    
    def __str__(self) -> str:
        return f"Skill({self.name})"
    
    def __repr__(self) -> str:
        stats = self.get_stats()
        return (
            f"Skill(name='{self.name}', "
            f"executions={stats['execution_count']}, "
            f"success_rate={stats['success_rate']:.2f})"
        )