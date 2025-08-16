"""
Modules API pour Desktop Agent.

Contient tous les endpoints et routes de l'API.
"""

from .command import router as command_router
from .status import router as status_router
from .websocket import router as websocket_router

__all__ = ["command_router", "status_router", "websocket_router"]