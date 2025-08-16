# Guide de déploiement

## Environnements de déploiement

### Développement local
Configuration pour le développement et les tests.

### Production utilisateur final
Installation sur le poste de travail de l'utilisateur.

### Serveur de démo
Déploiement pour démonstrations et tests.

## Prérequis système

### Windows 10/11
- **Processeur** : x64, 2+ GHz
- **RAM** : 4 GB minimum, 8 GB recommandé
- **Stockage** : 2 GB d'espace libre
- **Permissions** : Accès administrateur pour l'installation
- **APIs** : UIAutomation activée

### macOS (Support partiel)
- **Version** : macOS 10.15+
- **RAM** : 4 GB minimum
- **Permissions** : Accessibilité, Automation
- **Status** : Stubs implémentés, développement requis

### Linux (Support partiel)  
- **Distribution** : Ubuntu 20.04+, CentOS 8+
- **Desktop** : X11 ou Wayland
- **Packages** : `python3-dev`, `build-essential`
- **Status** : Stubs implémentés, développement requis

## Installation de développement

### 1. Clone et setup
```bash
git clone https://github.com/your-org/desktop-agent.git
cd desktop-agent

# Setup automatique
python scripts/setup.py

# Vérification
make test
```

### 2. Configuration IDE

#### VS Code
```json
// .vscode/settings.json
{
  "python.defaultInterpreterPath": ".venv/bin/python",
  "python.formatting.provider": "black",
  "python.linting.enabled": true,
  "python.linting.flake8Enabled": true,
  "typescript.preferences.importModuleSpecifier": "relative"
}
```

#### PyCharm
1. Ouvrir le projet
2. Configurer l'interpréteur Poetry
3. Activer les inspections Black et flake8

### 3. Variables d'environnement
```bash
# .env (optionnel)
DESKTOP_AGENT_DEBUG=true
DESKTOP_AGENT_LOG_LEVEL=DEBUG
DESKTOP_AGENT_PORT=8000
DESKTOP_AGENT_DATA_DIR=./data
```

## Installation production

### 1. Package binaire (recommandé)

#### Windows
```powershell
# Télécharger l'installeur
Invoke-WebRequest -Uri "https://releases.../desktop-agent-setup.exe" -OutFile "setup.exe"

# Installation
.\setup.exe /S /D="C:\Program Files\Desktop Agent"

# Vérification
desktop-agent --version
```

#### macOS
```bash
# Télécharger le package
curl -L "https://releases.../desktop-agent.dmg" -o desktop-agent.dmg

# Installation
hdiutil mount desktop-agent.dmg
cp -R "/Volumes/Desktop Agent/Desktop Agent.app" /Applications/
hdiutil unmount "/Volumes/Desktop Agent"
```

### 2. Installation via pip (alternative)
```bash
# Créer un environnement virtuel
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Installer depuis PyPI (quand disponible)
pip install desktop-agent

# Ou depuis les sources
pip install git+https://github.com/your-org/desktop-agent.git

# Configuration initiale
desktop-agent init
```

### 3. Installation Docker (serveur)
```bash
# Pull de l'image
docker pull your-org/desktop-agent:latest

# Lancement
docker run -d \
  --name desktop-agent \
  -p 8000:8000 \
  -v /path/to/data:/app/data \
  -e DESKTOP_AGENT_LOG_LEVEL=INFO \
  your-org/desktop-agent:latest

# Vérification
curl http://localhost:8000/status
```

## Configuration post-installation

### 1. Permissions Windows

#### Accessibilité
1. **Paramètres** → **Confidentialité et sécurité** → **Accessibilité**
2. Activer "Desktop Agent" dans la liste des applications
3. Redémarrer l'application

#### UIAutomation
```powershell
# Vérifier que UIAutomation est activé
Get-WindowsOptionalFeature -Online -FeatureName "UIAutomation"

# Activer si nécessaire (administrateur requis)
Enable-WindowsOptionalFeature -Online -FeatureName "UIAutomation"
```

#### Microphone (pour la voix)
1. **Paramètres** → **Confidentialité** → **Microphone**
2. Autoriser l'accès au microphone pour Desktop Agent

### 2. Configuration firewall
```powershell
# Windows Defender
New-NetFirewallRule -DisplayName "Desktop Agent" -Direction Inbound -Port 8000 -Protocol TCP -Action Allow

# Ou via l'interface graphique
# Panneau de configuration → Système et sécurité → Pare-feu Windows Defender
```

### 3. Fichier de configuration
```yaml
# %APPDATA%\Desktop Agent\config.yaml (Windows)
# ~/.config/desktop-agent/config.yaml (Linux/macOS)

app:
  name: desktop-agent
  version: 0.1.0
  debug: false
  auto_start: true

api:
  host: 127.0.0.1  # Localhost seulement
  port: 8000
  cors_origins: []

ui:
  overlay_enabled: true
  hotkey: "ctrl+`"
  push_to_talk_key: "alt+space"
  auto_hide_delay: 5000

skills:
  timeout: 10.0
  confirm_file_operations: true
  allowed_directories:
    - "~/Documents"
    - "~/Desktop" 
    - "~/Downloads"

voice:
  enabled: true
  whisper_model: "base"
  language: "fr"

logging:
  level: INFO
  file: "logs/agent.log"
  max_size: "10MB"
  backup_count: 5
```

## Déploiement serveur

### 1. Architecture serveur
```
[Load Balancer]
       |
[Desktop Agent API] x N instances
       |
[Shared Storage] (logs, models)
```

### 2. Docker Compose
```yaml
# docker-compose.yml
version: '3.8'

services:
  desktop-agent:
    image: your-org/desktop-agent:latest
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    environment:
      - DESKTOP_AGENT_LOG_LEVEL=INFO
      - DESKTOP_AGENT_PORT=8000
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/status"]
      interval: 30s
      timeout: 10s
      retries: 3

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - desktop-agent
    restart: unless-stopped
```

### 3. Configuration Nginx
```nginx
# nginx.conf
upstream desktop_agent {
    server desktop-agent:8000;
}

server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    
    location / {
        proxy_pass http://desktop_agent;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location /events {
        proxy_pass http://desktop_agent;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

### 4. Kubernetes (optionnel)
```yaml
# k8s-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: desktop-agent
spec:
  replicas: 3
  selector:
    matchLabels:
      app: desktop-agent
  template:
    metadata:
      labels:
        app: desktop-agent
    spec:
      containers:
      - name: desktop-agent
        image: your-org/desktop-agent:latest
        ports:
        - containerPort: 8000
        env:
        - name: DESKTOP_AGENT_LOG_LEVEL
          value: "INFO"
        volumeMounts:
        - name: data
          mountPath: /app/data
        livenessProbe:
          httpGet:
            path: /status
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: desktop-agent-data

---
apiVersion: v1
kind: Service
metadata:
  name: desktop-agent-service
spec:
  selector:
    app: desktop-agent
  ports:
  - port: 8000
    targetPort: 8000
  type: LoadBalancer
```

## Monitoring et maintenance

### 1. Health checks
```bash
# Vérification locale
curl -f http://localhost:8000/status

# Vérification détaillée
curl http://localhost:8000/status | jq '.'
```

### 2. Logs
```bash
# Logs en temps réel
tail -f data/logs/agent.log

# Recherche d'erreurs
grep ERROR data/logs/agent.log

# Logs Docker
docker logs desktop-agent -f
```

### 3. Métriques
```python
# Endpoint /metrics (Prometheus format)
GET http://localhost:8000/metrics

# Métriques importantes:
# - desktop_agent_sessions_total
# - desktop_agent_actions_duration_seconds
# - desktop_agent_errors_total
# - desktop_agent_memory_usage_bytes
```

### 4. Backup
```bash
#!/bin/bash
# backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backup/desktop-agent"

# Créer le dossier de backup
mkdir -p "$BACKUP_DIR/$DATE"

# Sauvegarder les données
tar -czf "$BACKUP_DIR/$DATE/data.tar.gz" data/
tar -czf "$BACKUP_DIR/$DATE/logs.tar.gz" logs/
cp config.yaml "$BACKUP_DIR/$DATE/"

# Nettoyer les anciens backups (garde 7 jours)
find "$BACKUP_DIR" -type d -mtime +7 -exec rm -rf {} +

echo "Backup créé: $BACKUP_DIR/$DATE"
```

## Mise à jour

### 1. Mise à jour locale
```bash
# Via pip
pip install --upgrade desktop-agent

# Via git (développement)
git pull origin main
poetry install
make test
```

### 2. Mise à jour production
```bash
# Arrêter le service
systemctl stop desktop-agent

# Sauvegarder
./backup.sh

# Mettre à jour
pip install --upgrade desktop-agent

# Vérifier la configuration
desktop-agent config validate

# Redémarrer
systemctl start desktop-agent
systemctl status desktop-agent
```

### 3. Rollback
```bash
# Revenir à la version précédente
pip install desktop-agent==0.1.0

# Ou restaurer depuis backup
tar -xzf /backup/desktop-agent/20231201_120000/data.tar.gz
```

## Troubleshooting déploiement

### 1. Problèmes courants

#### Port déjà utilisé
```bash
# Trouver le processus
netstat -tulpn | grep :8000
lsof -i :8000

# Changer le port
export DESKTOP_AGENT_PORT=8001
```

#### Permissions insuffisantes
```bash
# Linux: ajouter l'utilisateur aux groupes nécessaires
sudo usermod -a -G input,audio $USER

# Windows: exécuter en tant qu'administrateur
```

#### Modules Python manquants
```bash
# Réinstaller les dépendances
poetry install --with dev,test

# Ou forcer la réinstallation
pip install --force-reinstall desktop-agent
```

### 2. Diagnostics
```bash
# Test de connectivité
curl -v http://localhost:8000/status

# Test des permissions
python -c "import pyautogui; print('OK')"

# Test des dépendances
desktop-agent doctor

# Logs détaillés
export DESKTOP_AGENT_LOG_LEVEL=DEBUG
desktop-agent run
```

### 3. Support
- **Documentation** : https://docs.desktop-agent.com
- **Issues** : https://github.com/your-org/desktop-agent/issues
- **Discord** : https://discord.gg/desktop-agent
- **Email** : support@desktop-agent.com

## Sécurité en production

### 1. Réseau
- Utiliser HTTPS uniquement
- Restreindre l'accès par IP si possible
- Configurer un firewall approprié

### 2. Authentification
```yaml
# config.yaml
security:
  api_key_required: true
  api_keys:
    - "your-secure-api-key-here"
  rate_limiting:
    requests_per_minute: 60
```

### 3. Audit
- Activer tous les logs
- Surveiller les actions sensibles
- Alertes sur les échecs répétés

Cette configuration assure un déploiement robuste et sécurisé de Desktop Agent.