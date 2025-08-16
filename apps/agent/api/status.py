"""
Endpoints pour le statut et les informations système.

Fournit des informations sur l'état de l'agent et ses composants.
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

from packages.common.logging_utils import get_agent_logger

logger = get_agent_logger()

router = APIRouter(tags=["status"])


class SystemStatus(BaseModel):
    """Statut complet du système."""
    service: Dict[str, Any] = Field(..., description="État du service principal")
    active_sessions: int = Field(..., description="Nombre de sessions actives")
    components: Dict[str, Any] = Field(..., description="État des composants")
    system: Dict[str, Any] = Field(..., description="Informations système")


class ObservationResponse(BaseModel):
    """Réponse d'observation du bureau."""
    timestamp: str = Field(..., description="Timestamp de l'observation")
    screenshot: Dict[str, Any] = Field(..., description="Informations capture d'écran")
    ui_elements_count: int = Field(..., description="Nombre d'éléments UI détectés")
    text_matches_count: int = Field(..., description="Nombre de textes OCR trouvés")
    active_window: Optional[Dict[str, Any]] = Field(None, description="Fenêtre active")
    mouse_position: tuple = Field(..., description="Position de la souris")
    platform: str = Field(..., description="Plateforme OS")


@router.get("/status", response_model=SystemStatus)
async def get_system_status(http_request: Request):
    """
    Retourne le statut complet du système.
    
    Inclut l'état de tous les composants, statistiques et informations système.
    """
    try:
        # Récupérer le service agent
        agent_service = http_request.app.state.agent_service
        
        # Obtenir le statut complet
        status = await agent_service.get_system_status()
        
        return SystemStatus(**status)
        
    except Exception as e:
        logger.error(f"Erreur récupération statut: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur récupération statut: {str(e)}"
        )


@router.get("/observation", response_model=ObservationResponse)
async def get_current_observation(http_request: Request):
    """
    Retourne l'observation actuelle du bureau.
    
    Inclut la capture d'écran, éléments UI détectés et informations contextuelles.
    """
    try:
        # Récupérer le service agent
        agent_service = http_request.app.state.agent_service
        
        # Obtenir l'observation
        observation = await agent_service.get_current_observation()
        
        if "error" in observation:
            raise HTTPException(
                status_code=500,
                detail=observation["error"]
            )
        
        return ObservationResponse(**observation)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur récupération observation: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur récupération observation: {str(e)}"
        )


@router.get("/components")
async def get_components_info(http_request: Request):
    """
    Retourne des informations détaillées sur tous les composants.
    
    Utile pour le debugging et le monitoring.
    """
    try:
        # Récupérer le service agent
        agent_service = http_request.app.state.agent_service
        
        components_info = {
            "nlu": {
                "stats": agent_service.nlu_manager.get_nlu_stats(),
                "supported_commands": agent_service.nlu_manager.get_supported_commands()
            },
            "planner": {
                "stats": agent_service.planner_manager.get_planner_stats(),
                "security_summary": agent_service.planner_manager.guardrails.get_security_summary()
            },
            "skills": {
                "stats": agent_service.skill_manager.get_manager_stats(),
                "available_skills": agent_service.skill_manager.get_all_skills_info()
            },
            "perception": {
                "stats": agent_service.perception_manager.get_performance_stats(),
                "monitors": agent_service.perception_manager.screen_capture.get_monitors_info()
            }
        }
        
        return components_info
        
    except Exception as e:
        logger.error(f"Erreur récupération composants: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur récupération composants: {str(e)}"
        )


@router.get("/skills")
async def get_skills_info(http_request: Request):
    """
    Retourne des informations détaillées sur les compétences disponibles.
    """
    try:
        # Récupérer le service agent
        agent_service = http_request.app.state.agent_service
        
        skills_info = agent_service.skill_manager.get_all_skills_info()
        
        return {
            "total_skills": len(skills_info),
            "skills": skills_info
        }
        
    except Exception as e:
        logger.error(f"Erreur récupération skills: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur récupération skills: {str(e)}"
        )


@router.get("/skills/{skill_name}")
async def get_skill_info(skill_name: str, http_request: Request):
    """
    Retourne des informations détaillées sur une compétence spécifique.
    """
    try:
        # Récupérer le service agent
        agent_service = http_request.app.state.agent_service
        
        skill_info = agent_service.skill_manager.get_skill_info(skill_name)
        
        if not skill_info:
            raise HTTPException(
                status_code=404,
                detail=f"Compétence '{skill_name}' non trouvée"
            )
        
        return skill_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur récupération skill {skill_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur récupération skill: {str(e)}"
        )


@router.post("/skills/{skill_name}/test")
async def test_skill(skill_name: str, http_request: Request):
    """
    Teste une compétence avec des paramètres par défaut.
    """
    try:
        # Récupérer le service agent
        agent_service = http_request.app.state.agent_service
        
        # Tester la compétence
        test_result = await agent_service.skill_manager.test_skill(skill_name)
        
        return {
            "skill_name": skill_name,
            "test_passed": test_result,
            "message": f"Test {'réussi' if test_result else 'échoué'}"
        }
        
    except Exception as e:
        logger.error(f"Erreur test skill {skill_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur test skill: {str(e)}"
        )


@router.get("/monitors")
async def get_monitors_info(http_request: Request):
    """
    Retourne des informations sur les moniteurs disponibles.
    """
    try:
        # Récupérer le service agent
        agent_service = http_request.app.state.agent_service
        
        monitors_info = agent_service.perception_manager.screen_capture.get_monitors_info()
        
        return {
            "monitors_count": len(monitors_info),
            "monitors": monitors_info
        }
        
    except Exception as e:
        logger.error(f"Erreur récupération moniteurs: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur récupération moniteurs: {str(e)}"
        )


@router.get("/ui-elements")
async def get_ui_elements(window_id: Optional[str] = None, http_request: Request = None):
    """
    Retourne les éléments UI actuellement visibles.
    
    Utile pour le debugging et l'inspection de l'interface.
    """
    try:
        # Récupérer le service agent
        agent_service = http_request.app.state.agent_service
        
        # Obtenir les éléments UI
        ui_elements = agent_service.perception_manager.accessibility_fusion.get_unified_ui_elements(
            window_id=window_id,
            include_ocr=True
        )
        
        # Formater pour l'API
        elements_data = []
        for element in ui_elements[:50]:  # Limiter à 50 éléments
            elements_data.append({
                "id": element.id,
                "name": element.name,
                "role": element.role.value,
                "bounds": {
                    "x": element.bounds.x,
                    "y": element.bounds.y,
                    "width": element.bounds.width,
                    "height": element.bounds.height
                },
                "text": element.text,
                "enabled": element.enabled,
                "visible": element.visible
            })
        
        return {
            "total_elements": len(ui_elements),
            "displayed_elements": len(elements_data),
            "window_id": window_id,
            "elements": elements_data
        }
        
    except Exception as e:
        logger.error(f"Erreur récupération éléments UI: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur récupération éléments UI: {str(e)}"
        )


@router.post("/cache/clear")
async def clear_caches(http_request: Request):
    """
    Vide tous les caches du système.
    
    Utile pour le debugging et la gestion de la mémoire.
    """
    try:
        # Récupérer le service agent
        agent_service = http_request.app.state.agent_service
        
        # Vider les caches
        agent_service.perception_manager.clear_all_caches()
        agent_service.planner_manager.clear_plan_cache()
        
        return {
            "success": True,
            "message": "Tous les caches ont été vidés"
        }
        
    except Exception as e:
        logger.error(f"Erreur vidage caches: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur vidage caches: {str(e)}"
        )


@router.post("/stats/reset")
async def reset_statistics(http_request: Request):
    """
    Remet à zéro toutes les statistiques.
    """
    try:
        # Récupérer le service agent
        agent_service = http_request.app.state.agent_service
        
        # Reset des statistiques
        agent_service.nlu_manager.reset_stats()
        agent_service.planner_manager.reset_stats()
        agent_service.skill_manager.reset_all_stats()
        
        return {
            "success": True,
            "message": "Toutes les statistiques ont été remises à zéro"
        }
        
    except Exception as e:
        logger.error(f"Erreur reset statistiques: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur reset statistiques: {str(e)}"
        )