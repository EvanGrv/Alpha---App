#!/usr/bin/env python3
"""Script de setup initial pour Desktop Agent."""

import os
import sys
import subprocess
import platform
from pathlib import Path


def run_command(cmd, cwd=None, check=True):
    """Exécute une commande et affiche le résultat."""
    print(f"🔧 Exécution: {cmd}")
    
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            cwd=cwd, 
            check=check,
            capture_output=True,
            text=True
        )
        
        if result.stdout:
            print(result.stdout)
        
        return result
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Erreur: {e}")
        if e.stderr:
            print(f"Stderr: {e.stderr}")
        if check:
            sys.exit(1)
        return e


def check_prerequisites():
    """Vérifie les prérequis système."""
    print("🔍 Vérification des prérequis...")
    
    # Python
    python_version = sys.version_info
    if python_version < (3, 8):
        print("❌ Python 3.8+ requis")
        sys.exit(1)
    print(f"✅ Python {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    # Poetry
    try:
        result = run_command("poetry --version", check=False)
        if result.returncode == 0:
            print(f"✅ {result.stdout.strip()}")
        else:
            print("❌ Poetry non trouvé. Installation nécessaire:")
            print("   curl -sSL https://install.python-poetry.org | python3 -")
            sys.exit(1)
    except FileNotFoundError:
        print("❌ Poetry non trouvé dans le PATH")
        sys.exit(1)
    
    # Node.js
    try:
        result = run_command("node --version", check=False)
        if result.returncode == 0:
            print(f"✅ Node.js {result.stdout.strip()}")
        else:
            print("❌ Node.js non trouvé. Installation nécessaire.")
            sys.exit(1)
    except FileNotFoundError:
        print("❌ Node.js non trouvé dans le PATH")
        sys.exit(1)
    
    # npm
    try:
        result = run_command("npm --version", check=False)
        if result.returncode == 0:
            print(f"✅ npm {result.stdout.strip()}")
        else:
            print("❌ npm non trouvé")
            sys.exit(1)
    except FileNotFoundError:
        print("❌ npm non trouvé dans le PATH")
        sys.exit(1)


def create_directories():
    """Crée les dossiers nécessaires."""
    print("📁 Création des dossiers...")
    
    directories = [
        "data/logs",
        "data/demos", 
        "data/models",
        "data/screenshots",
        "logs",
        "temp"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✅ {directory}")


def install_python_deps():
    """Installe les dépendances Python."""
    print("🐍 Installation des dépendances Python...")
    
    # Installation des dépendances principales
    run_command("poetry install")
    
    print("✅ Dépendances Python installées")


def install_node_deps():
    """Installe les dépendances Node.js."""
    print("📦 Installation des dépendances Node.js...")
    
    overlay_dir = Path("apps/overlay")
    
    if overlay_dir.exists():
        run_command("npm install", cwd=overlay_dir)
        print("✅ Dépendances Node.js installées")
    else:
        print("⚠️  Dossier overlay non trouvé, skip")


def setup_config():
    """Configure les fichiers de configuration."""
    print("⚙️  Configuration...")
    
    config_file = Path("packages/planner/config.yaml")
    
    if not config_file.exists():
        print("⚠️  Fichier de configuration non trouvé")
    else:
        print("✅ Configuration trouvée")


def check_optional_deps():
    """Vérifie les dépendances optionnelles."""
    print("🔍 Vérification des dépendances optionnelles...")
    
    optional_deps = [
        ("git", "Contrôle de version"),
        ("docker", "Containerisation"),
        ("code", "VS Code (optionnel)")
    ]
    
    for cmd, description in optional_deps:
        result = run_command(f"{cmd} --version", check=False)
        if result.returncode == 0:
            print(f"✅ {cmd}: {description}")
        else:
            print(f"⚠️  {cmd}: {description} (optionnel)")


def setup_development_env():
    """Configure l'environnement de développement."""
    print("🛠️  Configuration environnement de développement...")
    
    # Pre-commit hooks (si disponible)
    result = run_command("poetry run pre-commit install", check=False)
    if result.returncode == 0:
        print("✅ Pre-commit hooks configurés")
    else:
        print("⚠️  Pre-commit non disponible (optionnel)")
    
    # Configuration IDE
    vscode_dir = Path(".vscode")
    if not vscode_dir.exists():
        vscode_dir.mkdir()
        
        # Paramètres VS Code
        settings = {
            "python.defaultInterpreterPath": "./venv/bin/python",
            "python.formatting.provider": "black",
            "python.linting.enabled": True,
            "python.linting.flake8Enabled": True,
            "typescript.preferences.importModuleSpecifier": "relative"
        }
        
        import json
        with open(vscode_dir / "settings.json", "w") as f:
            json.dump(settings, f, indent=2)
        
        print("✅ Configuration VS Code créée")


def run_tests():
    """Lance les tests pour vérifier l'installation."""
    print("🧪 Tests de vérification...")
    
    # Tests unitaires basiques
    result = run_command("poetry run pytest tests/unit/test_common.py -v", check=False)
    
    if result.returncode == 0:
        print("✅ Tests de base passés")
    else:
        print("⚠️  Certains tests ont échoué (peut être normal lors de l'installation initiale)")


def print_next_steps():
    """Affiche les prochaines étapes."""
    print("\n🎉 Setup terminé!")
    print("\n📋 Prochaines étapes:")
    print("1. Activer l'environnement: poetry shell")
    print("2. Lancer en mode dev: make dev")
    print("3. Tester les commandes MVP:")
    print("   - 'Ouvre Google Chrome'")
    print("   - 'Crée un fichier texte et écris Bonjour'")
    print("\n🔧 Commandes utiles:")
    print("- make help          : Aide")
    print("- make test          : Lancer les tests")
    print("- make lint          : Vérifier le code")
    print("- make clean         : Nettoyer")
    print("\n📚 Documentation:")
    print("- README.md          : Guide principal")
    print("- docs/              : Documentation complète")
    
    print(f"\n🖥️  Système détecté: {platform.system()} {platform.machine()}")
    
    if platform.system() == "Windows":
        print("💡 Sur Windows, utilisez PowerShell ou Git Bash")
        print("💡 Certaines commandes peuvent nécessiter des permissions administrateur")


def main():
    """Fonction principale."""
    print("🚀 Desktop Agent - Setup Initial")
    print("=" * 50)
    
    try:
        check_prerequisites()
        create_directories()
        install_python_deps()
        install_node_deps()
        setup_config()
        check_optional_deps()
        setup_development_env()
        run_tests()
        print_next_steps()
        
    except KeyboardInterrupt:
        print("\n❌ Setup interrompu par l'utilisateur")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erreur lors du setup: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()