"""
Interface en ligne de commande pour Desktop Agent.

Fournit des commandes pour tester, déboguer et gérer l'agent.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

# Ajouter le répertoire racine au path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from packages.common.config import get_settings, setup_logging
from packages.common.logging_utils import get_agent_logger
from packages.common.models import Command, CommandSource
from packages.skills import SkillManager
from packages.nlu import NLUManager
from packages.planner import PlannerManager
from packages.perception import PerceptionManager

console = Console()


@click.group()
@click.option('--config', '-c', help='Fichier de configuration')
@click.option('--debug', '-d', is_flag=True, help='Mode debug')
def cli(config: Optional[str], debug: bool):
    """Desktop Agent CLI - Interface en ligne de commande."""
    # Configuration
    if config:
        # TODO: Charger config personnalisée
        pass
    
    settings = get_settings()
    if debug:
        settings.debug = True
    
    # Setup logging
    setup_logging(settings.logging, "desktop-agent-cli")


@cli.command()
@click.argument('text')
@click.option('--source', '-s', default='text', type=click.Choice(['text', 'voice']), 
              help='Source de la commande')
@click.option('--confirm', '-y', is_flag=True, help='Confirmer automatiquement')
async def execute(text: str, source: str, confirm: bool):
    """Exécute une commande via l'agent."""
    try:
        console.print(f"[blue]Exécution de la commande:[/blue] {text}")
        
        # Initialiser les services
        skill_manager = SkillManager()
        nlu_manager = NLUManager()
        planner_manager = PlannerManager(skill_manager)
        perception_manager = PerceptionManager()
        
        from .services import AgentService
        
        agent_service = AgentService(
            skill_manager=skill_manager,
            nlu_manager=nlu_manager,
            planner_manager=planner_manager,
            perception_manager=perception_manager
        )
        
        await agent_service.start()
        
        # Créer la commande
        command = Command(
            source=CommandSource(source),
            text=text,
            require_confirmation=not confirm
        )
        
        # Traiter la commande
        result = await agent_service.process_command(command)
        
        # Afficher le résultat
        if result["success"]:
            console.print(f"[green]✓ Succès:[/green] {result['message']}")
            
            if result["stage"] == "confirmation_required" and not confirm:
                console.print(f"[yellow]Plan généré:[/yellow] {result['plan_summary']}")
                
                if click.confirm("Voulez-vous exécuter ce plan?"):
                    exec_result = await agent_service.execute_plan_by_id(result["plan_id"])
                    
                    if exec_result["success"]:
                        console.print(f"[green]✓ Exécution réussie:[/green] {exec_result['message']}")
                    else:
                        console.print(f"[red]✗ Exécution échouée:[/red] {exec_result['message']}")
        else:
            console.print(f"[red]✗ Échec:[/red] {result['message']}")
            
            if "suggestions" in result:
                console.print("[yellow]Suggestions:[/yellow]")
                for suggestion in result.get("suggestions", {}).values():
                    if isinstance(suggestion, list):
                        for item in suggestion[:3]:
                            console.print(f"  - {item}")
        
        await agent_service.stop()
        
    except Exception as e:
        console.print(f"[red]Erreur:[/red] {e}")
        sys.exit(1)


@cli.command()
def test():
    """Teste tous les composants de l'agent."""
    console.print("[blue]Test des composants Desktop Agent[/blue]")
    
    try:
        # Test des skills
        console.print("\n[yellow]Test des compétences...[/yellow]")
        skill_manager = SkillManager()
        
        table = Table(title="Résultats des tests de compétences")
        table.add_column("Compétence", style="cyan")
        table.add_column("Statut", style="green")
        table.add_column("Statistiques", style="blue")
        
        for skill_name in skill_manager.list_skills():
            skill_info = skill_manager.get_skill_info(skill_name)
            stats = skill_info["stats"]
            
            status = "✓ Disponible"
            stats_text = f"Exécutions: {stats['execution_count']}, Succès: {stats['success_rate']:.1%}"
            
            table.add_row(skill_name, status, stats_text)
        
        console.print(table)
        
        # Test NLU
        console.print("\n[yellow]Test NLU...[/yellow]")
        nlu_manager = NLUManager()
        
        test_phrases = [
            "Ouvre Google Chrome",
            "Écris bonjour",
            "Clique sur OK",
            "Crée un fichier texte"
        ]
        
        nlu_table = Table(title="Test d'analyse NLU")
        nlu_table.add_column("Phrase", style="cyan")
        nlu_table.add_column("Intention", style="green")
        nlu_table.add_column("Confiance", style="blue")
        
        for phrase in test_phrases:
            result = nlu_manager.understand(phrase)
            intent = result["intent"]["type"]
            confidence = f"{result['intent']['confidence']:.1%}"
            
            nlu_table.add_row(phrase, intent, confidence)
        
        console.print(nlu_table)
        
        console.print("\n[green]✓ Tests terminés avec succès[/green]")
        
    except Exception as e:
        console.print(f"[red]Erreur lors des tests:[/red] {e}")
        sys.exit(1)


@cli.command()
def status():
    """Affiche le statut des composants."""
    console.print("[blue]Statut Desktop Agent[/blue]")
    
    try:
        settings = get_settings()
        
        # Informations générales
        info_panel = Panel(
            f"Version: 0.1.0\n"
            f"Plateforme: {settings.platform.value}\n"
            f"Mode debug: {'Activé' if settings.debug else 'Désactivé'}\n"
            f"API: {settings.api_host}:{settings.api_port}",
            title="Informations générales",
            border_style="blue"
        )
        console.print(info_panel)
        
        # Initialiser les gestionnaires pour les stats
        skill_manager = SkillManager()
        nlu_manager = NLUManager()
        
        # Statistiques des composants
        stats_table = Table(title="Statistiques des composants")
        stats_table.add_column("Composant", style="cyan")
        stats_table.add_column("Statut", style="green")
        stats_table.add_column("Détails", style="blue")
        
        # Skills
        skill_stats = skill_manager.get_manager_stats()
        stats_table.add_row(
            "Compétences",
            "✓ Actif",
            f"{skill_stats['total_skills']} compétences, "
            f"{skill_stats['total_executions']} exécutions"
        )
        
        # NLU
        nlu_stats = nlu_manager.get_nlu_stats()
        stats_table.add_row(
            "NLU",
            "✓ Actif", 
            f"{nlu_stats['processed_count']} analyses, "
            f"Taux succès: {nlu_stats['success_rate']:.1%}"
        )
        
        # Configuration
        stats_table.add_row(
            "Configuration",
            "✓ Chargée",
            f"OCR: {settings.perception.ocr_language}, "
            f"Hotkey: {settings.ui.overlay_hotkey}"
        )
        
        console.print(stats_table)
        
    except Exception as e:
        console.print(f"[red]Erreur récupération statut:[/red] {e}")
        sys.exit(1)


@cli.command()
@click.argument('skill_name')
def skill_info(skill_name: str):
    """Affiche des informations détaillées sur une compétence."""
    try:
        skill_manager = SkillManager()
        info = skill_manager.get_skill_info(skill_name)
        
        if not info:
            console.print(f"[red]Compétence '{skill_name}' non trouvée[/red]")
            sys.exit(1)
        
        # Panneau principal
        main_info = Panel(
            f"Description: {info['description']}\n"
            f"Classe: {info['class_name']}\n"
            f"Exécutions: {info['stats']['execution_count']}\n"
            f"Taux de succès: {info['stats']['success_rate']:.1%}\n"
            f"Durée moyenne: {info['stats']['average_duration']:.2f}s",
            title=f"Compétence: {skill_name}",
            border_style="green"
        )
        console.print(main_info)
        
        # Schéma des paramètres
        console.print("\n[yellow]Schéma des paramètres:[/yellow]")
        console.print(json.dumps(info['parameter_schema'], indent=2))
        
        # Exemples
        if info['examples']:
            console.print("\n[yellow]Exemples d'utilisation:[/yellow]")
            for i, example in enumerate(info['examples'], 1):
                console.print(f"{i}. {json.dumps(example, indent=2)}")
        
    except Exception as e:
        console.print(f"[red]Erreur:[/red] {e}")
        sys.exit(1)


@cli.command()
@click.argument('text')
def analyze(text: str):
    """Analyse une phrase avec le NLU sans l'exécuter."""
    try:
        console.print(f"[blue]Analyse de:[/blue] {text}")
        
        nlu_manager = NLUManager()
        result = nlu_manager.understand(text)
        
        # Intention
        intent_panel = Panel(
            f"Type: {result['intent']['type']}\n"
            f"Confiance: {result['intent']['confidence']:.1%}\n"
            f"Texte original: {result['intent']['original_text']}\n"
            f"Texte normalisé: {result['intent']['normalized_text']}",
            title="Intention détectée",
            border_style="green"
        )
        console.print(intent_panel)
        
        # Slots
        if result['slots']:
            console.print("\n[yellow]Paramètres extraits:[/yellow]")
            for key, value in result['slots'].items():
                console.print(f"  {key}: {value}")
        
        # Validation
        validation = result['validation']
        if validation['errors']:
            console.print("\n[red]Erreurs de validation:[/red]")
            for error in validation['errors']:
                console.print(f"  ✗ {error}")
        
        if validation['warnings']:
            console.print("\n[yellow]Avertissements:[/yellow]")
            for warning in validation['warnings']:
                console.print(f"  ⚠ {warning}")
        
        # Prêt pour exécution
        ready = result['ready_for_execution']
        status_color = "green" if ready else "red"
        status_text = "Prêt pour exécution" if ready else "Non prêt pour exécution"
        console.print(f"\n[{status_color}]{status_text}[/{status_color}]")
        
    except Exception as e:
        console.print(f"[red]Erreur:[/red] {e}")
        sys.exit(1)


@cli.command()
def interactive():
    """Mode interactif pour tester l'agent."""
    console.print("[blue]Mode interactif Desktop Agent[/blue]")
    console.print("Tapez 'quit' pour quitter, 'help' pour l'aide")
    
    try:
        # Initialiser les services
        skill_manager = SkillManager()
        nlu_manager = NLUManager()
        
        while True:
            try:
                text = input("\n> ").strip()
                
                if not text:
                    continue
                
                if text.lower() in ['quit', 'exit', 'q']:
                    break
                
                if text.lower() == 'help':
                    console.print("""
[yellow]Commandes disponibles:[/yellow]
- Tapez une commande en langage naturel pour l'analyser
- 'analyze <texte>' : Analyse seulement (sans exécution)
- 'status' : Affiche le statut
- 'skills' : Liste les compétences
- 'quit' : Quitter
                    """)
                    continue
                
                if text.startswith('analyze '):
                    # Analyse seulement
                    query = text[8:]
                    result = nlu_manager.understand(query)
                    console.print(f"Intention: {result['intent']['type']} "
                                f"(confiance: {result['intent']['confidence']:.1%})")
                    
                elif text == 'status':
                    console.print("Service actif - Mode interactif")
                    
                elif text == 'skills':
                    skills = skill_manager.list_skills()
                    console.print(f"Compétences disponibles: {', '.join(skills)}")
                    
                else:
                    # Analyser la commande
                    result = nlu_manager.understand(text)
                    
                    console.print(f"[green]Intention:[/green] {result['intent']['type']} "
                                f"(confiance: {result['intent']['confidence']:.1%})")
                    
                    if result['slots']:
                        console.print(f"[blue]Paramètres:[/blue] {result['slots']}")
                    
                    if not result['ready_for_execution']:
                        console.print("[red]⚠ Commande incomplète ou non valide[/red]")
                        if result['validation']['errors']:
                            for error in result['validation']['errors']:
                                console.print(f"  - {error}")
                    else:
                        console.print("[green]✓ Commande prête pour exécution[/green]")
                        console.print("[yellow]Note: Mode interactif - exécution simulée seulement[/yellow]")
            
            except KeyboardInterrupt:
                break
            except Exception as e:
                console.print(f"[red]Erreur:[/red] {e}")
        
        console.print("\n[blue]Au revoir![/blue]")
        
    except Exception as e:
        console.print(f"[red]Erreur mode interactif:[/red] {e}")
        sys.exit(1)


if __name__ == '__main__':
    # Adapter pour asyncio si nécessaire
    import inspect
    
    original_cli = cli
    
    def async_cli():
        # Wrapper pour gérer les commandes async
        for command_name, command in cli.commands.items():
            if inspect.iscoroutinefunction(command.callback):
                # Wrapper la commande async
                original_callback = command.callback
                
                def make_sync_wrapper(async_func):
                    def sync_wrapper(*args, **kwargs):
                        return asyncio.run(async_func(*args, **kwargs))
                    return sync_wrapper
                
                command.callback = make_sync_wrapper(original_callback)
        
        original_cli()
    
    async_cli()