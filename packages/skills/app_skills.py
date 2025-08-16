"""
Compétences de gestion d'applications pour Desktop Agent.

Fournit les capacités d'ouverture, focus et fermeture d'applications.
"""

import asyncio
from typing import Any, Dict, List, Optional

from .base_skill import BaseSkill, SkillParameters, SkillResult
from ..common.errors import AppNotFoundError, SkillError


class OpenAppSkill(BaseSkill):
    """Compétence pour ouvrir une application."""
    
    def __init__(self):
        super().__init__("open_app")
    
    async def execute(
        self,
        parameters: Dict[str, Any],
        skill_params: Optional[SkillParameters] = None
    ) -> SkillResult:
        """
        Ouvre une application.
        
        Args:
            parameters: {"app_name": str, "wait_for_launch": bool}
            skill_params: Paramètres d'exécution
            
        Returns:
            Résultat de l'ouverture
        """
        app_name = parameters["app_name"]
        wait_for_launch = parameters.get("wait_for_launch", True)
        
        try:
            # Vérifier si l'app est déjà ouverte
            running_apps = self.os_adapter.get_running_apps()
            for app in running_apps:
                if app_name.lower() in app["name"].lower():
                    return SkillResult(
                        skill_name=self.name,
                        success=True,
                        message=f"Application {app_name} déjà ouverte",
                        duration=0.0,
                        data={"app_info": app}
                    )
            
            # Ouvrir l'application
            success = self.os_adapter.open_app(app_name)
            
            if not success:
                raise AppNotFoundError(f"Impossible d'ouvrir {app_name}")
            
            # Attendre le lancement si demandé
            if wait_for_launch:
                await self._wait_for_app_launch(app_name)
            
            return SkillResult(
                skill_name=self.name,
                success=True,
                message=f"Application {app_name} ouverte avec succès",
                duration=0.0,
                data={"app_name": app_name}
            )
            
        except Exception as e:
            raise SkillError(f"Erreur ouverture {app_name}: {e}")
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Valide les paramètres."""
        return (
            "app_name" in parameters and
            isinstance(parameters["app_name"], str) and
            len(parameters["app_name"].strip()) > 0
        )
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        """Retourne le schéma des paramètres."""
        return {
            "type": "object",
            "properties": {
                "app_name": {
                    "type": "string",
                    "description": "Nom de l'application à ouvrir"
                },
                "wait_for_launch": {
                    "type": "boolean",
                    "description": "Attendre que l'application se lance",
                    "default": True
                }
            },
            "required": ["app_name"]
        }
    
    def get_description(self) -> str:
        """Description de la compétence."""
        return "Ouvre une application par son nom"
    
    def get_examples(self) -> List[Dict[str, Any]]:
        """Exemples d'utilisation."""
        return [
            {"app_name": "Google Chrome"},
            {"app_name": "Notepad", "wait_for_launch": False},
            {"app_name": "Calculator"}
        ]
    
    async def _wait_for_app_launch(self, app_name: str, timeout: float = 10.0) -> bool:
        """
        Attend qu'une application se lance.
        
        Args:
            app_name: Nom de l'application
            timeout: Timeout en secondes
            
        Returns:
            True si l'application est détectée
        """
        start_time = asyncio.get_event_loop().time()
        
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            running_apps = self.os_adapter.get_running_apps()
            for app in running_apps:
                if app_name.lower() in app["name"].lower():
                    return True
            
            await asyncio.sleep(0.5)
        
        return False


class FocusAppSkill(BaseSkill):
    """Compétence pour mettre le focus sur une application."""
    
    def __init__(self):
        super().__init__("focus_app")
    
    async def execute(
        self,
        parameters: Dict[str, Any],
        skill_params: Optional[SkillParameters] = None
    ) -> SkillResult:
        """
        Met le focus sur une application.
        
        Args:
            parameters: {"app_name": str}
            skill_params: Paramètres d'exécution
            
        Returns:
            Résultat du focus
        """
        app_name = parameters["app_name"]
        
        try:
            # Vérifier que l'app est en cours d'exécution
            running_apps = self.os_adapter.get_running_apps()
            target_app = None
            
            for app in running_apps:
                if app_name.lower() in app["name"].lower():
                    target_app = app
                    break
            
            if not target_app:
                raise AppNotFoundError(f"Application {app_name} non trouvée")
            
            # Mettre le focus
            success = self.os_adapter.focus_app(app_name)
            
            if not success:
                raise SkillError(f"Impossible de mettre le focus sur {app_name}")
            
            return SkillResult(
                skill_name=self.name,
                success=True,
                message=f"Focus mis sur {app_name}",
                duration=0.0,
                data={"app_info": target_app}
            )
            
        except Exception as e:
            raise SkillError(f"Erreur focus {app_name}: {e}")
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Valide les paramètres."""
        return (
            "app_name" in parameters and
            isinstance(parameters["app_name"], str) and
            len(parameters["app_name"].strip()) > 0
        )
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        """Retourne le schéma des paramètres."""
        return {
            "type": "object",
            "properties": {
                "app_name": {
                    "type": "string",
                    "description": "Nom de l'application à cibler"
                }
            },
            "required": ["app_name"]
        }
    
    def get_description(self) -> str:
        """Description de la compétence."""
        return "Met le focus sur une application en cours d'exécution"
    
    def get_examples(self) -> List[Dict[str, Any]]:
        """Exemples d'utilisation."""
        return [
            {"app_name": "Google Chrome"},
            {"app_name": "Notepad"},
            {"app_name": "File Explorer"}
        ]


class CloseAppSkill(BaseSkill):
    """Compétence pour fermer une application."""
    
    def __init__(self):
        super().__init__("close_app")
    
    async def execute(
        self,
        parameters: Dict[str, Any],
        skill_params: Optional[SkillParameters] = None
    ) -> SkillResult:
        """
        Ferme une application.
        
        Args:
            parameters: {"app_name": str, "force": bool}
            skill_params: Paramètres d'exécution
            
        Returns:
            Résultat de la fermeture
        """
        app_name = parameters["app_name"]
        force = parameters.get("force", False)
        
        try:
            # Vérifier que l'app est en cours d'exécution
            running_apps = self.os_adapter.get_running_apps()
            target_app = None
            
            for app in running_apps:
                if app_name.lower() in app["name"].lower():
                    target_app = app
                    break
            
            if not target_app:
                return SkillResult(
                    skill_name=self.name,
                    success=True,
                    message=f"Application {app_name} déjà fermée",
                    duration=0.0
                )
            
            # Fermer l'application
            if force:
                # Fermeture forcée via l'OS
                success = self.os_adapter.close_app(app_name)
            else:
                # Fermeture normale (Alt+F4 ou équivalent)
                success = self.os_adapter.focus_app(app_name)
                if success:
                    await asyncio.sleep(0.5)
                    success = self.os_adapter.hotkey("alt", "f4")
            
            if not success:
                raise SkillError(f"Impossible de fermer {app_name}")
            
            # Vérifier la fermeture
            await asyncio.sleep(1.0)
            still_running = any(
                app_name.lower() in app["name"].lower()
                for app in self.os_adapter.get_running_apps()
            )
            
            if still_running and not force:
                # Tentative de fermeture forcée
                self.os_adapter.close_app(app_name)
            
            return SkillResult(
                skill_name=self.name,
                success=True,
                message=f"Application {app_name} fermée",
                duration=0.0,
                data={"app_info": target_app, "force": force}
            )
            
        except Exception as e:
            raise SkillError(f"Erreur fermeture {app_name}: {e}")
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Valide les paramètres."""
        return (
            "app_name" in parameters and
            isinstance(parameters["app_name"], str) and
            len(parameters["app_name"].strip()) > 0
        )
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        """Retourne le schéma des paramètres."""
        return {
            "type": "object",
            "properties": {
                "app_name": {
                    "type": "string",
                    "description": "Nom de l'application à fermer"
                },
                "force": {
                    "type": "boolean",
                    "description": "Fermeture forcée",
                    "default": False
                }
            },
            "required": ["app_name"]
        }
    
    def get_description(self) -> str:
        """Description de la compétence."""
        return "Ferme une application en cours d'exécution"
    
    def get_examples(self) -> List[Dict[str, Any]]:
        """Exemples d'utilisation."""
        return [
            {"app_name": "Notepad"},
            {"app_name": "Google Chrome", "force": True},
            {"app_name": "Calculator"}
        ]