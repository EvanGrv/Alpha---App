"""
Analyseur d'intentions basé sur des règles pour Desktop Agent.

Utilise des patterns regex et des mots-clés pour identifier les intentions utilisateur.
"""

import re
from typing import Dict, List, Optional, Tuple

from ..common.config import get_settings
from ..common.errors import IntentParsingError, NLUError
from ..common.logging_utils import get_nlu_logger
from ..common.models import Intent, IntentType

logger = get_nlu_logger()


class IntentPattern:
    """Pattern pour reconnaître une intention."""
    
    def __init__(
        self,
        intent_type: IntentType,
        patterns: List[str],
        keywords: List[str],
        priority: int = 1,
        required_slots: Optional[List[str]] = None
    ):
        self.intent_type = intent_type
        self.patterns = [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
        self.keywords = [kw.lower() for kw in keywords]
        self.priority = priority
        self.required_slots = required_slots or []


class IntentParser:
    """Analyseur d'intentions basé sur des règles."""
    
    def __init__(self):
        self.settings = get_settings()
        self._patterns: List[IntentPattern] = []
        self._initialize_patterns()
        
        logger.info(f"Analyseur d'intentions initialisé avec {len(self._patterns)} patterns")
    
    def _initialize_patterns(self) -> None:
        """Initialise les patterns d'intention."""
        
        # Patterns pour ouvrir une application
        self._patterns.append(IntentPattern(
            intent_type=IntentType.OPEN_APP,
            patterns=[
                r"ouvre?\s+(.+)",
                r"lance[rz]?\s+(.+)",
                r"démarre[rz]?\s+(.+)",
                r"exécute[rz]?\s+(.+)",
                r"start\s+(.+)",
                r"open\s+(.+)",
                r"launch\s+(.+)"
            ],
            keywords=["ouvre", "ouvrir", "lance", "lancer", "démarre", "démarrer", "start", "open", "launch"],
            priority=2,
            required_slots=["app_name"]
        ))
        
        # Patterns pour mettre le focus sur une application
        self._patterns.append(IntentPattern(
            intent_type=IntentType.FOCUS_APP,
            patterns=[
                r"va\s+(?:sur|à)\s+(.+)",
                r"focus\s+(?:sur\s+)?(.+)",
                r"active[rz]?\s+(.+)",
                r"switch\s+to\s+(.+)",
                r"passe\s+(?:sur|à)\s+(.+)"
            ],
            keywords=["focus", "active", "activer", "switch", "passe", "passer"],
            priority=2,
            required_slots=["app_name"]
        ))
        
        # Patterns pour cliquer sur du texte
        self._patterns.append(IntentPattern(
            intent_type=IntentType.CLICK_TEXT,
            patterns=[
                r"clique\s+sur\s+(.+)",
                r"appuie\s+sur\s+(.+)",
                r"sélectionne\s+(.+)",
                r"click\s+(?:on\s+)?(.+)",
                r"press\s+(.+)",
                r"touche\s+(.+)"
            ],
            keywords=["clique", "cliquer", "appuie", "appuyer", "sélectionne", "click", "press", "touche"],
            priority=2,
            required_slots=["text"]
        ))
        
        # Patterns pour saisir du texte
        self._patterns.append(IntentPattern(
            intent_type=IntentType.TYPE_TEXT,
            patterns=[
                r"écris\s+(.+)",
                r"tape\s+(.+)",
                r"saisir?\s+(.+)",
                r"type\s+(.+)",
                r"write\s+(.+)",
                r"enter\s+(.+)"
            ],
            keywords=["écris", "écrire", "tape", "taper", "saisir", "type", "write", "enter"],
            priority=2,
            required_slots=["text"]
        ))
        
        # Patterns pour sauvegarder un fichier
        self._patterns.append(IntentPattern(
            intent_type=IntentType.SAVE_FILE,
            patterns=[
                r"sauvegarde\s*(?:le\s+fichier)?(?:\s+(?:dans|vers)\s+(.+))?",
                r"enregistre\s*(?:le\s+fichier)?(?:\s+(?:dans|vers)\s+(.+))?",
                r"save\s*(?:file)?(?:\s+(?:to|as)\s+(.+))?",
                r"ctrl\s*\+\s*s"
            ],
            keywords=["sauvegarde", "sauvegarder", "enregistre", "enregistrer", "save"],
            priority=2
        ))
        
        # Patterns pour recherche web
        self._patterns.append(IntentPattern(
            intent_type=IntentType.WEB_SEARCH,
            patterns=[
                r"recherche\s+(?:sur\s+(?:google|internet)\s+)?(.+)",
                r"cherche\s+(?:sur\s+(?:google|internet)\s+)?(.+)",
                r"search\s+(?:(?:for|on)\s+(?:google|web)\s+)?(.+)",
                r"google\s+(.+)"
            ],
            keywords=["recherche", "rechercher", "cherche", "chercher", "search", "google"],
            priority=2,
            required_slots=["query"]
        ))
        
        # Patterns pour créer un fichier texte
        self._patterns.append(IntentPattern(
            intent_type=IntentType.WRITE_TEXT_FILE,
            patterns=[
                r"crée?\s+(?:un\s+)?fichier\s*(?:texte)?\s*(?:et\s+)?(?:écris\s+)?(.+)",
                r"nouveau\s+fichier\s*(?:texte)?\s*(?:avec\s+)?(.+)",
                r"create\s+(?:a\s+)?(?:text\s+)?file\s*(?:with\s+)?(.+)",
                r"new\s+file\s*(?:with\s+)?(.+)"
            ],
            keywords=["crée", "créer", "nouveau", "fichier", "create", "new", "file"],
            priority=3,
            required_slots=["content"]
        ))
        
        # Trier par priorité décroissante
        self._patterns.sort(key=lambda p: p.priority, reverse=True)
    
    def parse_intent(self, text: str) -> Intent:
        """
        Analyse le texte pour extraire l'intention.
        
        Args:
            text: Texte à analyser
            
        Returns:
            Intention détectée
            
        Raises:
            IntentParsingError: Si aucune intention n'est détectée
        """
        try:
            normalized_text = self._normalize_text(text)
            
            logger.debug(f"Analyse intention: '{text}' -> '{normalized_text}'")
            
            # Essayer chaque pattern
            for pattern in self._patterns:
                match_result = self._match_pattern(normalized_text, pattern)
                
                if match_result:
                    intent_type, confidence, raw_slots = match_result
                    
                    intent = Intent(
                        type=intent_type,
                        confidence=confidence,
                        slots=raw_slots,
                        original_text=text,
                        normalized_text=normalized_text
                    )
                    
                    logger.info(
                        f"Intention détectée: {intent_type.value} (confiance: {confidence:.2f})",
                        intent_type=intent_type.value,
                        confidence=confidence,
                        slots=raw_slots
                    )
                    
                    return intent
            
            # Aucune intention détectée
            logger.warning(f"Aucune intention détectée pour: '{text}'")
            
            return Intent(
                type=IntentType.UNKNOWN,
                confidence=0.0,
                slots={},
                original_text=text,
                normalized_text=normalized_text
            )
            
        except Exception as e:
            logger.error(f"Erreur analyse intention '{text}': {e}")
            raise IntentParsingError(f"Erreur parsing intention: {e}")
    
    def _normalize_text(self, text: str) -> str:
        """
        Normalise le texte pour l'analyse.
        
        Args:
            text: Texte à normaliser
            
        Returns:
            Texte normalisé
        """
        # Nettoyer et normaliser
        normalized = text.strip().lower()
        
        # Remplacer les contractions françaises
        contractions = {
            "j'": "je ",
            "l'": "le ",
            "d'": "de ",
            "n'": "ne ",
            "m'": "me ",
            "t'": "te ",
            "s'": "se ",
            "qu'": "que ",
            "c'": "ce "
        }
        
        for contraction, replacement in contractions.items():
            normalized = normalized.replace(contraction, replacement)
        
        # Nettoyer les espaces multiples
        normalized = re.sub(r'\s+', ' ', normalized)
        
        return normalized
    
    def _match_pattern(self, text: str, pattern: IntentPattern) -> Optional[Tuple[IntentType, float, Dict[str, str]]]:
        """
        Teste si un pattern correspond au texte.
        
        Args:
            text: Texte normalisé
            pattern: Pattern à tester
            
        Returns:
            Tuple (intent_type, confidence, slots) ou None
        """
        confidence = 0.0
        slots = {}
        
        # Tester les patterns regex
        regex_match = False
        for regex in pattern.patterns:
            match = regex.search(text)
            if match:
                regex_match = True
                confidence += 0.7
                
                # Extraire les groupes capturés comme slots potentiels
                if match.groups():
                    if pattern.intent_type == IntentType.OPEN_APP or pattern.intent_type == IntentType.FOCUS_APP:
                        slots["app_name"] = match.group(1).strip()
                    elif pattern.intent_type == IntentType.CLICK_TEXT or pattern.intent_type == IntentType.TYPE_TEXT:
                        slots["text"] = match.group(1).strip()
                    elif pattern.intent_type == IntentType.WEB_SEARCH:
                        slots["query"] = match.group(1).strip()
                    elif pattern.intent_type == IntentType.WRITE_TEXT_FILE:
                        slots["content"] = match.group(1).strip()
                    elif pattern.intent_type == IntentType.SAVE_FILE and match.group(1):
                        slots["path"] = match.group(1).strip()
                
                break
        
        # Tester les mots-clés si pas de match regex
        if not regex_match:
            keyword_matches = sum(1 for keyword in pattern.keywords if keyword in text)
            if keyword_matches > 0:
                confidence += (keyword_matches / len(pattern.keywords)) * 0.5
        
        # Seuil minimum de confiance
        if confidence < 0.3:
            return None
        
        # Bonus pour les patterns de priorité plus élevée
        confidence += (pattern.priority - 1) * 0.1
        
        # Limiter la confiance à 1.0
        confidence = min(confidence, 1.0)
        
        return (pattern.intent_type, confidence, slots)
    
    def get_intent_suggestions(self, text: str, limit: int = 3) -> List[Intent]:
        """
        Retourne plusieurs suggestions d'intentions possibles.
        
        Args:
            text: Texte à analyser
            limit: Nombre maximum de suggestions
            
        Returns:
            Liste des intentions possibles triées par confiance
        """
        normalized_text = self._normalize_text(text)
        suggestions = []
        
        for pattern in self._patterns:
            match_result = self._match_pattern(normalized_text, pattern)
            
            if match_result:
                intent_type, confidence, raw_slots = match_result
                
                intent = Intent(
                    type=intent_type,
                    confidence=confidence,
                    slots=raw_slots,
                    original_text=text,
                    normalized_text=normalized_text
                )
                
                suggestions.append(intent)
        
        # Trier par confiance décroissante
        suggestions.sort(key=lambda x: x.confidence, reverse=True)
        
        return suggestions[:limit]
    
    def add_custom_pattern(self, pattern: IntentPattern) -> None:
        """
        Ajoute un pattern personnalisé.
        
        Args:
            pattern: Pattern à ajouter
        """
        self._patterns.append(pattern)
        
        # Re-trier par priorité
        self._patterns.sort(key=lambda p: p.priority, reverse=True)
        
        logger.info(f"Pattern personnalisé ajouté pour {pattern.intent_type.value}")
    
    def get_supported_intents(self) -> List[Dict[str, any]]:
        """
        Retourne la liste des intentions supportées.
        
        Returns:
            Liste des intentions avec leurs patterns
        """
        intents_info = {}
        
        for pattern in self._patterns:
            intent_type = pattern.intent_type.value
            
            if intent_type not in intents_info:
                intents_info[intent_type] = {
                    "type": intent_type,
                    "keywords": [],
                    "examples": [],
                    "required_slots": pattern.required_slots,
                    "priority": pattern.priority
                }
            
            intents_info[intent_type]["keywords"].extend(pattern.keywords)
        
        # Générer des exemples basiques
        examples = {
            IntentType.OPEN_APP.value: ["Ouvre Google Chrome", "Lance Notepad"],
            IntentType.FOCUS_APP.value: ["Va sur Chrome", "Focus sur Notepad"],
            IntentType.CLICK_TEXT.value: ["Clique sur OK", "Appuie sur Enregistrer"],
            IntentType.TYPE_TEXT.value: ["Écris Bonjour", "Tape mon email"],
            IntentType.SAVE_FILE.value: ["Sauvegarde le fichier", "Enregistre"],
            IntentType.WEB_SEARCH.value: ["Recherche Python", "Google intelligence artificielle"],
            IntentType.WRITE_TEXT_FILE.value: ["Crée un fichier et écris Bonjour", "Nouveau fichier avec du texte"]
        }
        
        for intent_type, info in intents_info.items():
            info["examples"] = examples.get(intent_type, [])
            # Dédupliquer les mots-clés
            info["keywords"] = list(set(info["keywords"]))
        
        return list(intents_info.values())
    
    def test_intent_parsing(self, test_cases: List[Tuple[str, IntentType]]) -> Dict[str, any]:
        """
        Teste l'analyseur avec des cas de test.
        
        Args:
            test_cases: Liste de (texte, intention_attendue)
            
        Returns:
            Résultats des tests
        """
        results = {
            "total": len(test_cases),
            "correct": 0,
            "incorrect": 0,
            "details": []
        }
        
        for text, expected_intent in test_cases:
            try:
                parsed_intent = self.parse_intent(text)
                is_correct = parsed_intent.type == expected_intent
                
                if is_correct:
                    results["correct"] += 1
                else:
                    results["incorrect"] += 1
                
                results["details"].append({
                    "text": text,
                    "expected": expected_intent.value,
                    "actual": parsed_intent.type.value,
                    "confidence": parsed_intent.confidence,
                    "correct": is_correct
                })
                
            except Exception as e:
                results["incorrect"] += 1
                results["details"].append({
                    "text": text,
                    "expected": expected_intent.value,
                    "actual": "ERROR",
                    "confidence": 0.0,
                    "correct": False,
                    "error": str(e)
                })
        
        results["accuracy"] = results["correct"] / results["total"] if results["total"] > 0 else 0.0
        
        return results