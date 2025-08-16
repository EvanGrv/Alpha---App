"""Tests unitaires pour le module NLU."""

import pytest

from packages.nlu.intent_parser import IntentParser
from packages.nlu.slot_extractor import SlotExtractor
from packages.nlu.nlu_manager import NLUManager
from packages.common.models import Intent, IntentType


class TestIntentParser:
    """Tests pour IntentParser."""
    
    def test_parse_open_app_intent(self, test_config):
        """Test de parsing d'intent open_app."""
        parser = IntentParser(test_config)
        
        # Test avec différentes formulations
        test_cases = [
            ("ouvre chrome", IntentType.OPEN_APP, {"app_name": "chrome"}),
            ("lance google chrome", IntentType.OPEN_APP, {"app_name": "google chrome"}),
            ("démarre notepad", IntentType.OPEN_APP, {"app_name": "notepad"}),
            ("ouvrir le bloc-notes", IntentType.OPEN_APP, {"app_name": "bloc-notes"})
        ]
        
        for text, expected_type, expected_slots in test_cases:
            intent = parser.parse_intent(text)
            
            assert intent.type == expected_type
            assert intent.confidence > 0.7
            for key, value in expected_slots.items():
                assert key in intent.slots
                assert intent.slots[key] == value
    
    def test_parse_write_file_intent(self, test_config):
        """Test de parsing d'intent write_file."""
        parser = IntentParser(test_config)
        
        test_cases = [
            ("écris bonjour dans un fichier", IntentType.WRITE_FILE, {"content": "bonjour"}),
            ("crée un fichier avec le texte hello", IntentType.WRITE_FILE, {"content": "hello"}),
            ("sauvegarde 'test content' dans un fichier", IntentType.WRITE_FILE, {"content": "test content"})
        ]
        
        for text, expected_type, expected_slots in test_cases:
            intent = parser.parse_intent(text)
            
            assert intent.type == expected_type
            assert intent.confidence > 0.6
            for key, value in expected_slots.items():
                assert key in intent.slots
                assert intent.slots[key] == value
    
    def test_parse_web_search_intent(self, test_config):
        """Test de parsing d'intent web_search."""
        parser = IntentParser(test_config)
        
        test_cases = [
            ("recherche python sur google", IntentType.WEB_SEARCH, {"query": "python"}),
            ("cherche desktop automation", IntentType.WEB_SEARCH, {"query": "desktop automation"}),
            ("google 'machine learning'", IntentType.WEB_SEARCH, {"query": "machine learning"})
        ]
        
        for text, expected_type, expected_slots in test_cases:
            intent = parser.parse_intent(text)
            
            assert intent.type == expected_type
            assert intent.confidence > 0.6
            for key, value in expected_slots.items():
                assert key in intent.slots
                assert intent.slots[key] == value
    
    def test_parse_unknown_intent(self, test_config):
        """Test de parsing d'intent inconnu."""
        parser = IntentParser(test_config)
        
        intent = parser.parse_intent("blah blah incomprehensible text")
        
        assert intent.type == IntentType.UNKNOWN
        assert intent.confidence < 0.5


class TestSlotExtractor:
    """Tests pour SlotExtractor."""
    
    def test_normalize_app_name(self, test_config):
        """Test de normalisation des noms d'application."""
        extractor = SlotExtractor(test_config)
        
        test_cases = [
            ("chrome", "chrome"),
            ("google chrome", "chrome"),
            ("bloc-notes", "notepad"),
            ("notepad", "notepad"),
            ("calculatrice", "calc"),
            ("explorer", "explorer")
        ]
        
        for input_name, expected in test_cases:
            result = extractor.normalize_app_name(input_name)
            assert result == expected
    
    def test_extract_file_content(self, test_config):
        """Test d'extraction de contenu de fichier."""
        extractor = SlotExtractor(test_config)
        
        test_cases = [
            ("écris 'hello world' dans un fichier", "hello world"),
            ("sauvegarde \"test content\" en fichier", "test content"),
            ("crée un fichier avec bonjour", "bonjour"),
            ("fichier texte: important message", "important message")
        ]
        
        for text, expected in test_cases:
            content = extractor.extract_file_content(text)
            assert content == expected
    
    def test_extract_search_query(self, test_config):
        """Test d'extraction de requête de recherche."""
        extractor = SlotExtractor(test_config)
        
        test_cases = [
            ("recherche python programming", "python programming"),
            ("google 'machine learning'", "machine learning"),
            ("cherche \"desktop automation\"", "desktop automation"),
            ("trouve des infos sur AI", "AI")
        ]
        
        for text, expected in test_cases:
            query = extractor.extract_search_query(text)
            assert query == expected


class TestNLUManager:
    """Tests pour NLUManager."""
    
    @pytest.mark.asyncio
    async def test_process_command(self, test_config):
        """Test de traitement de commande complète."""
        nlu_manager = NLUManager(test_config)
        await nlu_manager.initialize()
        
        # Test commande open app
        intent = await nlu_manager.process_command("ouvre chrome")
        
        assert intent.type == IntentType.OPEN_APP
        assert intent.confidence > 0.7
        assert "app_name" in intent.slots
        assert intent.slots["app_name"] == "chrome"
    
    @pytest.mark.asyncio
    async def test_process_multiple_commands(self, test_config):
        """Test de traitement de plusieurs commandes."""
        nlu_manager = NLUManager(test_config)
        await nlu_manager.initialize()
        
        commands = [
            "lance notepad",
            "écris hello dans un fichier",
            "recherche python sur google",
            "commande inconnue xyz"
        ]
        
        expected_types = [
            IntentType.OPEN_APP,
            IntentType.WRITE_FILE,
            IntentType.WEB_SEARCH,
            IntentType.UNKNOWN
        ]
        
        for command, expected_type in zip(commands, expected_types):
            intent = await nlu_manager.process_command(command)
            assert intent.type == expected_type
    
    @pytest.mark.asyncio
    async def test_cleanup(self, test_config):
        """Test de nettoyage des ressources."""
        nlu_manager = NLUManager(test_config)
        await nlu_manager.initialize()
        await nlu_manager.cleanup()
        
        # Vérifier que le manager peut être réinitialisé
        await nlu_manager.initialize()
        intent = await nlu_manager.process_command("test")
        assert intent is not None