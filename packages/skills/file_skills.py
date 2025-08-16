"""
Compétences de gestion de fichiers pour Desktop Agent.

Fournit les capacités de sauvegarde et de création de fichiers.
"""

import asyncio
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_skill import BaseSkill, SkillParameters, SkillResult
from ..common.errors import PermissionDeniedError, SkillError


class SaveFileSkill(BaseSkill):
    """Compétence pour sauvegarder un fichier via les raccourcis OS."""
    
    def __init__(self):
        super().__init__("save_file")
    
    async def execute(
        self,
        parameters: Dict[str, Any],
        skill_params: Optional[SkillParameters] = None
    ) -> SkillResult:
        """
        Sauvegarde le fichier actuel.
        
        Args:
            parameters: {"path": str (optionnel), "use_save_as": bool}
            skill_params: Paramètres d'exécution
            
        Returns:
            Résultat de la sauvegarde
        """
        path = parameters.get("path")
        use_save_as = parameters.get("use_save_as", bool(path))
        
        try:
            if use_save_as or path:
                # Utiliser "Enregistrer sous"
                success = self.os_adapter.hotkey("ctrl", "shift", "s")
                if not success:
                    # Fallback vers F12 ou autre raccourci
                    success = self.os_adapter.key_press("f12")
                
                if not success:
                    raise SkillError("Impossible d'ouvrir le dialogue Enregistrer sous")
                
                # Attendre que le dialogue s'ouvre
                await asyncio.sleep(1.0)
                
                # Si un chemin est spécifié, le saisir
                if path:
                    # Effacer le chemin actuel et saisir le nouveau
                    self.os_adapter.hotkey("ctrl", "a")
                    await asyncio.sleep(0.2)
                    self.os_adapter.type_text(str(path))
                    await asyncio.sleep(0.5)
                
                # Confirmer avec Entrée
                self.os_adapter.key_press("enter")
                
                return SkillResult(
                    skill_name=self.name,
                    success=True,
                    message=f"Fichier sauvegardé{'  vers ' + str(path) if path else ''}",
                    duration=0.0,
                    data={
                        "path": path,
                        "method": "save_as"
                    }
                )
            
            else:
                # Sauvegarde simple (Ctrl+S)
                success = self.os_adapter.hotkey("ctrl", "s")
                
                if not success:
                    raise SkillError("Impossible d'exécuter Ctrl+S")
                
                return SkillResult(
                    skill_name=self.name,
                    success=True,
                    message="Fichier sauvegardé",
                    duration=0.0,
                    data={
                        "method": "save"
                    }
                )
                
        except Exception as e:
            raise SkillError(f"Erreur sauvegarde fichier: {e}")
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Valide les paramètres."""
        # Pas de paramètres obligatoires
        return True
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        """Retourne le schéma des paramètres."""
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Chemin de sauvegarde (optionnel)"
                },
                "use_save_as": {
                    "type": "boolean",
                    "description": "Utiliser 'Enregistrer sous'",
                    "default": False
                }
            }
        }
    
    def get_description(self) -> str:
        """Description de la compétence."""
        return "Sauvegarde le fichier actuel via les raccourcis système"
    
    def get_examples(self) -> List[Dict[str, Any]]:
        """Exemples d'utilisation."""
        return [
            {},  # Sauvegarde simple
            {"path": "C:\\Users\\Documents\\mon_fichier.txt"},
            {"use_save_as": True}
        ]


class WriteTextFileSkill(BaseSkill):
    """Compétence composite pour créer et écrire un fichier texte."""
    
    def __init__(self):
        super().__init__("write_text_file")
    
    async def execute(
        self,
        parameters: Dict[str, Any],
        skill_params: Optional[SkillParameters] = None
    ) -> SkillResult:
        """
        Crée un nouveau fichier texte avec le contenu spécifié.
        
        Args:
            parameters: {"content": str, "path": str (optionnel), "app": str}
            skill_params: Paramètres d'exécution
            
        Returns:
            Résultat de la création
        """
        content = parameters["content"]
        path = parameters.get("path")
        app = parameters.get("app", "notepad")  # Application par défaut
        
        try:
            # Étape 1: Ouvrir l'éditeur de texte
            from .app_skills import OpenAppSkill
            open_skill = OpenAppSkill()
            
            open_result = await open_skill._execute_with_monitoring(
                {"app_name": app, "wait_for_launch": True}
            )
            
            if not open_result.success:
                raise SkillError(f"Impossible d'ouvrir {app}")
            
            # Attendre que l'application soit prête
            await asyncio.sleep(1.0)
            
            # Étape 2: Saisir le contenu
            from .interaction_skills import TypeTextSkill
            type_skill = TypeTextSkill()
            
            type_result = await type_skill._execute_with_monitoring(
                {"text": content, "clear_before": True}
            )
            
            if not type_result.success:
                raise SkillError("Impossible de saisir le contenu")
            
            # Étape 3: Sauvegarder si un chemin est spécifié
            if path:
                # Vérifier les permissions d'écriture
                path_obj = Path(path)
                if not self._check_write_permission(path_obj):
                    raise PermissionDeniedError(f"Écriture non autorisée: {path}")
                
                save_skill = SaveFileSkill()
                save_result = await save_skill._execute_with_monitoring(
                    {"path": path, "use_save_as": True}
                )
                
                if not save_result.success:
                    raise SkillError(f"Impossible de sauvegarder vers {path}")
            
            return SkillResult(
                skill_name=self.name,
                success=True,
                message=f"Fichier texte créé{'  et sauvegardé vers ' + str(path) if path else ''}",
                duration=0.0,
                data={
                    "content_length": len(content),
                    "app": app,
                    "path": path,
                    "steps": [
                        "open_app",
                        "type_text",
                        "save_file" if path else None
                    ]
                }
            )
            
        except Exception as e:
            raise SkillError(f"Erreur création fichier texte: {e}")
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Valide les paramètres."""
        return (
            "content" in parameters and
            isinstance(parameters["content"], str)
        )
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        """Retourne le schéma des paramètres."""
        return {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Contenu du fichier texte"
                },
                "path": {
                    "type": "string",
                    "description": "Chemin de sauvegarde (optionnel)"
                },
                "app": {
                    "type": "string",
                    "description": "Application à utiliser",
                    "default": "notepad",
                    "enum": ["notepad", "wordpad", "code", "sublime", "notepad++"]
                }
            },
            "required": ["content"]
        }
    
    def get_description(self) -> str:
        """Description de la compétence."""
        return "Crée un nouveau fichier texte avec le contenu spécifié"
    
    def get_examples(self) -> List[Dict[str, Any]]:
        """Exemples d'utilisation."""
        return [
            {"content": "Bonjour monde!"},
            {
                "content": "# Mon fichier\nContenu du fichier...",
                "path": "C:\\Users\\Documents\\mon_fichier.txt"
            },
            {
                "content": "Code Python:\nprint('Hello World')",
                "app": "code"
            }
        ]
    
    def _check_write_permission(self, path: Path) -> bool:
        """
        Vérifie les permissions d'écriture selon les règles de sécurité.
        
        Args:
            path: Chemin à vérifier
            
        Returns:
            True si l'écriture est autorisée
        """
        # Convertir en chemin absolu
        abs_path = path.resolve()
        
        # Vérifier les chemins autorisés
        allowed_paths = self.settings.security.allowed_write_paths
        
        for allowed in allowed_paths:
            allowed_path = Path(allowed).expanduser().resolve()
            
            try:
                # Vérifier si le chemin est dans un répertoire autorisé
                abs_path.relative_to(allowed_path)
                return True
            except ValueError:
                continue
        
        # Vérifier si c'est un chemin système critique
        system_paths = [
            Path("C:\\Windows"),
            Path("C:\\Program Files"),
            Path("C:\\Program Files (x86)"),
            Path("/System"),
            Path("/usr"),
            Path("/etc")
        ]
        
        for system_path in system_paths:
            try:
                abs_path.relative_to(system_path.resolve())
                # C'est un chemin système, interdire
                return False
            except (ValueError, OSError):
                continue
        
        # Par défaut, autoriser si pas dans les chemins système
        return True