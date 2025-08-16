#!/usr/bin/env python3
"""Script de développement pour Desktop Agent."""

import asyncio
import signal
import sys
import subprocess
import time
from pathlib import Path
import argparse


class DevServer:
    """Gestionnaire des serveurs de développement."""
    
    def __init__(self):
        self.processes = []
        self.running = False
    
    async def start_agent(self, port=8000, reload=True):
        """Démarre l'agent FastAPI."""
        print(f"🤖 Démarrage agent sur port {port}...")
        
        cmd = [
            "poetry", "run", "uvicorn", 
            "apps.agent.main:app",
            "--host", "0.0.0.0",
            "--port", str(port)
        ]
        
        if reload:
            cmd.append("--reload")
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        self.processes.append(("agent", process))
        return process
    
    async def start_overlay(self):
        """Démarre l'overlay Electron."""
        print("🖥️  Démarrage overlay...")
        
        overlay_dir = Path("apps/overlay")
        
        if not overlay_dir.exists():
            print("❌ Dossier overlay non trouvé")
            return None
        
        cmd = ["npm", "run", "dev"]
        
        process = subprocess.Popen(
            cmd,
            cwd=overlay_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        self.processes.append(("overlay", process))
        return process
    
    async def monitor_processes(self):
        """Surveille les processus et affiche les logs."""
        print("📊 Surveillance des processus...")
        
        while self.running:
            for name, process in self.processes:
                if process.poll() is not None:
                    print(f"❌ {name} s'est arrêté (code: {process.returncode})")
                    
                    # Lire les dernières sorties
                    try:
                        output = process.stdout.read()
                        if output:
                            print(f"[{name}] {output}")
                    except:
                        pass
            
            await asyncio.sleep(1)
    
    async def start_all(self, agent_port=8000, overlay=True):
        """Démarre tous les services."""
        self.running = True
        
        try:
            # Démarrer l'agent
            await self.start_agent(port=agent_port)
            
            # Attendre un peu que l'agent démarre
            await asyncio.sleep(2)
            
            # Démarrer l'overlay si demandé
            if overlay:
                await self.start_overlay()
                await asyncio.sleep(2)
            
            print("\n✅ Services démarrés!")
            print(f"🔗 Agent: http://localhost:{agent_port}")
            print(f"🔗 API Docs: http://localhost:{agent_port}/docs")
            
            if overlay:
                print("🔗 Overlay: Interface Electron")
            
            print("\n⌨️  Raccourcis:")
            print("  Ctrl+` : Toggle overlay")
            print("  Alt+Space : Push-to-talk")
            print("  Ctrl+C : Arrêter tous les services")
            print("\n📝 Logs en temps réel:")
            print("-" * 50)
            
            # Surveiller les processus
            await self.monitor_processes()
            
        except Exception as e:
            print(f"❌ Erreur: {e}")
            await self.stop_all()
    
    async def stop_all(self):
        """Arrête tous les services."""
        print("\n🛑 Arrêt des services...")
        self.running = False
        
        for name, process in self.processes:
            if process.poll() is None:
                print(f"🔴 Arrêt {name}...")
                process.terminate()
                
                # Attendre un peu
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    print(f"⚡ Force kill {name}...")
                    process.kill()
        
        self.processes.clear()
        print("✅ Tous les services arrêtés")
    
    def setup_signal_handlers(self):
        """Configure les gestionnaires de signaux."""
        def signal_handler(signum, frame):
            print(f"\n📡 Signal reçu: {signum}")
            asyncio.create_task(self.stop_all())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)


class LogMonitor:
    """Moniteur de logs en temps réel."""
    
    def __init__(self):
        self.log_files = [
            "data/logs/agent.log",
            "data/logs/overlay.log"
        ]
    
    async def tail_logs(self):
        """Affiche les logs en temps réel."""
        print("📋 Monitoring des logs...")
        
        # Pour l'instant, on simule
        while True:
            await asyncio.sleep(5)
            print("📋 Logs monitoring... (implémentation à venir)")


def check_environment():
    """Vérifie l'environnement de développement."""
    print("🔍 Vérification de l'environnement...")
    
    # Vérifier Poetry
    try:
        subprocess.run(["poetry", "--version"], check=True, capture_output=True)
        print("✅ Poetry disponible")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Poetry non trouvé")
        return False
    
    # Vérifier Node.js pour overlay
    overlay_dir = Path("apps/overlay")
    if overlay_dir.exists():
        try:
            subprocess.run(["npm", "--version"], check=True, capture_output=True, cwd=overlay_dir)
            print("✅ npm disponible")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("❌ npm non trouvé pour overlay")
            return False
    
    # Vérifier les dossiers
    required_dirs = ["apps/agent", "packages"]
    for dir_path in required_dirs:
        if not Path(dir_path).exists():
            print(f"❌ Dossier manquant: {dir_path}")
            return False
        print(f"✅ {dir_path}")
    
    return True


async def main():
    """Fonction principale."""
    parser = argparse.ArgumentParser(description="Serveur de développement Desktop Agent")
    
    parser.add_argument("--port", type=int, default=8000, help="Port de l'agent")
    parser.add_argument("--no-overlay", action="store_true", help="Ne pas démarrer l'overlay")
    parser.add_argument("--agent-only", action="store_true", help="Démarrer seulement l'agent")
    parser.add_argument("--overlay-only", action="store_true", help="Démarrer seulement l'overlay")
    parser.add_argument("--check", action="store_true", help="Vérifier l'environnement seulement")
    
    args = parser.parse_args()
    
    print("🚀 Desktop Agent - Serveur de Développement")
    print("=" * 50)
    
    # Vérification de l'environnement
    if not check_environment():
        print("\n❌ Environnement non configuré correctement")
        print("💡 Lancez: python scripts/setup.py")
        sys.exit(1)
    
    if args.check:
        print("\n✅ Environnement OK")
        return
    
    # Créer le serveur
    dev_server = DevServer()
    dev_server.setup_signal_handlers()
    
    try:
        if args.agent_only:
            print("🤖 Mode: Agent seulement")
            await dev_server.start_all(agent_port=args.port, overlay=False)
            
        elif args.overlay_only:
            print("🖥️  Mode: Overlay seulement")
            await dev_server.start_overlay()
            await dev_server.monitor_processes()
            
        else:
            print("🔄 Mode: Complet (Agent + Overlay)")
            overlay = not args.no_overlay
            await dev_server.start_all(agent_port=args.port, overlay=overlay)
    
    except KeyboardInterrupt:
        print("\n👋 Arrêt demandé par l'utilisateur")
    
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await dev_server.stop_all()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Au revoir!")
    except Exception as e:
        print(f"❌ Erreur fatale: {e}")
        sys.exit(1)