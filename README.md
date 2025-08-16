# Desktop Agent 🤖

Un agent d'automatisation de bureau cross-platform avec Computer Vision et Reinforcement Learning, interface vocale/texte, et barre de recherche toujours visible déclenchée par raccourci clavier global.

## 🎯 Objectifs MVP

- **Ouvrir Google Chrome** et effectuer une recherche
- **Créer/écrire un fichier texte** et le sauvegarder
- **Déclencher des actions** via : (1) barre de recherche UI en bas d'écran, (2) raccourci push-to-talk
- **Percevoir le bureau** via captures d'écran + OCR + APIs d'accessibilité
- **Tout enregistrer** pour replay et entraînement RL/imitation futur

## 🏗️ Architecture

```
desktop-agent/
├── apps/
│   ├── agent/              # Service FastAPI: NLP, planificateur, exécuteur
│   └── overlay/            # UI Electron+React (barre de recherche)
├── packages/
│   ├── common/             # config, schémas Pydantic, utils logging
│   ├── nlu/                # parsing intent/slot, grammaire basée règles
│   ├── planner/            # intent → plan (séquence de skills)
│   ├── skills/             # open_app, click_text, type_text, save_file
│   ├── perception/         # capture, OCR, détection, fusion accessibilité
│   ├── os_adapters/        # win/, mac/, linux/ (feature-flagged)
│   ├── rl_env/             # environnement Gym + wrappers
│   └── policy/             # scripts entraînement BC et PPO
├── data/
│   ├── demos/              # épisodes enregistrés avec frames
│   └── models/             # modèles entraînés
└── tests/
    ├── unit/               # tests unitaires
    └── e2e/                # tests end-to-end
```

## 🚀 Installation rapide (Windows)

### Prérequis
- **Python 3.11+** avec Poetry
- **Node.js 18+** avec npm
- **Git**

### Setup
```bash
# Cloner et installer
git clone <repo-url> desktop-agent
cd desktop-agent
make install

# Configuration Windows (permissions accessibilité)
make setup-windows

# Lancer en mode développement
make dev
```

### Permissions Windows requises
1. **Paramètres > Confidentialité et sécurité > Accessibilité**
2. Activer l'accès pour l'application
3. Redémarrer si nécessaire

## 🎮 Utilisation

### Raccourcis clavier
- **Ctrl + `** : Toggle barre de recherche overlay
- **Alt + Space** : Push-to-talk (maintenir enfoncé)
- **Enter** : Envoyer commande
- **Esc** : Masquer overlay

### Commandes MVP
```
# Via texte ou voix
"Ouvre Google Chrome"
"Crée un fichier texte et écris Bonjour"
"Recherche sur Google: intelligence artificielle"
"Sauvegarde le fichier dans Documents"
```

## 🛠️ Développement

### Commandes principales
```bash
make help          # Affiche toutes les commandes
make dev            # Lance agent + overlay
make agent          # Lance uniquement l'agent FastAPI
make overlay        # Lance uniquement l'UI Electron
make test           # Lance tous les tests
make lint           # Vérification code
make format         # Formatage code
```

### Structure des packages

#### `packages/common/`
- **Models** : `UiObject`, `Observation`, `Intent`, `Plan`, `Action`, `StepResult`
- **Config** : Chargement YAML + variables d'environnement
- **Logging** : Setup structuré avec rotation

#### `packages/os_adapters/`
- **Windows** : UIAutomation + pywinauto (complet)
- **macOS** : Accessibility API + AppleScript (stubs)
- **Linux** : AT-SPI + xdotool (stubs)

#### `packages/perception/`
- **Capture** : Multi-moniteur avec mss
- **OCR** : PaddleOCR + API recherche texte fuzzy
- **Accessibilité** : Énumération fenêtres/éléments unifiée

#### `packages/skills/`
- `open_app(name)` - Ouvrir application
- `focus_app(name)` - Focus sur application  
- `click_text(query)` - Clic via accessibilité/OCR
- `type_text(text)` - Saisie de texte
- `save_file(path)` - Sauvegarde fichier
- `write_text_file(path, content)` - Skill composite

## 🧠 IA et apprentissage

### NLP simple
- **Intents** basés règles : `open_app`, `write_file`, `web_search`
- **Normalisation** noms d'apps : "chrome" → "Google Chrome"
- **Slots** extraction : app, chemin, contenu, requête

### Planificateur
- **Intent → Plan** : Séquence de skills avec guardrails
- **Confirmation** : Écriture disque hors Documents
- **Plans lisibles** : Résumé humain + machine

### Reinforcement Learning
- **Environnement Gym** : Observation (perception) → Action (primitives)
- **Baseline** : Politique scriptée pour MVP
- **Entraînement** : SB3 PPO + Behavior Cloning
- **Données** : Episodes `/data/demos` avec frames

## 📊 Logging et Replay

### Enregistrement
- **Chaque étape** : hash observation, action, résultat, capture écran
- **SQLite** : Métadonnées episodes
- **Fichiers** : Screenshots dans `/data/demos/{episode_id}/`

### Replay
```bash
# Lister épisodes
python apps/agent/cli.py list-episodes

# Rejouer épisode (dry-run)
python apps/agent/cli.py replay --episode 12345

# Rejouer avec exécution réelle
python apps/agent/cli.py replay --episode 12345 --execute
```

## 🔧 API

### Agent FastAPI (Port 8000)
```http
POST /command
{
  "source": "voice|text",
  "text": "Ouvre Google Chrome",
  "confirm": true
}

WS /events
# Stream temps réel des logs

GET /observation
# Snapshot actuel du graphe UI
```

### Overlay UI
- **Always-on-top** : Barre en bas d'écran
- **Frameless** : Design minimal
- **Keyboard-first** : Navigation clavier
- **Notifications** : Toast feedback

## 🧪 Tests

### Tests unitaires
```bash
make test-unit
# Tests parsing intents, planificateur, skills isolés
```

### Tests E2E
```bash
make test-e2e  
# Tests mocked + scénarios manuels documentés
```

### Démo manuelle
```bash
make demo
# Lance avec instructions MVP
```

## ⚠️ Limitations et risques

### Version actuelle
- **Windows uniquement** (macOS/Linux en stubs)
- **Skills basiques** (pas de navigation web complexe)
- **OCR anglais/français** principalement
- **RL non entraîné** (politique scriptée)

### Sécurité
- **Permissions élevées** requises (accessibilité)
- **Confirmation** pour actions sensibles
- **Sandbox** recommandé pour tests

### Performance
- **Latence OCR** : ~200-500ms par capture
- **Mémoire** : Screenshots haute résolution
- **CPU** : Traitement vision continue

## 🔮 Prochaines étapes

### Court terme
1. **Stabilité Windows** : Gestion erreurs robuste
2. **Skills avancés** : Navigation web, manipulation fichiers
3. **Voice VAD** : Détection activité vocale améliorée

### Moyen terme  
1. **Support macOS/Linux** : Implémentation complète
2. **RL Training** : Entraînement sur données réelles
3. **Plugin system** : Skills personnalisés

### Long terme
1. **Multi-modal** : Vision + Language models
2. **Cloud sync** : Synchronisation cross-device
3. **Collaboration** : Agents multiples

## 📄 License

MIT License - Voir [LICENSE](LICENSE) pour détails.

## 🤝 Contribution

1. Fork le projet
2. Créer une branche feature (`git checkout -b feature/amazing-feature`)
3. Commit (`git commit -m 'Add amazing feature'`)
4. Push (`git push origin feature/amazing-feature`)
5. Ouvrir une Pull Request

---

**Desktop Agent** - Automatisation intelligente pour tous 🚀