"""Tests unitaires pour le module common."""

import pytest
from pathlib import Path
import tempfile

from packages.common.config import Config
from packages.common.models import *
from packages.common.errors import *
from packages.common.retry import retry_async, RetryConfig


class TestConfig:
    """Tests pour Config."""
    
    def test_config_from_dict(self):
        """Test de création de config depuis un dictionnaire."""
        config_data = {
            'app': {'name': 'test-app', 'version': '1.0.0'},
            'database': {'url': 'sqlite:///test.db'}
        }
        
        config = Config(config_data)
        
        assert config.get('app.name') == 'test-app'
        assert config.get('app.version') == '1.0.0'
        assert config.get('database.url') == 'sqlite:///test.db'
    
    def test_config_default_values(self):
        """Test des valeurs par défaut."""
        config = Config()
        
        # Vérifier quelques valeurs par défaut
        assert config.get('nonexistent.key', 'default') == 'default'
        assert config.get('app.name', 'desktop-agent') == 'desktop-agent'
    
    def test_config_nested_access(self):
        """Test d'accès aux valeurs imbriquées."""
        config_data = {
            'level1': {
                'level2': {
                    'level3': 'deep_value'
                }
            }
        }
        
        config = Config(config_data)
        
        assert config.get('level1.level2.level3') == 'deep_value'
        assert config.get('level1.level2.nonexistent') is None
        assert config.get('level1.level2.nonexistent', 'default') == 'default'


class TestModels:
    """Tests pour les modèles Pydantic."""
    
    def test_ui_object_creation(self):
        """Test de création d'UiObject."""
        ui_obj = UiObject(
            name="Test Button",
            role="button",
            bounds=[10, 20, 100, 30],
            text="Click me",
            enabled=True,
            visible=True
        )
        
        assert ui_obj.name == "Test Button"
        assert ui_obj.role == "button"
        assert ui_obj.bounds == [10, 20, 100, 30]
        assert ui_obj.enabled is True
        assert ui_obj.visible is True
    
    def test_observation_creation(self, sample_screenshot, mock_ui_elements):
        """Test de création d'Observation."""
        obs = Observation(
            timestamp=1234567890.0,
            screenshot_path=str(sample_screenshot),
            ui_elements=mock_ui_elements,
            ocr_results=[],
            active_window="Test Window",
            mouse_position=[100, 200],
            step_count=5,
            last_action_success=True
        )
        
        assert obs.timestamp == 1234567890.0
        assert obs.active_window == "Test Window"
        assert obs.mouse_position == [100, 200]
        assert obs.step_count == 5
        assert obs.last_action_success is True
        assert len(obs.ui_elements) == len(mock_ui_elements)
    
    def test_action_creation(self):
        """Test de création d'Action."""
        action = Action(
            type=ActionType.CLICK,
            parameters={"x": 100, "y": 200, "button": "left"},
            timestamp=1234567890.0
        )
        
        assert action.type == ActionType.CLICK
        assert action.parameters["x"] == 100
        assert action.parameters["y"] == 200
        assert action.timestamp == 1234567890.0
    
    def test_intent_creation(self):
        """Test de création d'Intent."""
        intent = Intent(
            type=IntentType.OPEN_APP,
            slots={"app_name": "chrome"},
            confidence=0.95,
            original_text="ouvre chrome"
        )
        
        assert intent.type == IntentType.OPEN_APP
        assert intent.slots["app_name"] == "chrome"
        assert intent.confidence == 0.95
        assert intent.original_text == "ouvre chrome"
    
    def test_plan_creation(self):
        """Test de création de Plan."""
        actions = [
            Action(
                type=ActionType.OPEN_APP,
                parameters={"app_name": "chrome"},
                timestamp=0
            ),
            Action(
                type=ActionType.WAIT,
                parameters={"duration": 2.0},
                timestamp=0
            )
        ]
        
        plan = Plan(
            intent_type=IntentType.OPEN_APP,
            actions=actions,
            confidence=0.9,
            description="Ouvrir Chrome et attendre"
        )
        
        assert plan.intent_type == IntentType.OPEN_APP
        assert len(plan.actions) == 2
        assert plan.confidence == 0.9
        assert "Chrome" in plan.description


class TestErrors:
    """Tests pour les erreurs personnalisées."""
    
    def test_desktop_agent_error(self):
        """Test de DesktopAgentError."""
        with pytest.raises(DesktopAgentError) as exc_info:
            raise DesktopAgentError("Test error message")
        
        assert str(exc_info.value) == "Test error message"
    
    def test_perception_error(self):
        """Test de PerceptionError."""
        with pytest.raises(PerceptionError) as exc_info:
            raise PerceptionError("Perception failed")
        
        assert str(exc_info.value) == "Perception failed"
        assert isinstance(exc_info.value, DesktopAgentError)
    
    def test_skill_execution_error(self):
        """Test de SkillExecutionError."""
        with pytest.raises(SkillExecutionError) as exc_info:
            raise SkillExecutionError("Skill failed", skill_name="test_skill")
        
        error = exc_info.value
        assert str(error) == "Skill failed"
        assert error.skill_name == "test_skill"


class TestRetry:
    """Tests pour le système de retry."""
    
    @pytest.mark.asyncio
    async def test_retry_success_on_first_attempt(self):
        """Test de retry avec succès au premier essai."""
        call_count = 0
        
        @retry_async(RetryConfig(max_attempts=3, delay=0.1))
        async def successful_function():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = await successful_function()
        
        assert result == "success"
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_retry_success_after_failures(self):
        """Test de retry avec succès après quelques échecs."""
        call_count = 0
        
        @retry_async(RetryConfig(max_attempts=3, delay=0.1))
        async def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError(f"Attempt {call_count} failed")
            return "success"
        
        result = await flaky_function()
        
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_max_attempts_exceeded(self):
        """Test de retry avec dépassement du nombre max d'essais."""
        call_count = 0
        
        @retry_async(RetryConfig(max_attempts=2, delay=0.1))
        async def always_failing_function():
            nonlocal call_count
            call_count += 1
            raise ValueError(f"Attempt {call_count} failed")
        
        with pytest.raises(ValueError) as exc_info:
            await always_failing_function()
        
        assert call_count == 2
        assert "Attempt 2 failed" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_retry_with_specific_exceptions(self):
        """Test de retry avec exceptions spécifiques."""
        call_count = 0
        
        @retry_async(RetryConfig(
            max_attempts=3, 
            delay=0.1, 
            exceptions=(ValueError,)
        ))
        async def selective_retry_function():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Retryable error")
            elif call_count == 2:
                raise RuntimeError("Non-retryable error")
            return "success"
        
        with pytest.raises(RuntimeError):
            await selective_retry_function()
        
        assert call_count == 2  # Stopped at RuntimeError