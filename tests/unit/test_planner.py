"""Tests unitaires pour le module Planner."""

import pytest

from packages.planner.plan_generator import PlanGenerator
from packages.planner.guardrails import GuardrailsManager
from packages.planner.planner_manager import PlannerManager
from packages.common.models import Intent, IntentType, Plan, Action, ActionType


class TestPlanGenerator:
    """Tests pour PlanGenerator."""
    
    def test_generate_open_app_plan(self, test_config):
        """Test de génération de plan pour open_app."""
        generator = PlanGenerator(test_config)
        
        intent = Intent(
            type=IntentType.OPEN_APP,
            slots={"app_name": "chrome"},
            confidence=0.9,
            original_text="ouvre chrome"
        )
        
        plan = generator.generate_plan(intent)
        
        assert isinstance(plan, Plan)
        assert len(plan.actions) >= 1
        assert plan.actions[0].type == ActionType.OPEN_APP
        assert plan.actions[0].parameters["app_name"] == "chrome"
        assert plan.confidence > 0.8
    
    def test_generate_write_file_plan(self, test_config):
        """Test de génération de plan pour write_file."""
        generator = PlanGenerator(test_config)
        
        intent = Intent(
            type=IntentType.WRITE_FILE,
            slots={"content": "hello world", "filename": "test.txt"},
            confidence=0.8,
            original_text="écris hello world dans test.txt"
        )
        
        plan = generator.generate_plan(intent)
        
        assert isinstance(plan, Plan)
        assert len(plan.actions) >= 2  # Au moins ouvrir éditeur + écrire
        
        # Vérifier les actions
        action_types = [action.type for action in plan.actions]
        assert ActionType.OPEN_APP in action_types  # Ouvrir éditeur
        assert ActionType.TYPE_TEXT in action_types  # Taper le texte
    
    def test_generate_web_search_plan(self, test_config):
        """Test de génération de plan pour web_search."""
        generator = PlanGenerator(test_config)
        
        intent = Intent(
            type=IntentType.WEB_SEARCH,
            slots={"query": "python programming"},
            confidence=0.85,
            original_text="recherche python programming"
        )
        
        plan = generator.generate_plan(intent)
        
        assert isinstance(plan, Plan)
        assert len(plan.actions) >= 3  # Ouvrir navigateur + naviguer + chercher
        
        # Vérifier qu'on ouvre un navigateur
        assert any(action.type == ActionType.OPEN_APP for action in plan.actions)
    
    def test_generate_unknown_intent_plan(self, test_config):
        """Test de génération de plan pour intent inconnu."""
        generator = PlanGenerator(test_config)
        
        intent = Intent(
            type=IntentType.UNKNOWN,
            slots={},
            confidence=0.3,
            original_text="commande incompréhensible"
        )
        
        plan = generator.generate_plan(intent)
        
        assert isinstance(plan, Plan)
        assert len(plan.actions) == 0  # Pas d'actions pour intent inconnu
        assert plan.confidence < 0.5


class TestGuardrailsManager:
    """Tests pour GuardrailsManager."""
    
    def test_safe_file_write_plan(self, test_config):
        """Test de validation d'un plan d'écriture de fichier sûr."""
        guardrails = GuardrailsManager(test_config)
        
        plan = Plan(
            intent_type=IntentType.WRITE_FILE,
            actions=[
                Action(
                    type=ActionType.OPEN_APP,
                    parameters={"app_name": "notepad"},
                    timestamp=0
                ),
                Action(
                    type=ActionType.TYPE_TEXT,
                    parameters={"text": "hello world"},
                    timestamp=0
                ),
                Action(
                    type=ActionType.SAVE_FILE,
                    parameters={"path": "Documents/test.txt"},
                    timestamp=0
                )
            ],
            confidence=0.9,
            description="Écrire hello world dans un fichier"
        )
        
        result = guardrails.validate_plan(plan)
        
        assert result.is_safe
        assert result.requires_confirmation is False
        assert len(result.warnings) == 0
    
    def test_unsafe_file_write_plan(self, test_config):
        """Test de validation d'un plan d'écriture de fichier dangereux."""
        guardrails = GuardrailsManager(test_config)
        
        plan = Plan(
            intent_type=IntentType.WRITE_FILE,
            actions=[
                Action(
                    type=ActionType.SAVE_FILE,
                    parameters={"path": "C:/Windows/System32/critical.dll"},
                    timestamp=0
                )
            ],
            confidence=0.8,
            description="Écrire dans un fichier système"
        )
        
        result = guardrails.validate_plan(plan)
        
        assert result.is_safe is False
        assert result.requires_confirmation is True
        assert len(result.warnings) > 0
        assert "système" in result.warnings[0].lower()
    
    def test_confirmation_required_plan(self, test_config):
        """Test de validation d'un plan nécessitant confirmation."""
        guardrails = GuardrailsManager(test_config)
        
        plan = Plan(
            intent_type=IntentType.WRITE_FILE,
            actions=[
                Action(
                    type=ActionType.SAVE_FILE,
                    parameters={"path": "Desktop/important.txt"},
                    timestamp=0
                )
            ],
            confidence=0.6,  # Confiance faible
            description="Écrire sur le bureau"
        )
        
        result = guardrails.validate_plan(plan)
        
        assert result.is_safe is True
        assert result.requires_confirmation is True  # À cause de la faible confiance


class TestPlannerManager:
    """Tests pour PlannerManager."""
    
    @pytest.mark.asyncio
    async def test_create_plan_from_intent(self, test_config):
        """Test de création de plan à partir d'un intent."""
        planner = PlannerManager(test_config)
        await planner.initialize()
        
        intent = Intent(
            type=IntentType.OPEN_APP,
            slots={"app_name": "notepad"},
            confidence=0.9,
            original_text="ouvre notepad"
        )
        
        plan = await planner.create_plan(intent)
        
        assert isinstance(plan, Plan)
        assert plan.intent_type == IntentType.OPEN_APP
        assert len(plan.actions) > 0
        assert plan.confidence > 0.8
    
    @pytest.mark.asyncio
    async def test_validate_plan_safety(self, test_config):
        """Test de validation de sécurité d'un plan."""
        planner = PlannerManager(test_config)
        await planner.initialize()
        
        # Plan sûr
        safe_intent = Intent(
            type=IntentType.OPEN_APP,
            slots={"app_name": "chrome"},
            confidence=0.9,
            original_text="ouvre chrome"
        )
        
        safe_plan = await planner.create_plan(safe_intent)
        validation = await planner.validate_plan(safe_plan)
        
        assert validation.is_safe
        assert not validation.requires_confirmation
    
    @pytest.mark.asyncio
    async def test_plan_execution_order(self, test_config):
        """Test de l'ordre d'exécution des actions dans un plan."""
        planner = PlannerManager(test_config)
        await planner.initialize()
        
        intent = Intent(
            type=IntentType.WRITE_FILE,
            slots={"content": "test content", "filename": "test.txt"},
            confidence=0.8,
            original_text="écris test content dans test.txt"
        )
        
        plan = await planner.create_plan(intent)
        
        # Vérifier que les actions sont dans l'ordre logique
        action_types = [action.type for action in plan.actions]
        
        # On devrait d'abord ouvrir l'application, puis taper le texte
        if ActionType.OPEN_APP in action_types and ActionType.TYPE_TEXT in action_types:
            open_index = action_types.index(ActionType.OPEN_APP)
            type_index = action_types.index(ActionType.TYPE_TEXT)
            assert open_index < type_index
    
    @pytest.mark.asyncio
    async def test_cleanup(self, test_config):
        """Test de nettoyage des ressources."""
        planner = PlannerManager(test_config)
        await planner.initialize()
        await planner.cleanup()
        
        # Vérifier que le manager peut être réinitialisé
        await planner.initialize()
        
        intent = Intent(
            type=IntentType.OPEN_APP,
            slots={"app_name": "test"},
            confidence=0.8,
            original_text="test"
        )
        
        plan = await planner.create_plan(intent)
        assert plan is not None