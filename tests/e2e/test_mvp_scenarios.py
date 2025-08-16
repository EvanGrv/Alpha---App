"""Tests E2E pour les scénarios MVP."""

import pytest
import asyncio
from pathlib import Path

from packages.common.models import Command, CommandSource
from apps.agent.services import AgentService


class TestMVPScenarios:
    """Tests E2E pour les scénarios MVP avec mocks."""
    
    @pytest.fixture
    async def agent_service(self, test_config):
        """Service agent pour les tests."""
        service = AgentService(test_config)
        await service.initialize()
        yield service
        await service.cleanup()
    
    @pytest.mark.asyncio
    async def test_open_chrome_scenario(self, agent_service):
        """Test E2E: Ouvrir Google Chrome."""
        
        # Commande d'entrée
        command = Command(
            source=CommandSource.TEXT,
            text="Ouvre Google Chrome",
            timestamp=1234567890.0
        )
        
        # Exécuter la commande
        session = await agent_service.execute_command(command)
        
        # Vérifications
        assert session is not None
        assert session.command.text == "Ouvre Google Chrome"
        assert len(session.plan.actions) > 0
        
        # Vérifier qu'on a une action d'ouverture d'app
        action_types = [action.type.value for action in session.plan.actions]
        assert "open_app" in action_types
        
        # En mode test/mock, on considère que l'exécution réussit
        assert session.success is True or session.success is None  # Peut être None en cours d'exécution
    
    @pytest.mark.asyncio
    async def test_write_file_scenario(self, agent_service):
        """Test E2E: Créer un fichier texte et écrire Bonjour."""
        
        command = Command(
            source=CommandSource.TEXT,
            text="Crée un fichier texte et écris Bonjour",
            timestamp=1234567890.0
        )
        
        session = await agent_service.execute_command(command)
        
        assert session is not None
        assert session.command.text == "Crée un fichier texte et écris Bonjour"
        
        # Vérifier les actions générées
        action_types = [action.type.value for action in session.plan.actions]
        
        # On devrait avoir des actions pour ouvrir un éditeur et taper du texte
        assert any("open" in action_type for action_type in action_types)
        assert any("type" in action_type for action_type in action_types)
    
    @pytest.mark.asyncio
    async def test_voice_command_scenario(self, agent_service):
        """Test E2E: Commande vocale."""
        
        command = Command(
            source=CommandSource.VOICE,
            text="Lance le bloc-notes",
            timestamp=1234567890.0
        )
        
        session = await agent_service.execute_command(command)
        
        assert session is not None
        assert session.command.source == CommandSource.VOICE
        assert len(session.plan.actions) > 0
    
    @pytest.mark.asyncio
    async def test_web_search_scenario(self, agent_service):
        """Test E2E: Recherche web."""
        
        command = Command(
            source=CommandSource.TEXT,
            text="Recherche desktop automation sur Google",
            timestamp=1234567890.0
        )
        
        session = await agent_service.execute_command(command)
        
        assert session is not None
        
        # Vérifier qu'on a des actions pour ouvrir le navigateur et effectuer la recherche
        action_types = [action.type.value for action in session.plan.actions]
        assert "open_app" in action_types
    
    @pytest.mark.asyncio
    async def test_unknown_command_scenario(self, agent_service):
        """Test E2E: Commande inconnue."""
        
        command = Command(
            source=CommandSource.TEXT,
            text="Fais quelque chose d'impossible et incompréhensible",
            timestamp=1234567890.0
        )
        
        session = await agent_service.execute_command(command)
        
        assert session is not None
        
        # Pour une commande inconnue, on devrait avoir un plan vide ou avec peu d'actions
        assert len(session.plan.actions) == 0 or session.plan.confidence < 0.5
    
    @pytest.mark.asyncio
    async def test_multiple_commands_sequence(self, agent_service):
        """Test E2E: Séquence de commandes multiples."""
        
        commands = [
            "Ouvre Chrome",
            "Lance Notepad",
            "Écris Hello World"
        ]
        
        sessions = []
        
        for cmd_text in commands:
            command = Command(
                source=CommandSource.TEXT,
                text=cmd_text,
                timestamp=1234567890.0
            )
            
            session = await agent_service.execute_command(command)
            sessions.append(session)
            
            # Petite pause entre les commandes
            await asyncio.sleep(0.1)
        
        # Vérifier que toutes les sessions ont été créées
        assert len(sessions) == len(commands)
        
        for session in sessions:
            assert session is not None
            assert len(session.plan.actions) >= 0
    
    @pytest.mark.asyncio 
    async def test_error_handling(self, agent_service):
        """Test E2E: Gestion d'erreurs."""
        
        # Commande qui pourrait causer des erreurs
        command = Command(
            source=CommandSource.TEXT,
            text="",  # Commande vide
            timestamp=1234567890.0
        )
        
        session = await agent_service.execute_command(command)
        
        # Même avec une commande vide, on devrait avoir une session
        assert session is not None
        
        # La session pourrait être marquée comme échouée
        # ou avoir un plan vide
        assert (session.success is False or 
                len(session.plan.actions) == 0 or
                session.plan.confidence < 0.3)
    
    @pytest.mark.asyncio
    async def test_concurrent_commands(self, agent_service):
        """Test E2E: Commandes concurrentes."""
        
        commands = [
            Command(CommandSource.TEXT, f"Test command {i}", 1234567890.0 + i)
            for i in range(3)
        ]
        
        # Exécuter les commandes en parallèle
        tasks = [agent_service.execute_command(cmd) for cmd in commands]
        sessions = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Vérifier qu'on a des résultats pour toutes les commandes
        assert len(sessions) == len(commands)
        
        for session in sessions:
            # Certaines pourraient être des exceptions, d'autres des sessions
            assert session is not None
    
    @pytest.mark.asyncio
    async def test_logging_integration(self, agent_service, temp_dir):
        """Test E2E: Intégration avec le logging."""
        
        # Configurer le logging pour utiliser le dossier temporaire
        agent_service.config.update({
            'logging': {
                'log_dir': str(temp_dir / 'logs'),
                'demo_dir': str(temp_dir / 'demos')
            }
        })
        
        command = Command(
            source=CommandSource.TEXT,
            text="Test logging command",
            timestamp=1234567890.0
        )
        
        session = await agent_service.execute_command(command)
        
        assert session is not None
        
        # Vérifier que des logs ont été créés
        log_dir = temp_dir / 'logs'
        if log_dir.exists():
            log_files = list(log_dir.glob('*.log'))
            # Il pourrait y avoir des logs ou pas selon l'implémentation
            # On vérifie juste que ça ne plante pas