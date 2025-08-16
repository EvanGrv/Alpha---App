"""
Package de perception pour Desktop Agent.

Fournit les capacités de capture d'écran, OCR et fusion d'accessibilité.
"""

from .screen_capture import ScreenCaptureService
from .ocr_service import OCRService  
from .accessibility_fusion import AccessibilityFusion
from .perception_manager import PerceptionManager

__all__ = [
    "ScreenCaptureService",
    "OCRService", 
    "AccessibilityFusion",
    "PerceptionManager"
]