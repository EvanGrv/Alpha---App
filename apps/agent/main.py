"""
Application FastAPI principale pour Desktop Agent.

Point d'entrée du service d'automatisation de bureau.
"""

import asyncio
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Ajouter le répertoire racine au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from packages.common.config import get_settings
from packages.common.logging_utils import setup_logging, get_agent_logger
from packages.skills import SkillManager
from packages.nlu import NLUManager
from packages.planner import PlannerManager
from packages.perception import PerceptionManager

from .api import command_router, status_router, websocket_router
from .services import AgentService

# Variables globales pour les services
agent_service: AgentService = None
logger = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestionnaire de cycle de vie de l'application."""
    global agent_service, logger
    
    try:
        # Configuration et logging
        settings = get_settings()
        setup_logging(settings.logging, "desktop-agent")
        logger = get_agent_logger()
        
        logger.info("Démarrage Desktop Agent API")
        
        # Initialisation des services
        skill_manager = SkillManager()
        nlu_manager = NLUManager()
        planner_manager = PlannerManager(skill_manager)
        perception_manager = PerceptionManager()
        
        # Service principal
        agent_service = AgentService(
            skill_manager=skill_manager,
            nlu_manager=nlu_manager,
            planner_manager=planner_manager,
            perception_manager=perception_manager
        )
        
        # Démarrer les services
        await agent_service.start()
        
        # Attacher le service à l'app pour l'accès dans les routes
        app.state.agent_service = agent_service
        
        logger.info(f"Desktop Agent API démarré sur {settings.api_host}:{settings.api_port}")
        
        yield
        
    except Exception as e:
        if logger:
            logger.error(f"Erreur démarrage application: {e}")
        raise
    finally:
        # Nettoyage
        if agent_service:
            await agent_service.stop()
        if logger:
            logger.info("Desktop Agent API arrêté")


# Création de l'application FastAPI
app = FastAPI(
    title="Desktop Agent API",
    description="API pour l'automatisation de bureau avec IA",
    version="0.1.0",
    lifespan=lifespan
)

# Configuration CORS
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Enregistrement des routers
app.include_router(command_router, prefix="/api/v1")
app.include_router(status_router, prefix="/api/v1")
app.include_router(websocket_router, prefix="/api/v1")


@app.get("/")
async def root():
    """Endpoint racine."""
    return {
        "name": "Desktop Agent API",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
        "websocket": "/api/v1/ws/events"
    }


@app.get("/health")
async def health_check():
    """Vérification de santé de l'API."""
    try:
        if not hasattr(app.state, 'agent_service') or not app.state.agent_service:
            return JSONResponse(
                status_code=503,
                content={"status": "unhealthy", "reason": "Agent service not initialized"}
            )
        
        health_status = await app.state.agent_service.get_health_status()
        
        return {
            "status": "healthy" if health_status["healthy"] else "unhealthy",
            "timestamp": health_status["timestamp"],
            "services": health_status["services"],
            "uptime": health_status["uptime"]
        }
        
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Gestionnaire d'exceptions global."""
    if logger:
        logger.error(f"Erreur non gérée: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc) if settings.debug else "Une erreur interne s'est produite"
        }
    )


if __name__ == "__main__":
    # Configuration pour le développement
    settings = get_settings()
    
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        log_level="info" if not settings.debug else "debug",
        access_log=True
    )