"""
Endpoints WebSocket pour les événements temps réel.

Fournit des mises à jour en temps réel sur l'état de l'agent.
"""

import asyncio
import json
from typing import Any, Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from fastapi.websockets import WebSocketState

from packages.common.logging_utils import get_agent_logger

logger = get_agent_logger()

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """Gestionnaire des connexions WebSocket."""
    
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.connection_info: dict[WebSocket, dict] = {}
    
    async def connect(self, websocket: WebSocket, client_info: dict = None):
        """Accepte une nouvelle connexion."""
        await websocket.accept()
        self.active_connections.append(websocket)
        self.connection_info[websocket] = client_info or {}
        
        logger.info(f"Nouvelle connexion WebSocket: {len(self.active_connections)} actives")
    
    def disconnect(self, websocket: WebSocket):
        """Supprime une connexion."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.connection_info:
            del self.connection_info[websocket]
        
        logger.info(f"Connexion WebSocket fermée: {len(self.active_connections)} actives")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Envoie un message à une connexion spécifique."""
        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.warning(f"Erreur envoi message personnel: {e}")
                self.disconnect(websocket)
    
    async def broadcast(self, message: dict):
        """Diffuse un message à toutes les connexions actives."""
        if not self.active_connections:
            return
        
        disconnected = []
        
        for connection in self.active_connections:
            try:
                if connection.client_state == WebSocketState.CONNECTED:
                    await connection.send_text(json.dumps(message))
                else:
                    disconnected.append(connection)
            except Exception as e:
                logger.warning(f"Erreur diffusion message: {e}")
                disconnected.append(connection)
        
        # Nettoyer les connexions fermées
        for connection in disconnected:
            self.disconnect(connection)
    
    def get_stats(self) -> dict:
        """Retourne les statistiques des connexions."""
        return {
            "active_connections": len(self.active_connections),
            "connections_info": [
                {
                    "client": getattr(conn.client, 'host', 'unknown'),
                    "info": self.connection_info.get(conn, {})
                }
                for conn in self.active_connections
            ]
        }


# Instance globale du gestionnaire de connexions
manager = ConnectionManager()


@router.websocket("/ws/events")
async def websocket_events_endpoint(websocket: WebSocket):
    """
    Endpoint WebSocket pour les événements en temps réel.
    
    Diffuse tous les événements de l'agent (commandes, exécutions, erreurs, etc.).
    """
    await manager.connect(websocket, {"type": "events", "subscribed_at": asyncio.get_event_loop().time()})
    
    try:
        # Récupérer le service agent depuis l'app state
        # Note: websocket n'a pas accès direct à request.app, on doit passer par l'instance globale
        agent_service = None
        event_queue = None
        
        # Message de bienvenue
        await manager.send_personal_message({
            "type": "connection_established",
            "message": "Connexion WebSocket établie",
            "timestamp": asyncio.get_event_loop().time()
        }, websocket)
        
        # Boucle de réception des messages du client
        receive_task = asyncio.create_task(handle_client_messages(websocket))
        
        # Boucle de diffusion des événements
        broadcast_task = asyncio.create_task(handle_event_broadcasting(websocket))
        
        # Attendre que l'une des tâches se termine
        done, pending = await asyncio.wait(
            [receive_task, broadcast_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Annuler les tâches en cours
        for task in pending:
            task.cancel()
    
    except WebSocketDisconnect:
        logger.info("Client WebSocket déconnecté")
    except Exception as e:
        logger.error(f"Erreur WebSocket: {e}")
    finally:
        manager.disconnect(websocket)


async def handle_client_messages(websocket: WebSocket):
    """Gère les messages entrants du client WebSocket."""
    try:
        while True:
            # Recevoir un message du client
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                await process_client_message(message, websocket)
            except json.JSONDecodeError:
                await manager.send_personal_message({
                    "type": "error",
                    "message": "Format JSON invalide"
                }, websocket)
            except Exception as e:
                logger.error(f"Erreur traitement message client: {e}")
                await manager.send_personal_message({
                    "type": "error",
                    "message": f"Erreur traitement message: {str(e)}"
                }, websocket)
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Erreur gestion messages client: {e}")


async def handle_event_broadcasting(websocket: WebSocket):
    """Gère la diffusion des événements système."""
    try:
        # Pour l'instant, on simule des événements
        # Dans une implémentation complète, on s'abonnerait aux événements du service
        
        while True:
            # Envoyer un ping périodique pour maintenir la connexion
            await asyncio.sleep(30)
            
            await manager.send_personal_message({
                "type": "ping",
                "timestamp": asyncio.get_event_loop().time()
            }, websocket)
    
    except Exception as e:
        logger.error(f"Erreur diffusion événements: {e}")


async def process_client_message(message: dict, websocket: WebSocket):
    """Traite un message du client WebSocket."""
    message_type = message.get("type")
    
    if message_type == "ping":
        # Répondre au ping
        await manager.send_personal_message({
            "type": "pong",
            "timestamp": asyncio.get_event_loop().time()
        }, websocket)
    
    elif message_type == "subscribe":
        # S'abonner à des événements spécifiques
        event_types = message.get("event_types", [])
        manager.connection_info[websocket]["subscriptions"] = event_types
        
        await manager.send_personal_message({
            "type": "subscription_confirmed",
            "event_types": event_types
        }, websocket)
    
    elif message_type == "unsubscribe":
        # Se désabonner
        manager.connection_info[websocket]["subscriptions"] = []
        
        await manager.send_personal_message({
            "type": "unsubscribed",
            "message": "Désabonné de tous les événements"
        }, websocket)
    
    elif message_type == "get_status":
        # Demander le statut actuel
        # TODO: Récupérer le statut du service agent
        await manager.send_personal_message({
            "type": "status_response",
            "status": "Service en cours d'exécution",
            "timestamp": asyncio.get_event_loop().time()
        }, websocket)
    
    else:
        await manager.send_personal_message({
            "type": "error",
            "message": f"Type de message non supporté: {message_type}"
        }, websocket)


@router.websocket("/ws/logs")
async def websocket_logs_endpoint(websocket: WebSocket):
    """
    Endpoint WebSocket pour les logs en temps réel.
    
    Diffuse les logs de l'agent en temps réel.
    """
    await manager.connect(websocket, {"type": "logs", "subscribed_at": asyncio.get_event_loop().time()})
    
    try:
        await manager.send_personal_message({
            "type": "connection_established",
            "message": "Connexion logs WebSocket établie",
            "timestamp": asyncio.get_event_loop().time()
        }, websocket)
        
        # Boucle de diffusion des logs
        while True:
            # TODO: Implémenter la diffusion des logs en temps réel
            # Pour l'instant, on envoie un message de test périodique
            
            await asyncio.sleep(10)
            
            await manager.send_personal_message({
                "type": "log_entry",
                "level": "info",
                "message": "Log de test",
                "timestamp": asyncio.get_event_loop().time(),
                "source": "websocket"
            }, websocket)
    
    except WebSocketDisconnect:
        logger.info("Client WebSocket logs déconnecté")
    except Exception as e:
        logger.error(f"Erreur WebSocket logs: {e}")
    finally:
        manager.disconnect(websocket)


@router.get("/ws/stats")
async def get_websocket_stats():
    """
    Retourne les statistiques des connexions WebSocket.
    """
    return manager.get_stats()


# Fonction utilitaire pour diffuser des événements depuis d'autres modules
async def broadcast_event(event: Dict[str, Any]):
    """
    Diffuse un événement à toutes les connexions WebSocket actives.
    
    Args:
        event: Événement à diffuser
    """
    await manager.broadcast(event)


# Fonction pour diffuser des logs
async def broadcast_log(level: str, message: str, source: str = "agent", **kwargs):
    """
    Diffuse un log à toutes les connexions WebSocket logs.
    
    Args:
        level: Niveau de log
        message: Message de log
        source: Source du log
        **kwargs: Données additionnelles
    """
    log_event = {
        "type": "log_entry",
        "level": level,
        "message": message,
        "source": source,
        "timestamp": asyncio.get_event_loop().time(),
        **kwargs
    }
    
    await manager.broadcast(log_event)