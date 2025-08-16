"""Logger de session pour enregistrer toutes les actions et observations."""

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import hashlib

from pydantic import BaseModel

from packages.common.config import Config
from packages.common.models import Action, Observation, StepResult, ExecutionSession


class LogEntry(BaseModel):
    """Entrée de log pour une étape."""
    session_id: str
    step_number: int
    timestamp: float
    observation_hash: str
    action: Dict[str, Any]
    result: Dict[str, Any]
    screenshot_path: Optional[str] = None
    metadata: Dict[str, Any] = {}


class SessionLogger:
    """Logger pour enregistrer les sessions d'exécution."""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Chemins
        self.log_dir = Path(config.get('logging.log_dir', 'data/logs'))
        self.demo_dir = Path(config.get('logging.demo_dir', 'data/demos'))
        self.db_path = self.log_dir / 'sessions.db'
        
        # Créer les dossiers
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.demo_dir.mkdir(parents=True, exist_ok=True)
        
        # Base de données
        self.db_connection = None
        self.current_session_id = None
        
        # Configuration
        self.save_screenshots = config.get('logging.save_screenshots', True)
        self.compress_observations = config.get('logging.compress_observations', True)
        
    async def initialize(self):
        """Initialise le logger de session."""
        
        # Créer/connecter à la base de données
        self.db_connection = sqlite3.connect(str(self.db_path))
        self.db_connection.row_factory = sqlite3.Row
        
        # Créer les tables
        self._create_tables()
        
        self.logger.info(f"Session Logger initialisé - DB: {self.db_path}")
    
    def _create_tables(self):
        """Crée les tables de base de données."""
        
        cursor = self.db_connection.cursor()
        
        # Table des sessions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                start_time REAL NOT NULL,
                end_time REAL,
                command_text TEXT,
                command_source TEXT,
                success BOOLEAN,
                error_message TEXT,
                total_steps INTEGER DEFAULT 0,
                metadata TEXT
            )
        """)
        
        # Table des steps
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                step_number INTEGER NOT NULL,
                timestamp REAL NOT NULL,
                observation_hash TEXT,
                action_type TEXT,
                action_params TEXT,
                result_success BOOLEAN,
                result_message TEXT,
                screenshot_path TEXT,
                metadata TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions (session_id)
            )
        """)
        
        # Index pour les requêtes fréquentes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_steps ON steps (session_id, step_number)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON steps (timestamp)")
        
        self.db_connection.commit()
    
    async def start_session(self, session: ExecutionSession) -> str:
        """Démarre l'enregistrement d'une nouvelle session."""
        
        session_id = self._generate_session_id(session)
        self.current_session_id = session_id
        
        # Enregistrer la session en DB
        cursor = self.db_connection.cursor()
        cursor.execute("""
            INSERT INTO sessions (session_id, start_time, command_text, command_source, metadata)
            VALUES (?, ?, ?, ?, ?)
        """, (
            session_id,
            session.start_time,
            session.command.text,
            session.command.source.value,
            json.dumps(session.metadata)
        ))
        
        self.db_connection.commit()
        
        self.logger.info(f"Session démarrée: {session_id}")
        
        return session_id
    
    async def log_step(self, 
                      observation: Observation,
                      action: Action,
                      result: StepResult,
                      step_number: int,
                      metadata: Dict[str, Any] = None) -> LogEntry:
        """Enregistre une étape de la session."""
        
        if not self.current_session_id:
            raise ValueError("Aucune session active")
        
        # Créer l'entrée de log
        timestamp = time.time()
        observation_hash = self._hash_observation(observation)
        
        # Sauvegarder le screenshot si configuré
        screenshot_path = None
        if self.save_screenshots and observation.screenshot_path:
            screenshot_path = await self._save_screenshot(
                observation.screenshot_path, 
                self.current_session_id,
                step_number
            )
        
        # Créer l'entrée
        log_entry = LogEntry(
            session_id=self.current_session_id,
            step_number=step_number,
            timestamp=timestamp,
            observation_hash=observation_hash,
            action=action.dict(),
            result=result.dict(),
            screenshot_path=screenshot_path,
            metadata=metadata or {}
        )
        
        # Enregistrer en DB
        await self._save_step_to_db(log_entry)
        
        return log_entry
    
    async def end_session(self, success: bool, error_message: str = None, total_steps: int = 0):
        """Termine l'enregistrement de la session."""
        
        if not self.current_session_id:
            return
        
        cursor = self.db_connection.cursor()
        cursor.execute("""
            UPDATE sessions 
            SET end_time = ?, success = ?, error_message = ?, total_steps = ?
            WHERE session_id = ?
        """, (
            time.time(),
            success,
            error_message,
            total_steps,
            self.current_session_id
        ))
        
        self.db_connection.commit()
        
        self.logger.info(
            f"Session terminée: {self.current_session_id} - "
            f"Succès: {success}, Steps: {total_steps}"
        )
        
        self.current_session_id = None
    
    async def _save_step_to_db(self, log_entry: LogEntry):
        """Sauvegarde une étape en base de données."""
        
        cursor = self.db_connection.cursor()
        cursor.execute("""
            INSERT INTO steps (
                session_id, step_number, timestamp, observation_hash,
                action_type, action_params, result_success, result_message,
                screenshot_path, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            log_entry.session_id,
            log_entry.step_number,
            log_entry.timestamp,
            log_entry.observation_hash,
            log_entry.action.get('type'),
            json.dumps(log_entry.action.get('parameters', {})),
            log_entry.result.get('success'),
            log_entry.result.get('message'),
            log_entry.screenshot_path,
            json.dumps(log_entry.metadata)
        ))
        
        self.db_connection.commit()
    
    async def _save_screenshot(self, original_path: str, session_id: str, step_number: int) -> str:
        """Sauvegarde le screenshot dans le dossier de démonstration."""
        
        import shutil
        
        original = Path(original_path)
        if not original.exists():
            return None
        
        # Créer le dossier de session
        session_dir = self.demo_dir / session_id
        session_dir.mkdir(exist_ok=True)
        
        # Copier le screenshot
        screenshot_name = f"step_{step_number:04d}.png"
        screenshot_path = session_dir / screenshot_name
        
        shutil.copy2(original, screenshot_path)
        
        return str(screenshot_path)
    
    def _generate_session_id(self, session: ExecutionSession) -> str:
        """Génère un ID unique pour la session."""
        
        # Utiliser timestamp + hash de la commande
        timestamp = datetime.fromtimestamp(session.start_time).strftime("%Y%m%d_%H%M%S")
        command_hash = hashlib.md5(session.command.text.encode()).hexdigest()[:8]
        
        return f"{timestamp}_{command_hash}"
    
    def _hash_observation(self, observation: Observation) -> str:
        """Crée un hash de l'observation pour détecter les changements."""
        
        # Créer un hash basé sur les éléments clés de l'observation
        hash_data = {
            'active_window': observation.active_window,
            'ui_elements_count': len(observation.ui_elements),
            'ocr_results_count': len(observation.ocr_results),
            'mouse_position': observation.mouse_position
        }
        
        # Ajouter un hash du screenshot si disponible
        if observation.screenshot_path:
            try:
                with open(observation.screenshot_path, 'rb') as f:
                    # Lire seulement les premiers Ko pour la performance
                    screenshot_sample = f.read(1024)
                    hash_data['screenshot_hash'] = hashlib.md5(screenshot_sample).hexdigest()
            except:
                pass
        
        # Créer le hash final
        hash_string = json.dumps(hash_data, sort_keys=True)
        return hashlib.md5(hash_string.encode()).hexdigest()
    
    def get_session_history(self, session_id: str) -> Dict[str, Any]:
        """Récupère l'historique complet d'une session."""
        
        cursor = self.db_connection.cursor()
        
        # Récupérer les infos de session
        cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
        session_row = cursor.fetchone()
        
        if not session_row:
            return None
        
        # Récupérer les steps
        cursor.execute("""
            SELECT * FROM steps 
            WHERE session_id = ? 
            ORDER BY step_number
        """, (session_id,))
        
        steps = []
        for step_row in cursor.fetchall():
            steps.append({
                'step_number': step_row['step_number'],
                'timestamp': step_row['timestamp'],
                'observation_hash': step_row['observation_hash'],
                'action_type': step_row['action_type'],
                'action_params': json.loads(step_row['action_params']) if step_row['action_params'] else {},
                'result_success': step_row['result_success'],
                'result_message': step_row['result_message'],
                'screenshot_path': step_row['screenshot_path'],
                'metadata': json.loads(step_row['metadata']) if step_row['metadata'] else {}
            })
        
        return {
            'session_id': session_row['session_id'],
            'start_time': session_row['start_time'],
            'end_time': session_row['end_time'],
            'command_text': session_row['command_text'],
            'command_source': session_row['command_source'],
            'success': session_row['success'],
            'error_message': session_row['error_message'],
            'total_steps': session_row['total_steps'],
            'metadata': json.loads(session_row['metadata']) if session_row['metadata'] else {},
            'steps': steps
        }
    
    def list_sessions(self, limit: int = 100, success_only: bool = False) -> List[Dict[str, Any]]:
        """Liste les sessions enregistrées."""
        
        cursor = self.db_connection.cursor()
        
        query = "SELECT * FROM sessions"
        params = []
        
        if success_only:
            query += " WHERE success = 1"
        
        query += " ORDER BY start_time DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        
        sessions = []
        for row in cursor.fetchall():
            sessions.append({
                'session_id': row['session_id'],
                'start_time': row['start_time'],
                'end_time': row['end_time'],
                'command_text': row['command_text'],
                'command_source': row['command_source'],
                'success': row['success'],
                'error_message': row['error_message'],
                'total_steps': row['total_steps']
            })
        
        return sessions
    
    async def cleanup(self):
        """Nettoie les ressources."""
        
        if self.db_connection:
            self.db_connection.close()
            self.db_connection = None
        
        self.current_session_id = None
        self.logger.info("Session Logger nettoyé")