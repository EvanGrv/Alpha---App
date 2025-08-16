# API Documentation

## FastAPI Endpoints

L'agent expose une API REST et WebSocket pour l'intégration avec l'interface overlay et les clients externes.

### Base URL
```
http://localhost:8000
```

### Authentication
Aucune authentification n'est requise pour le MVP (développement local).

## REST Endpoints

### POST /command
Exécute une commande textuelle ou vocale.

**Request Body:**
```json
{
  "source": "text" | "voice",
  "text": "Ouvre Google Chrome"
}
```

**Response:**
```json
{
  "session_id": "20231201_143022_a1b2c3d4",
  "plan": {
    "intent_type": "open_app",
    "actions": [
      {
        "type": "open_app",
        "parameters": {"app_name": "chrome"},
        "timestamp": 1701434622.123
      }
    ],
    "confidence": 0.95,
    "description": "Ouvrir Google Chrome"
  },
  "status": "executing",
  "message": "Commande reçue et en cours d'exécution"
}
```

**Status Codes:**
- `200` - Commande acceptée
- `400` - Commande invalide
- `422` - Erreur de validation
- `500` - Erreur serveur

### GET /observation
Récupère l'état actuel de l'observation du système.

**Response:**
```json
{
  "timestamp": 1701434622.123,
  "screenshot_path": "/path/to/screenshot.png",
  "ui_elements": [
    {
      "name": "Chrome Browser",
      "role": "window",
      "bounds": [100, 100, 800, 600],
      "text": "Google Chrome",
      "enabled": true,
      "visible": true
    }
  ],
  "ocr_results": [
    {
      "text": "Google Search",
      "bounds": [200, 300, 150, 30],
      "confidence": 0.98
    }
  ],
  "active_window": "Google Chrome",
  "mouse_position": [400, 350],
  "step_count": 5,
  "last_action_success": true
}
```

### GET /status
Récupère le statut général de l'agent.

**Response:**
```json
{
  "status": "running",
  "version": "0.1.0",
  "uptime": 3600.5,
  "active_sessions": 2,
  "services": {
    "perception": "healthy",
    "planner": "healthy", 
    "skills": "healthy",
    "voice": "optional"
  },
  "system": {
    "os": "Windows",
    "memory_usage": "245MB",
    "cpu_usage": "12%"
  }
}
```

## WebSocket Endpoints

### WS /events
Flux d'événements en temps réel de l'agent.

**Connection:**
```javascript
const ws = new WebSocket('ws://localhost:8000/events');
```

**Event Types:**

#### session_started
```json
{
  "type": "session_started",
  "data": {
    "session_id": "20231201_143022_a1b2c3d4",
    "command": "Ouvre Google Chrome",
    "source": "text"
  },
  "timestamp": 1701434622.123
}
```

#### plan_generated
```json
{
  "type": "plan_generated", 
  "data": {
    "session_id": "20231201_143022_a1b2c3d4",
    "plan": {
      "intent_type": "open_app",
      "actions": [...],
      "confidence": 0.95
    }
  },
  "timestamp": 1701434622.456
}
```

#### action_executed
```json
{
  "type": "action_executed",
  "data": {
    "session_id": "20231201_143022_a1b2c3d4",
    "action": {
      "type": "open_app",
      "parameters": {"app_name": "chrome"}
    },
    "result": {
      "success": true,
      "message": "Application ouverte avec succès"
    }
  },
  "timestamp": 1701434623.789
}
```

#### session_completed
```json
{
  "type": "session_completed",
  "data": {
    "session_id": "20231201_143022_a1b2c3d4", 
    "success": true,
    "total_steps": 3,
    "duration": 2.5
  },
  "timestamp": 1701434625.123
}
```

#### error
```json
{
  "type": "error",
  "data": {
    "session_id": "20231201_143022_a1b2c3d4",
    "error_type": "SkillExecutionError",
    "message": "Impossible d'ouvrir l'application",
    "details": {...}
  },
  "timestamp": 1701434623.456
}
```

## Data Models

### Command
```typescript
interface Command {
  source: "text" | "voice";
  text: string;
  timestamp?: number;
}
```

### Intent
```typescript
interface Intent {
  type: "open_app" | "write_file" | "web_search" | "unknown";
  slots: Record<string, any>;
  confidence: number;
  original_text: string;
}
```

### Action
```typescript
interface Action {
  type: "open_app" | "click" | "type_text" | "key_press" | "save_file" | "wait";
  parameters: Record<string, any>;
  timestamp: number;
}
```

### Plan
```typescript
interface Plan {
  intent_type: string;
  actions: Action[];
  confidence: number;
  description: string;
}
```

### UiObject
```typescript
interface UiObject {
  name: string;
  role: string;
  bounds: [number, number, number, number]; // [x, y, width, height]
  text: string;
  enabled: boolean;
  visible: boolean;
}
```

### OCRResult
```typescript
interface OCRResult {
  text: string;
  bounds: [number, number, number, number];
  confidence: number;
}
```

### Observation
```typescript
interface Observation {
  timestamp: number;
  screenshot_path: string;
  ui_elements: UiObject[];
  ocr_results: OCRResult[];
  active_window: string;
  mouse_position: [number, number];
  step_count: number;
  last_action_success: boolean;
}
```

## Error Handling

### Error Response Format
```json
{
  "error": {
    "type": "ValidationError",
    "message": "Invalid command format",
    "details": {
      "field": "text",
      "issue": "Required field missing"
    }
  },
  "timestamp": 1701434622.123
}
```

### Common Error Types
- `ValidationError` - Données d'entrée invalides
- `PerceptionError` - Erreur de capture/analyse écran
- `SkillExecutionError` - Erreur d'exécution d'action
- `PlanningError` - Erreur de planification
- `ConfigurationError` - Erreur de configuration
- `TimeoutError` - Timeout d'exécution

## Rate Limiting

Pour éviter la surcharge :
- **Commands** : 10 requêtes/minute par client
- **Observations** : 60 requêtes/minute par client
- **WebSocket** : 1 connexion par client

## Examples

### JavaScript Client
```javascript
class DesktopAgentClient {
  constructor(baseUrl = 'http://localhost:8000') {
    this.baseUrl = baseUrl;
    this.ws = null;
  }

  async sendCommand(text, source = 'text') {
    const response = await fetch(`${this.baseUrl}/command`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source, text })
    });
    return response.json();
  }

  async getObservation() {
    const response = await fetch(`${this.baseUrl}/observation`);
    return response.json();
  }

  connectEvents(onEvent) {
    this.ws = new WebSocket(`ws://localhost:8000/events`);
    this.ws.onmessage = (event) => onEvent(JSON.parse(event.data));
  }
}

// Usage
const client = new DesktopAgentClient();

// Send command
const result = await client.sendCommand("Ouvre Chrome");
console.log('Command result:', result);

// Listen to events
client.connectEvents((event) => {
  console.log('Agent event:', event.type, event.data);
});
```

### Python Client
```python
import requests
import websocket
import json

class DesktopAgentClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
    
    def send_command(self, text, source="text"):
        response = requests.post(
            f"{self.base_url}/command",
            json={"source": source, "text": text}
        )
        return response.json()
    
    def get_observation(self):
        response = requests.get(f"{self.base_url}/observation")
        return response.json()
    
    def listen_events(self, on_event):
        def on_message(ws, message):
            event = json.loads(message)
            on_event(event)
        
        ws = websocket.WebSocketApp(
            "ws://localhost:8000/events",
            on_message=on_message
        )
        ws.run_forever()

# Usage
client = DesktopAgentClient()

# Send command
result = client.send_command("Ouvre Chrome")
print("Command result:", result)

# Listen to events
client.listen_events(lambda event: print("Event:", event["type"]))
```

## OpenAPI Schema

Le schéma OpenAPI complet est disponible à :
- **Swagger UI** : http://localhost:8000/docs
- **ReDoc** : http://localhost:8000/redoc
- **JSON Schema** : http://localhost:8000/openapi.json