"""
Compétences d'interaction utilisateur pour Desktop Agent.

Fournit les capacités de clic, saisie de texte et raccourcis clavier.
"""

import asyncio
from typing import Any, Dict, List, Optional

from .base_skill import BaseSkill, SkillParameters, SkillResult
from ..common.errors import ElementNotFoundError, SkillError


class ClickTextSkill(BaseSkill):
    """Compétence pour cliquer sur du texte visible à l'écran."""
    
    def __init__(self):
        super().__init__("click_text")
    
    async def execute(
        self,
        parameters: Dict[str, Any],
        skill_params: Optional[SkillParameters] = None
    ) -> SkillResult:
        """
        Clique sur du texte trouvé à l'écran.
        
        Args:
            parameters: {"text": str, "fuzzy": bool, "button": str}
            skill_params: Paramètres d'exécution
            
        Returns:
            Résultat du clic
        """
        text = parameters["text"]
        fuzzy = parameters.get("fuzzy", True)
        button = parameters.get("button", "left")
        
        try:
            # Méthode 1: Recherche via accessibilité
            element = await self.perception.find_ui_element(
                text, query_type="text", fuzzy=fuzzy
            )
            
            if element and element.enabled:
                center = element.bounds.center
                success = self.os_adapter.click(center[0], center[1], button)
                
                if success:
                    return SkillResult(
                        skill_name=self.name,
                        success=True,
                        message=f"Clic sur '{text}' via accessibilité",
                        duration=0.0,
                        data={
                            "element": {
                                "name": element.name,
                                "role": element.role.value,
                                "bounds": element.bounds.model_dump()
                            },
                            "click_position": center,
                            "method": "accessibility"
                        }
                    )
            
            # Méthode 2: Recherche via OCR
            text_matches = await self.perception.find_text_on_screen(text, fuzzy=fuzzy)
            
            if text_matches:
                # Prendre la correspondance avec la meilleure confiance
                best_match = max(text_matches, key=lambda x: x.confidence)
                center = best_match.bounds.center
                
                success = self.os_adapter.click(center[0], center[1], button)
                
                if success:
                    return SkillResult(
                        skill_name=self.name,
                        success=True,
                        message=f"Clic sur '{text}' via OCR",
                        duration=0.0,
                        data={
                            "text_match": {
                                "text": best_match.text,
                                "confidence": best_match.confidence,
                                "bounds": best_match.bounds.model_dump()
                            },
                            "click_position": center,
                            "method": "ocr"
                        }
                    )
            
            raise ElementNotFoundError(f"Texte '{text}' non trouvé à l'écran")
            
        except Exception as e:
            raise SkillError(f"Erreur clic sur texte '{text}': {e}")
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Valide les paramètres."""
        return (
            "text" in parameters and
            isinstance(parameters["text"], str) and
            len(parameters["text"].strip()) > 0
        )
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        """Retourne le schéma des paramètres."""
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Texte à rechercher et cliquer"
                },
                "fuzzy": {
                    "type": "boolean",
                    "description": "Recherche approximative",
                    "default": True
                },
                "button": {
                    "type": "string",
                    "enum": ["left", "right", "middle"],
                    "description": "Bouton de souris",
                    "default": "left"
                }
            },
            "required": ["text"]
        }
    
    def get_description(self) -> str:
        """Description de la compétence."""
        return "Clique sur du texte visible à l'écran en utilisant l'accessibilité ou l'OCR"
    
    def get_examples(self) -> List[Dict[str, Any]]:
        """Exemples d'utilisation."""
        return [
            {"text": "OK"},
            {"text": "Enregistrer", "fuzzy": False},
            {"text": "Menu", "button": "right"}
        ]


class TypeTextSkill(BaseSkill):
    """Compétence pour saisir du texte."""
    
    def __init__(self):
        super().__init__("type_text")
    
    async def execute(
        self,
        parameters: Dict[str, Any],
        skill_params: Optional[SkillParameters] = None
    ) -> SkillResult:
        """
        Saisit du texte au clavier.
        
        Args:
            parameters: {"text": str, "clear_before": bool, "press_enter": bool}
            skill_params: Paramètres d'exécution
            
        Returns:
            Résultat de la saisie
        """
        text = parameters["text"]
        clear_before = parameters.get("clear_before", False)
        press_enter = parameters.get("press_enter", False)
        
        try:
            # Effacer le contenu existant si demandé
            if clear_before:
                self.os_adapter.hotkey("ctrl", "a")
                await asyncio.sleep(0.1)
            
            # Saisir le texte
            success = self.os_adapter.type_text(text)
            
            if not success:
                raise SkillError("Échec de la saisie de texte")
            
            # Appuyer sur Entrée si demandé
            if press_enter:
                await asyncio.sleep(0.2)
                self.os_adapter.key_press("enter")
            
            return SkillResult(
                skill_name=self.name,
                success=True,
                message=f"Texte saisi: '{text}'",
                duration=0.0,
                data={
                    "text": text,
                    "length": len(text),
                    "clear_before": clear_before,
                    "press_enter": press_enter
                }
            )
            
        except Exception as e:
            raise SkillError(f"Erreur saisie texte: {e}")
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Valide les paramètres."""
        return (
            "text" in parameters and
            isinstance(parameters["text"], str)
        )
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        """Retourne le schéma des paramètres."""
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Texte à saisir"
                },
                "clear_before": {
                    "type": "boolean",
                    "description": "Effacer le contenu avant saisie",
                    "default": False
                },
                "press_enter": {
                    "type": "boolean",
                    "description": "Appuyer sur Entrée après saisie",
                    "default": False
                }
            },
            "required": ["text"]
        }
    
    def get_description(self) -> str:
        """Description de la compétence."""
        return "Saisit du texte au clavier dans l'élément actuellement focalisé"
    
    def get_examples(self) -> List[Dict[str, Any]]:
        """Exemples d'utilisation."""
        return [
            {"text": "Bonjour monde"},
            {"text": "test@email.com", "clear_before": True},
            {"text": "recherche", "press_enter": True}
        ]


class HotkeySkill(BaseSkill):
    """Compétence pour exécuter des raccourcis clavier."""
    
    def __init__(self):
        super().__init__("hotkey")
    
    async def execute(
        self,
        parameters: Dict[str, Any],
        skill_params: Optional[SkillParameters] = None
    ) -> SkillResult:
        """
        Exécute un raccourci clavier.
        
        Args:
            parameters: {"keys": List[str] ou str, "repeat": int}
            skill_params: Paramètres d'exécution
            
        Returns:
            Résultat de l'exécution
        """
        keys = parameters["keys"]
        repeat = parameters.get("repeat", 1)
        
        try:
            # Normaliser les touches
            if isinstance(keys, str):
                # Format "ctrl+c" ou "alt+tab"
                key_list = [k.strip().lower() for k in keys.split("+")]
            elif isinstance(keys, list):
                key_list = [k.strip().lower() for k in keys]
            else:
                raise SkillError("Format de touches invalide")
            
            # Mapper les touches communes
            key_mapping = {
                "ctrl": "ctrl",
                "control": "ctrl",
                "alt": "alt",
                "shift": "shift",
                "win": "win",
                "windows": "win",
                "cmd": "cmd",
                "tab": "tab",
                "enter": "enter",
                "return": "enter",
                "space": "space",
                "esc": "esc",
                "escape": "esc"
            }
            
            mapped_keys = []
            for key in key_list:
                mapped_key = key_mapping.get(key, key)
                mapped_keys.append(mapped_key)
            
            # Exécuter le raccourci
            success = True
            for _ in range(repeat):
                if not self.os_adapter.hotkey(*mapped_keys):
                    success = False
                    break
                
                if repeat > 1:
                    await asyncio.sleep(0.1)
            
            if not success:
                raise SkillError(f"Échec exécution raccourci {keys}")
            
            return SkillResult(
                skill_name=self.name,
                success=True,
                message=f"Raccourci exécuté: {'+'.join(mapped_keys)}",
                duration=0.0,
                data={
                    "keys": mapped_keys,
                    "repeat": repeat,
                    "original_input": keys
                }
            )
            
        except Exception as e:
            raise SkillError(f"Erreur raccourci clavier: {e}")
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """Valide les paramètres."""
        if "keys" not in parameters:
            return False
        
        keys = parameters["keys"]
        
        if isinstance(keys, str):
            return len(keys.strip()) > 0
        elif isinstance(keys, list):
            return len(keys) > 0 and all(isinstance(k, str) for k in keys)
        
        return False
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        """Retourne le schéma des paramètres."""
        return {
            "type": "object",
            "properties": {
                "keys": {
                    "oneOf": [
                        {
                            "type": "string",
                            "description": "Raccourci au format 'ctrl+c' ou 'alt+tab'"
                        },
                        {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Liste des touches ['ctrl', 'c']"
                        }
                    ]
                },
                "repeat": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Nombre de répétitions",
                    "default": 1
                }
            },
            "required": ["keys"]
        }
    
    def get_description(self) -> str:
        """Description de la compétence."""
        return "Exécute des raccourcis clavier (Ctrl+C, Alt+Tab, etc.)"
    
    def get_examples(self) -> List[Dict[str, Any]]:
        """Exemples d'utilisation."""
        return [
            {"keys": "ctrl+c"},
            {"keys": "alt+tab"},
            {"keys": ["ctrl", "shift", "n"]},
            {"keys": "tab", "repeat": 3}
        ]