"""
Endpoints pour les commandes utilisateur.

Gère l'exécution des commandes texte et vocales.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from packages.common.models import Command, CommandSource
from packages.common.logging_utils import get_agent_logger

logger = get_agent_logger()

router = APIRouter(tags=["commands"])


class CommandRequest(BaseModel):
    """Requête de commande."""
    source: CommandSource = Field(..., description="Source de la commande")
    text: str = Field(..., min_length=1, description="Texte de la commande")
    require_confirmation: bool = Field(default=False, description="Forcer la confirmation")
    user_id: Optional[str] = Field(None, description="ID utilisateur")
    session_id: Optional[str] = Field(None, description="ID de session")


class CommandResponse(BaseModel):
    """Réponse de commande."""
    success: bool = Field(..., description="Succès de la commande")
    stage: str = Field(..., description="Étape atteinte")
    message: str = Field(..., description="Message de résultat")
    command_id: str = Field(..., description="ID de la commande")
    duration: Optional[float] = Field(None, description="Durée d'exécution")
    
    # Données optionnelles selon l'étape
    plan_id: Optional[str] = Field(None, description="ID du plan généré")
    session_id: Optional[str] = Field(None, description="ID de session d'exécution")
    suggestions: Optional[Dict[str, Any]] = Field(None, description="Suggestions")
    warnings: Optional[list] = Field(None, description="Avertissements")


class ExecutePlanRequest(BaseModel):
    """Requête d'exécution de plan."""
    plan_id: str = Field(..., description="ID du plan à exécuter")
    command_id: Optional[str] = Field(None, description="ID de la commande d'origine")


@router.post("/command", response_model=CommandResponse)
async def execute_command(request: CommandRequest, http_request: Request):
    """
    Exécute une commande utilisateur.
    
    Cette endpoint traite une commande complète depuis l'analyse NLU
    jusqu'à l'exécution, en passant par la planification et les guardrails.
    """
    try:
        # Récupérer le service agent
        agent_service = http_request.app.state.agent_service
        
        # Créer la commande
        command = Command(
            source=request.source,
            text=request.text,
            user_id=request.user_id,
            session_id=request.session_id,
            require_confirmation=request.require_confirmation
        )
        
        logger.info(f"Nouvelle commande: '{command.text}' ({command.source.value})")
        
        # Traiter la commande
        result = await agent_service.process_command(
            command=command,
            require_confirmation=request.require_confirmation
        )
        
        # Construire la réponse
        response = CommandResponse(
            success=result["success"],
            stage=result["stage"],
            message=result["message"],
            command_id=command.id,
            duration=result.get("duration")
        )
        
        # Ajouter les données optionnelles
        if "plan_id" in result:
            response.plan_id = result["plan_id"]
        
        if "session_id" in result:
            response.session_id = result["session_id"]
        
        if "suggestions" in result:
            response.suggestions = result["suggestions"]
        
        if "warnings" in result:
            response.warnings = result["warnings"]
        
        return response
        
    except Exception as e:
        logger.error(f"Erreur exécution commande: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur traitement commande: {str(e)}"
        )


@router.post("/execute-plan", response_model=CommandResponse)
async def execute_plan(request: ExecutePlanRequest, http_request: Request):
    """
    Exécute un plan précédemment généré.
    
    Utilisé après confirmation utilisateur d'un plan nécessitant validation.
    """
    try:
        # Récupérer le service agent
        agent_service = http_request.app.state.agent_service
        
        logger.info(f"Exécution plan: {request.plan_id}")
        
        # Exécuter le plan
        result = await agent_service.execute_plan_by_id(
            plan_id=request.plan_id,
            command_id=request.command_id
        )
        
        # Construire la réponse
        response = CommandResponse(
            success=result["success"],
            stage="execution_completed" if result["success"] else "execution_failed",
            message=result["message"],
            command_id=request.command_id or "unknown",
            duration=result.get("duration"),
            session_id=result.get("session_id")
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Erreur exécution plan {request.plan_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur exécution plan: {str(e)}"
        )


@router.get("/commands/examples")
async def get_command_examples():
    """
    Retourne des exemples de commandes supportées.
    
    Utile pour l'interface utilisateur et la documentation.
    """
    try:
        examples = {
            "basic_commands": [
                {
                    "text": "Ouvre Google Chrome",
                    "description": "Ouvre le navigateur Chrome",
                    "source": "text"
                },
                {
                    "text": "Crée un fichier texte et écris Bonjour",
                    "description": "Crée un nouveau fichier avec du contenu",
                    "source": "text"
                },
                {
                    "text": "Clique sur OK",
                    "description": "Clique sur un bouton ou texte visible",
                    "source": "text"
                },
                {
                    "text": "Recherche Python sur Google",
                    "description": "Effectue une recherche web",
                    "source": "text"
                }
            ],
            "voice_commands": [
                {
                    "text": "Lance Calculator",
                    "description": "Ouvre la calculatrice",
                    "source": "voice"
                },
                {
                    "text": "Écris mon nom",
                    "description": "Saisit du texte",
                    "source": "voice"
                }
            ],
            "advanced_commands": [
                {
                    "text": "Sauvegarde le fichier dans Documents",
                    "description": "Sauvegarde avec chemin spécifique",
                    "source": "text"
                }
            ]
        }
        
        return examples
        
    except Exception as e:
        logger.error(f"Erreur récupération exemples: {e}")
        raise HTTPException(
            status_code=500,
            detail="Erreur récupération exemples"
        )


@router.get("/commands/validate")
async def validate_command(text: str, http_request: Request):
    """
    Valide une commande sans l'exécuter.
    
    Utile pour la validation en temps réel dans l'interface.
    """
    try:
        if not text or len(text.strip()) < 1:
            raise HTTPException(
                status_code=400,
                detail="Texte de commande requis"
            )
        
        # Récupérer le service agent
        agent_service = http_request.app.state.agent_service
        
        # Analyser avec NLU seulement
        nlu_result = agent_service.nlu_manager.understand(text.strip())
        
        validation = {
            "valid": nlu_result["ready_for_execution"],
            "intent": {
                "type": nlu_result["intent"]["type"],
                "confidence": nlu_result["intent"]["confidence"]
            },
            "slots": nlu_result["slots"],
            "validation_errors": nlu_result["validation"].get("errors", []),
            "warnings": nlu_result["validation"].get("warnings", []),
            "suggestions": nlu_result.get("suggestions", {})
        }
        
        return validation
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur validation commande '{text}': {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur validation: {str(e)}"
        )


@router.get("/commands/suggestions")
async def get_command_suggestions(query: str, limit: int = 5, http_request: Request):
    """
    Retourne des suggestions de commandes basées sur une requête partielle.
    
    Utile pour l'auto-complétion dans l'interface.
    """
    try:
        if not query or len(query.strip()) < 2:
            return {"suggestions": []}
        
        # Récupérer le service agent
        agent_service = http_request.app.state.agent_service
        
        # Obtenir les suggestions d'intentions
        intent_suggestions = agent_service.nlu_manager.get_intent_suggestions(
            query.strip(), limit
        )
        
        # Obtenir les suggestions de compétences
        skill_suggestions = agent_service.skill_manager.get_skill_suggestions(
            query.strip(), limit
        )
        
        suggestions = {
            "intent_suggestions": intent_suggestions,
            "skill_suggestions": skill_suggestions,
            "query": query.strip()
        }
        
        return suggestions
        
    except Exception as e:
        logger.error(f"Erreur suggestions pour '{query}': {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur récupération suggestions: {str(e)}"
        )