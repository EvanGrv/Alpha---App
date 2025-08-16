"""
Adaptateurs OS pour Desktop Agent.

Fournit une interface unifiée pour les opérations système sur différentes plateformes.
"""

import sys
from typing import Type

from ..common.models import Platform
from .base import OSAdapter

# Import conditionnel selon la plateforme
if sys.platform == "win32":
    from .win.adapter import WindowsAdapter as PlatformAdapter
elif sys.platform == "darwin":
    from .mac.adapter import MacOSAdapter as PlatformAdapter
else:
    from .linux.adapter import LinuxAdapter as PlatformAdapter


def get_os_adapter() -> OSAdapter:
    """
    Retourne l'adaptateur OS approprié pour la plateforme actuelle.
    
    Returns:
        Instance de l'adaptateur OS
    """
    return PlatformAdapter()


def get_platform() -> Platform:
    """
    Détermine la plateforme actuelle.
    
    Returns:
        Plateforme détectée
    """
    if sys.platform == "win32":
        return Platform.WINDOWS
    elif sys.platform == "darwin":
        return Platform.MACOS
    else:
        return Platform.LINUX


__all__ = ["OSAdapter", "get_os_adapter", "get_platform", "PlatformAdapter"]