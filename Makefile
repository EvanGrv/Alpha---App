# Makefile pour Desktop Agent
.PHONY: help install dev agent overlay test clean lint format docs

# Variables
PYTHON := python
POETRY := poetry
NODE := npm
AGENT_PORT := 8000
OVERLAY_PORT := 3000

# Aide par défaut
help:
	@echo "Desktop Agent - Commandes disponibles:"
	@echo ""
	@echo "Setup:"
	@echo "  install     - Installer toutes les dépendances"
	@echo "  install-dev - Installer les dépendances de développement"
	@echo ""
	@echo "Développement:"
	@echo "  dev         - Lancer agent + overlay en mode développement"
	@echo "  agent       - Lancer seulement l'agent FastAPI"
	@echo "  overlay     - Lancer seulement l'overlay Electron"
	@echo ""
	@echo "Tests:"
	@echo "  test        - Lancer tous les tests"
	@echo "  test-unit   - Lancer les tests unitaires"
	@echo "  test-e2e    - Lancer les tests e2e"
	@echo "  lint        - Vérifier le code avec linters"
	@echo "  format      - Formater le code"
	@echo ""
	@echo "RL & Training:"
	@echo "  train-bc    - Entraîner le modèle Behavior Cloning"
	@echo "  train-ppo   - Entraîner le modèle PPO"
	@echo "  eval-baseline - Évaluer la politique baseline"
	@echo ""
	@echo "Données:"
	@echo "  demos       - Créer des démonstrations depuis les logs"
	@echo "  replay      - Rejouer une session (SESSION_ID=xxx make replay)"
	@echo "  list-sessions - Lister les sessions disponibles"
	@echo ""
	@echo "Maintenance:"
	@echo "  clean       - Nettoyer les fichiers temporaires"
	@echo "  docs        - Générer la documentation"

# Installation
install:
	@echo "🔧 Installation des dépendances..."
	$(POETRY) install
	cd apps/overlay && $(NODE) install
	@echo "✅ Installation terminée"

install-dev:
	@echo "🔧 Installation des dépendances de développement..."
	$(POETRY) install --with dev,test
	cd apps/overlay && $(NODE) install --include=dev
	@echo "✅ Installation dev terminée"

# Développement
dev:
	@echo "🚀 Démarrage en mode développement..."
	@echo "Agent: http://localhost:$(AGENT_PORT)"
	@echo "Overlay: http://localhost:$(OVERLAY_PORT)"
	@echo "Ctrl+C pour arrêter"
	$(MAKE) -j2 agent overlay

agent:
	@echo "🤖 Démarrage de l'agent FastAPI..."
	cd apps/agent && $(POETRY) run uvicorn main:app --host 0.0.0.0 --port $(AGENT_PORT) --reload

overlay:
	@echo "🖥️  Démarrage de l'overlay Electron..."
	cd apps/overlay && $(NODE) run dev

# Tests
test: test-unit test-e2e
	@echo "✅ Tous les tests terminés"

test-unit:
	@echo "🧪 Tests unitaires..."
	$(POETRY) run pytest tests/unit/ -v

test-e2e:
	@echo "🔄 Tests e2e..."
	$(POETRY) run pytest tests/e2e/ -v

lint:
	@echo "🔍 Vérification du code..."
	$(POETRY) run flake8 packages/ apps/agent/ tests/
	$(POETRY) run mypy packages/ apps/agent/
	cd apps/overlay && $(NODE) run lint

format:
	@echo "✨ Formatage du code..."
	$(POETRY) run black packages/ apps/agent/ tests/
	$(POETRY) run isort packages/ apps/agent/ tests/
	cd apps/overlay && $(NODE) run format

# RL & Training
train-bc:
	@echo "🎓 Entraînement Behavior Cloning..."
	$(POETRY) run python scripts/train_bc.py --demo-dir data/demos --epochs 50

train-ppo:
	@echo "🎯 Entraînement PPO..."
	$(POETRY) run python scripts/train_ppo.py --total-timesteps 50000 --simulation

eval-baseline:
	@echo "📊 Évaluation politique baseline..."
	$(POETRY) run python scripts/evaluate_model.py --model-type baseline --n-episodes 5

# Données
demos:
	@echo "📹 Création de démonstrations..."
	$(POETRY) run python apps/agent/cli.py demos --success-only

replay:
	@echo "▶️  Replay de session..."
	@if [ -z "$(SESSION_ID)" ]; then \
		echo "❌ Utilisation: SESSION_ID=xxx make replay"; \
		exit 1; \
	fi
	$(POETRY) run python apps/agent/cli.py replay $(SESSION_ID) --dry-run --interactive

list-sessions:
	@echo "📋 Sessions disponibles..."
	$(POETRY) run python apps/agent/cli.py list --limit 10

# Maintenance
clean:
	@echo "🧹 Nettoyage..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type f -name ".coverage" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	cd apps/overlay && $(NODE) run clean || true
	@echo "✅ Nettoyage terminé"

docs:
	@echo "📚 Génération de la documentation..."
	$(POETRY) run sphinx-build -b html docs/ docs/_build/html/
	@echo "✅ Documentation générée dans docs/_build/html/"

# Targets pour Windows (alternatives)
install-win: install
dev-win: dev
agent-win: agent
overlay-win: overlay
test-win: test
clean-win: clean

# Commandes utilitaires
check-deps:
	@echo "🔍 Vérification des dépendances..."
	$(POETRY) check
	cd apps/overlay && $(NODE) audit

setup-env:
	@echo "⚙️  Configuration de l'environnement..."
	@echo "Création des dossiers de données..."
	mkdir -p data/logs data/demos data/models data/screenshots
	@echo "Création du fichier de config par défaut..."
	@if [ ! -f packages/planner/config.yaml ]; then \
		echo "Fichier config.yaml existe déjà"; \
	fi
	@echo "✅ Environnement configuré"

# Build pour production
build:
	@echo "🏗️  Build pour production..."
	cd apps/overlay && $(NODE) run build
	$(POETRY) build
	@echo "✅ Build terminé"

# Installation pour production
install-prod:
	@echo "🚀 Installation production..."
	$(POETRY) install --only=main
	cd apps/overlay && $(NODE) ci --only=production
	@echo "✅ Installation production terminée"

# Démarrage production
start-prod:
	@echo "🚀 Démarrage production..."
	$(POETRY) run uvicorn apps.agent.main:app --host 0.0.0.0 --port $(AGENT_PORT)

# Commandes de développement avancées
debug-agent:
	@echo "🐛 Debug de l'agent..."
	cd apps/agent && $(POETRY) run python -m debugpy --listen 5678 --wait-for-client -m uvicorn main:app --reload

profile-agent:
	@echo "📊 Profiling de l'agent..."
	cd apps/agent && $(POETRY) run python -m cProfile -o profile_output.prof main.py

# Tests de performance
perf-test:
	@echo "⚡ Tests de performance..."
	$(POETRY) run pytest tests/performance/ -v --benchmark-only

# Sécurité
security-check:
	@echo "🔒 Vérification de sécurité..."
	$(POETRY) run safety check
	cd apps/overlay && $(NODE) audit --audit-level moderate

# Mise à jour des dépendances
update-deps:
	@echo "⬆️  Mise à jour des dépendances..."
	$(POETRY) update
	cd apps/overlay && $(NODE) update

# Docker (si utilisé)
docker-build:
	@echo "🐳 Build Docker..."
	docker build -t desktop-agent .

docker-run:
	@echo "🐳 Run Docker..."
	docker run -p $(AGENT_PORT):$(AGENT_PORT) desktop-agent

# Informations système
info:
	@echo "ℹ️  Informations système:"
	@echo "Python: $(shell $(PYTHON) --version)"
	@echo "Poetry: $(shell $(POETRY) --version)"
	@echo "Node: $(shell $(NODE) --version)"
	@echo "OS: $(shell uname -s 2>/dev/null || echo 'Windows')"
	@echo "Architecture: $(shell uname -m 2>/dev/null || echo 'Unknown')"