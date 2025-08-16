"""Configuration pytest pour les tests."""

import pytest
import asyncio
from pathlib import Path
import tempfile
import shutil

from packages.common.config import Config


@pytest.fixture(scope="session")
def event_loop():
    """Crée un event loop pour les tests async."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir():
    """Crée un dossier temporaire pour les tests."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def test_config(temp_dir):
    """Configuration de test."""
    config_data = {
        'app': {
            'name': 'desktop-agent-test',
            'version': '0.1.0-test',
            'debug': True
        },
        'logging': {
            'level': 'DEBUG',
            'log_dir': str(temp_dir / 'logs'),
            'demo_dir': str(temp_dir / 'demos')
        },
        'perception': {
            'screenshot_dir': str(temp_dir / 'screenshots'),
            'ocr_enabled': False  # Désactiver OCR pour les tests
        },
        'skills': {
            'timeout': 1.0  # Timeout court pour les tests
        }
    }
    
    return Config(config_data)


@pytest.fixture
def sample_screenshot(temp_dir):
    """Crée un screenshot de test."""
    from PIL import Image
    import numpy as np
    
    # Créer une image de test
    img_array = np.random.randint(0, 256, (100, 200, 3), dtype=np.uint8)
    img = Image.fromarray(img_array)
    
    screenshot_path = temp_dir / 'test_screenshot.png'
    img.save(screenshot_path)
    
    return screenshot_path


@pytest.fixture
def mock_ui_elements():
    """Éléments UI de test."""
    from packages.common.models import UiObject
    
    return [
        UiObject(
            name="Test Button",
            role="button",
            bounds=[100, 200, 50, 30],
            text="Click me",
            enabled=True,
            visible=True
        ),
        UiObject(
            name="Test Input",
            role="textbox",
            bounds=[150, 250, 200, 25],
            text="",
            enabled=True,
            visible=True
        )
    ]


@pytest.fixture
def mock_observation(sample_screenshot, mock_ui_elements):
    """Observation de test."""
    from packages.common.models import Observation, OCRResult
    
    return Observation(
        timestamp=1234567890.0,
        screenshot_path=str(sample_screenshot),
        ui_elements=mock_ui_elements,
        ocr_results=[
            OCRResult(
                text="Sample text",
                bounds=[10, 20, 100, 15],
                confidence=0.95
            )
        ],
        active_window="Test Window",
        mouse_position=[300, 400],
        step_count=1,
        last_action_success=True
    )