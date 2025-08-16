"""
Extracteur de slots pour Desktop Agent.

Normalise et enrichit les paramètres extraits des intentions.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..common.config import get_settings
from ..common.errors import SlotExtractionError
from ..common.logging_utils import get_nlu_logger
from ..common.models import Intent, IntentType

logger = get_nlu_logger()


class SlotExtractor:
    """Extracteur et normalisateur de slots."""
    
    def __init__(self):
        self.settings = get_settings()
        
        # Mappings pour la normalisation
        self._app_mappings = self._initialize_app_mappings()
        self._file_extensions = self._initialize_file_extensions()
        
        logger.info("Extracteur de slots initialisé")
    
    def _initialize_app_mappings(self) -> Dict[str, str]:
        """Initialise les mappings de noms d'applications."""
        return {
            # Navigateurs
            "chrome": "Google Chrome",
            "google chrome": "Google Chrome",
            "firefox": "Firefox",
            "mozilla firefox": "Firefox",
            "edge": "Microsoft Edge",
            "microsoft edge": "Microsoft Edge",
            "safari": "Safari",
            
            # Éditeurs de texte
            "notepad": "Notepad",
            "bloc-notes": "Notepad",
            "bloc notes": "Notepad",
            "wordpad": "WordPad",
            "word": "Microsoft Word",
            "microsoft word": "Microsoft Word",
            "code": "Visual Studio Code",
            "vscode": "Visual Studio Code",
            "visual studio code": "Visual Studio Code",
            "sublime": "Sublime Text",
            "sublime text": "Sublime Text",
            "notepad++": "Notepad++",
            "notepad plus plus": "Notepad++",
            
            # Utilitaires
            "calculator": "Calculator",
            "calculatrice": "Calculator",
            "calc": "Calculator",
            "paint": "Paint",
            "peinture": "Paint",
            "explorer": "File Explorer",
            "explorateur": "File Explorer",
            "file explorer": "File Explorer",
            "explorateur de fichiers": "File Explorer",
            
            # Communication
            "outlook": "Microsoft Outlook",
            "microsoft outlook": "Microsoft Outlook",
            "teams": "Microsoft Teams",
            "microsoft teams": "Microsoft Teams",
            "skype": "Skype",
            "discord": "Discord",
            "slack": "Slack",
            
            # Développement
            "cmd": "Command Prompt",
            "command prompt": "Command Prompt",
            "invite de commandes": "Command Prompt",
            "powershell": "PowerShell",
            "terminal": "Windows Terminal",
            "git bash": "Git Bash",
            
            # Multimédia
            "vlc": "VLC Media Player",
            "media player": "Windows Media Player",
            "windows media player": "Windows Media Player",
            "photos": "Photos",
            "spotify": "Spotify",
            
            # Bureautique
            "excel": "Microsoft Excel",
            "microsoft excel": "Microsoft Excel",
            "powerpoint": "Microsoft PowerPoint",
            "microsoft powerpoint": "Microsoft PowerPoint",
            "onenote": "Microsoft OneNote",
            "microsoft onenote": "Microsoft OneNote"
        }
    
    def _initialize_file_extensions(self) -> Dict[str, str]:
        """Initialise les extensions de fichiers par type."""
        return {
            "text": [".txt", ".md", ".rst", ".log"],
            "document": [".doc", ".docx", ".pdf", ".rtf", ".odt"],
            "spreadsheet": [".xls", ".xlsx", ".csv", ".ods"],
            "presentation": [".ppt", ".pptx", ".odp"],
            "image": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg"],
            "video": [".mp4", ".avi", ".mkv", ".mov", ".wmv"],
            "audio": [".mp3", ".wav", ".flac", ".m4a", ".wma"],
            "code": [".py", ".js", ".html", ".css", ".java", ".cpp", ".c", ".php"],
            "archive": [".zip", ".rar", ".7z", ".tar", ".gz"]
        }
    
    def extract_and_normalize_slots(self, intent: Intent) -> Dict[str, Any]:
        """
        Extrait et normalise les slots d'une intention.
        
        Args:
            intent: Intention avec slots bruts
            
        Returns:
            Slots normalisés et enrichis
        """
        try:
            normalized_slots = intent.slots.copy()
            
            # Normalisation selon le type d'intention
            if intent.type in [IntentType.OPEN_APP, IntentType.FOCUS_APP]:
                normalized_slots = self._normalize_app_slots(normalized_slots)
            
            elif intent.type == IntentType.CLICK_TEXT:
                normalized_slots = self._normalize_text_slots(normalized_slots)
            
            elif intent.type == IntentType.TYPE_TEXT:
                normalized_slots = self._normalize_text_input_slots(normalized_slots)
            
            elif intent.type == IntentType.WEB_SEARCH:
                normalized_slots = self._normalize_search_slots(normalized_slots)
            
            elif intent.type == IntentType.SAVE_FILE:
                normalized_slots = self._normalize_file_slots(normalized_slots)
            
            elif intent.type == IntentType.WRITE_TEXT_FILE:
                normalized_slots = self._normalize_write_file_slots(normalized_slots)
            
            logger.debug(
                f"Slots normalisés pour {intent.type.value}",
                original_slots=intent.slots,
                normalized_slots=normalized_slots
            )
            
            return normalized_slots
            
        except Exception as e:
            logger.error(f"Erreur normalisation slots: {e}")
            raise SlotExtractionError(f"Erreur extraction slots: {e}")
    
    def _normalize_app_slots(self, slots: Dict[str, Any]) -> Dict[str, Any]:
        """Normalise les slots d'application."""
        if "app_name" in slots:
            app_name = slots["app_name"].lower().strip()
            
            # Rechercher dans les mappings
            normalized_name = self._app_mappings.get(app_name, None)
            
            if normalized_name:
                slots["app_name"] = normalized_name
                slots["app_name_normalized"] = True
            else:
                # Capitaliser chaque mot si pas de mapping trouvé
                slots["app_name"] = app_name.title()
                slots["app_name_normalized"] = False
            
            # Ajouter des métadonnées
            slots["app_category"] = self._get_app_category(slots["app_name"])
        
        return slots
    
    def _normalize_text_slots(self, slots: Dict[str, Any]) -> Dict[str, Any]:
        """Normalise les slots de texte pour clic."""
        if "text" in slots:
            text = slots["text"].strip()
            
            # Nettoyer les guillemets
            text = text.strip('"\'')
            
            slots["text"] = text
            slots["text_length"] = len(text)
            
            # Déterminer le type de texte (bouton, lien, etc.)
            slots["text_type"] = self._classify_text_type(text)
        
        return slots
    
    def _normalize_text_input_slots(self, slots: Dict[str, Any]) -> Dict[str, Any]:
        """Normalise les slots de saisie de texte."""
        if "text" in slots:
            text = slots["text"]
            
            # Nettoyer les guillemets
            text = text.strip('"\'')
            
            slots["text"] = text
            slots["text_length"] = len(text)
            
            # Détecter des patterns spéciaux
            slots["contains_email"] = bool(re.search(r'\b[\w.-]+@[\w.-]+\.\w+\b', text))
            slots["contains_url"] = bool(re.search(r'https?://\S+', text))
            slots["contains_phone"] = bool(re.search(r'\b\d{2,4}[-.\s]?\d{2,4}[-.\s]?\d{2,4}\b', text))
            
            # Déterminer si c'est probablement un mot de passe
            slots["is_password"] = self._is_password_like(text)
        
        return slots
    
    def _normalize_search_slots(self, slots: Dict[str, Any]) -> Dict[str, Any]:
        """Normalise les slots de recherche web."""
        if "query" in slots:
            query = slots["query"].strip()
            
            # Nettoyer les guillemets
            query = query.strip('"\'')
            
            slots["query"] = query
            slots["query_length"] = len(query)
            slots["word_count"] = len(query.split())
            
            # Classifier le type de requête
            slots["query_type"] = self._classify_search_query(query)
        
        return slots
    
    def _normalize_file_slots(self, slots: Dict[str, Any]) -> Dict[str, Any]:
        """Normalise les slots de fichier."""
        if "path" in slots:
            path_str = slots["path"].strip()
            
            # Nettoyer les guillemets
            path_str = path_str.strip('"\'')
            
            try:
                path = Path(path_str)
                
                slots["path"] = str(path)
                slots["filename"] = path.name
                slots["directory"] = str(path.parent)
                slots["extension"] = path.suffix.lower()
                slots["file_type"] = self._get_file_type(path.suffix.lower())
                slots["is_absolute"] = path.is_absolute()
                
            except Exception:
                # Si le chemin n'est pas valide, garder tel quel
                slots["path"] = path_str
                slots["filename"] = path_str
                slots["is_valid_path"] = False
        
        return slots
    
    def _normalize_write_file_slots(self, slots: Dict[str, Any]) -> Dict[str, Any]:
        """Normalise les slots pour l'écriture de fichier."""
        if "content" in slots:
            content = slots["content"].strip()
            
            slots["content"] = content
            slots["content_length"] = len(content)
            slots["line_count"] = len(content.split('\n'))
            slots["word_count"] = len(content.split())
            
            # Détecter le type de contenu
            slots["content_type"] = self._classify_content_type(content)
            
            # Suggérer une extension de fichier
            slots["suggested_extension"] = self._suggest_file_extension(content)
            
            # Générer un nom de fichier par défaut
            slots["default_filename"] = self._generate_default_filename(content)
        
        # Normaliser le chemin si présent
        if "path" in slots:
            slots = self._normalize_file_slots(slots)
        
        return slots
    
    def _get_app_category(self, app_name: str) -> str:
        """Détermine la catégorie d'une application."""
        app_name_lower = app_name.lower()
        
        if any(browser in app_name_lower for browser in ["chrome", "firefox", "edge", "safari"]):
            return "browser"
        elif any(editor in app_name_lower for editor in ["notepad", "word", "code", "sublime"]):
            return "editor"
        elif any(util in app_name_lower for util in ["calculator", "paint", "explorer"]):
            return "utility"
        elif any(comm in app_name_lower for comm in ["outlook", "teams", "skype", "discord"]):
            return "communication"
        elif any(dev in app_name_lower for dev in ["cmd", "powershell", "terminal", "git"]):
            return "development"
        else:
            return "other"
    
    def _classify_text_type(self, text: str) -> str:
        """Classifie le type de texte pour clic."""
        text_lower = text.lower()
        
        # Boutons communs
        buttons = ["ok", "cancel", "annuler", "save", "enregistrer", "open", "ouvrir", 
                  "close", "fermer", "yes", "oui", "no", "non", "apply", "appliquer"]
        
        if text_lower in buttons:
            return "button"
        elif text_lower.startswith("http") or "www." in text_lower:
            return "link"
        elif text_lower in ["menu", "file", "edit", "view", "help", "fichier", "édition", "affichage", "aide"]:
            return "menu"
        else:
            return "text"
    
    def _is_password_like(self, text: str) -> bool:
        """Détermine si un texte ressemble à un mot de passe."""
        if len(text) < 4:
            return False
        
        # Heuristiques simples
        has_upper = any(c.isupper() for c in text)
        has_lower = any(c.islower() for c in text)
        has_digit = any(c.isdigit() for c in text)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in text)
        
        return sum([has_upper, has_lower, has_digit, has_special]) >= 2
    
    def _classify_search_query(self, query: str) -> str:
        """Classifie le type de requête de recherche."""
        query_lower = query.lower()
        
        if query.startswith('"') and query.endswith('"'):
            return "exact"
        elif any(word in query_lower for word in ["how", "comment", "why", "pourquoi", "what", "qu'est-ce"]):
            return "question"
        elif any(word in query_lower for word in ["tutorial", "tutoriel", "guide", "learn", "apprendre"]):
            return "learning"
        elif any(word in query_lower for word in ["buy", "acheter", "price", "prix", "cost", "coût"]):
            return "commercial"
        else:
            return "general"
    
    def _get_file_type(self, extension: str) -> str:
        """Détermine le type de fichier par extension."""
        for file_type, extensions in self._file_extensions.items():
            if extension in extensions:
                return file_type
        return "other"
    
    def _classify_content_type(self, content: str) -> str:
        """Classifie le type de contenu."""
        content_lower = content.lower()
        
        # Détecter du code
        code_indicators = ["def ", "function", "class ", "import ", "from ", "#include", "<?php", "<html"]
        if any(indicator in content_lower for indicator in code_indicators):
            return "code"
        
        # Détecter du Markdown
        if any(indicator in content for indicator in ["# ", "## ", "**", "*", "[", "]", "`"]):
            return "markdown"
        
        # Détecter du JSON/XML
        if content.strip().startswith(("{", "<")) and content.strip().endswith(("}", ">")):
            return "structured"
        
        # Détecter une liste
        lines = content.split('\n')
        list_indicators = [line.strip().startswith(("-", "*", "•")) for line in lines if line.strip()]
        if len(list_indicators) > 1 and sum(list_indicators) / len(list_indicators) > 0.5:
            return "list"
        
        return "text"
    
    def _suggest_file_extension(self, content: str) -> str:
        """Suggère une extension de fichier basée sur le contenu."""
        content_type = self._classify_content_type(content)
        
        suggestions = {
            "code": ".py",  # Par défaut Python
            "markdown": ".md",
            "structured": ".json",
            "list": ".txt",
            "text": ".txt"
        }
        
        return suggestions.get(content_type, ".txt")
    
    def _generate_default_filename(self, content: str) -> str:
        """Génère un nom de fichier par défaut basé sur le contenu."""
        # Prendre les premiers mots du contenu
        words = content.split()[:3]
        
        if not words:
            return "nouveau_fichier.txt"
        
        # Nettoyer les mots pour un nom de fichier
        clean_words = []
        for word in words:
            # Garder seulement les caractères alphanumériques
            clean_word = re.sub(r'[^\w]', '', word.lower())
            if clean_word:
                clean_words.append(clean_word)
        
        if not clean_words:
            return "nouveau_fichier.txt"
        
        base_name = "_".join(clean_words)
        extension = self._suggest_file_extension(content)
        
        return f"{base_name}{extension}"
    
    def validate_slots(self, intent_type: IntentType, slots: Dict[str, Any]) -> Dict[str, Any]:
        """
        Valide les slots selon le type d'intention.
        
        Args:
            intent_type: Type d'intention
            slots: Slots à valider
            
        Returns:
            Dictionnaire avec validation_errors et warnings
        """
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        # Validation selon le type d'intention
        if intent_type in [IntentType.OPEN_APP, IntentType.FOCUS_APP]:
            if not slots.get("app_name"):
                validation_result["errors"].append("app_name requis")
                validation_result["valid"] = False
        
        elif intent_type == IntentType.CLICK_TEXT:
            if not slots.get("text"):
                validation_result["errors"].append("text requis pour clic")
                validation_result["valid"] = False
        
        elif intent_type == IntentType.TYPE_TEXT:
            if not slots.get("text"):
                validation_result["errors"].append("text requis pour saisie")
                validation_result["valid"] = False
            elif slots.get("is_password"):
                validation_result["warnings"].append("Possible mot de passe détecté")
        
        elif intent_type == IntentType.WEB_SEARCH:
            if not slots.get("query"):
                validation_result["errors"].append("query requis pour recherche")
                validation_result["valid"] = False
        
        elif intent_type == IntentType.WRITE_TEXT_FILE:
            if not slots.get("content"):
                validation_result["errors"].append("content requis pour création de fichier")
                validation_result["valid"] = False
        
        return validation_result
    
    def get_slot_suggestions(self, intent_type: IntentType, partial_slots: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Fournit des suggestions pour compléter les slots.
        
        Args:
            intent_type: Type d'intention
            partial_slots: Slots partiels
            
        Returns:
            Suggestions par slot
        """
        suggestions = {}
        
        if intent_type in [IntentType.OPEN_APP, IntentType.FOCUS_APP]:
            if "app_name" not in partial_slots:
                suggestions["app_name"] = list(set(self._app_mappings.values()))[:10]
        
        elif intent_type == IntentType.SAVE_FILE:
            if "path" not in partial_slots:
                suggestions["path"] = [
                    str(Path.home() / "Documents"),
                    str(Path.home() / "Desktop"),
                    str(Path.home() / "Downloads")
                ]
        
        return suggestions