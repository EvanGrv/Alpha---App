"""
Adaptateur Windows pour Desktop Agent.

Implémentation complète utilisant pywinauto, pygetwindow et les APIs Windows.
"""

import os
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

try:
    import pyautogui
    import pygetwindow as gw
    import pywinauto
    from pywinauto import Application, Desktop
    from pywinauto.controls.uiawrapper import UIAWrapper
    import win32api
    import win32con
    import win32gui
    WINDOWS_LIBS_AVAILABLE = True
except ImportError:
    WINDOWS_LIBS_AVAILABLE = False

from ...common.errors import (
    OSAdapterError,
    PlatformNotSupportedError,
    SystemCallError,
    AppNotFoundError,
    ElementNotFoundError,
    TimeoutError as AgentTimeoutError
)
from ...common.logging_utils import get_logger
from ...common.models import BoundingBox, Platform, UiElementRole, UiObject
from ...common.retry import retry
from ..base import OSAdapter

logger = get_logger("os_adapter.windows")


class WindowsAdapter(OSAdapter):
    """Adaptateur pour Windows utilisant pywinauto et UIAutomation."""
    
    def __init__(self):
        if not self.is_supported():
            raise PlatformNotSupportedError(
                "Windows adapter requires Windows platform and pywinauto"
            )
        
        # Configuration pyautogui
        pyautogui.FAILSAFE = False  # Désactiver le failsafe pour l'automatisation
        pyautogui.PAUSE = 0.1  # Pause entre les actions
        
        self._desktop = Desktop(backend="uia")
        self._running_apps: Dict[str, Application] = {}
        
        logger.info("Windows adapter initialisé")
    
    @property
    def platform(self) -> Platform:
        return Platform.WINDOWS
    
    def is_supported(self) -> bool:
        """Vérifie si l'adaptateur Windows est supporté."""
        import sys
        return sys.platform == "win32" and WINDOWS_LIBS_AVAILABLE
    
    # Gestion des applications
    
    @retry(max_attempts=3, base_delay=1.0)
    def open_app(self, name: str, **kwargs: Any) -> bool:
        """Ouvre une application Windows."""
        try:
            # Normaliser le nom de l'application
            app_name = self._normalize_app_name(name)
            
            # Vérifier si l'app est déjà ouverte
            if self._is_app_running(app_name):
                logger.info(f"Application {app_name} déjà ouverte")
                return self.focus_app(app_name)
            
            # Tenter d'ouvrir via différentes méthodes
            success = (
                self._open_via_start_menu(app_name) or
                self._open_via_command(app_name) or
                self._open_via_executable(app_name)
            )
            
            if success:
                # Attendre que l'application se lance
                time.sleep(2.0)
                logger.info(f"Application {app_name} ouverte avec succès")
                return True
            
            raise AppNotFoundError(f"Impossible d'ouvrir l'application: {app_name}")
            
        except Exception as e:
            logger.error(f"Erreur lors de l'ouverture de {name}: {e}")
            if isinstance(e, (AppNotFoundError, OSAdapterError)):
                raise
            raise SystemCallError(f"Erreur système lors de l'ouverture de {name}: {e}")
    
    def focus_app(self, name: str, **kwargs: Any) -> bool:
        """Met le focus sur une application."""
        try:
            app_name = self._normalize_app_name(name)
            
            # Chercher la fenêtre par titre
            windows = gw.getWindowsWithTitle(app_name)
            if not windows:
                # Recherche plus flexible
                all_windows = gw.getAllWindows()
                windows = [w for w in all_windows if app_name.lower() in w.title.lower()]
            
            if windows:
                window = windows[0]
                if window.isMinimized:
                    window.restore()
                window.activate()
                logger.info(f"Focus mis sur {app_name}")
                return True
            
            logger.warning(f"Fenêtre non trouvée pour {app_name}")
            return False
            
        except Exception as e:
            logger.error(f"Erreur lors du focus sur {name}: {e}")
            return False
    
    def close_app(self, name: str, **kwargs: Any) -> bool:
        """Ferme une application."""
        try:
            app_name = self._normalize_app_name(name)
            
            windows = gw.getWindowsWithTitle(app_name)
            if not windows:
                all_windows = gw.getAllWindows()
                windows = [w for w in all_windows if app_name.lower() in w.title.lower()]
            
            for window in windows:
                window.close()
            
            if windows:
                logger.info(f"Application {app_name} fermée")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Erreur lors de la fermeture de {name}: {e}")
            return False
    
    def get_running_apps(self) -> List[Dict[str, Any]]:
        """Retourne les applications en cours d'exécution."""
        try:
            windows = gw.getAllWindows()
            apps = []
            
            for window in windows:
                if window.title and window.visible:
                    apps.append({
                        "name": window.title,
                        "pid": getattr(window, "_hWnd", None),
                        "visible": window.visible,
                        "minimized": window.isMinimized,
                        "maximized": window.isMaximized,
                        "bounds": {
                            "x": window.left,
                            "y": window.top,
                            "width": window.width,
                            "height": window.height
                        }
                    })
            
            return apps
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des apps: {e}")
            return []
    
    # Contrôle de la souris
    
    def move_mouse(self, x: int, y: int) -> bool:
        """Déplace la souris."""
        try:
            pyautogui.moveTo(x, y)
            return True
        except Exception as e:
            logger.error(f"Erreur déplacement souris vers ({x}, {y}): {e}")
            return False
    
    def click(self, x: int, y: int, button: str = "left") -> bool:
        """Effectue un clic."""
        try:
            pyautogui.click(x, y, button=button)
            return True
        except Exception as e:
            logger.error(f"Erreur clic {button} à ({x}, {y}): {e}")
            return False
    
    def double_click(self, x: int, y: int, button: str = "left") -> bool:
        """Effectue un double-clic."""
        try:
            pyautogui.doubleClick(x, y, button=button)
            return True
        except Exception as e:
            logger.error(f"Erreur double-clic à ({x}, {y}): {e}")
            return False
    
    def drag(self, start_x: int, start_y: int, end_x: int, end_y: int) -> bool:
        """Effectue un glisser-déposer."""
        try:
            pyautogui.drag(end_x - start_x, end_y - start_y, 
                          duration=0.5, button='left')
            return True
        except Exception as e:
            logger.error(f"Erreur drag de ({start_x}, {start_y}) vers ({end_x}, {end_y}): {e}")
            return False
    
    def scroll(self, x: int, y: int, direction: str, amount: int = 3) -> bool:
        """Effectue un scroll."""
        try:
            pyautogui.moveTo(x, y)
            
            if direction.lower() in ["up", "down"]:
                clicks = amount if direction.lower() == "up" else -amount
                pyautogui.scroll(clicks)
            elif direction.lower() in ["left", "right"]:
                # Scroll horizontal avec Shift+Scroll
                pyautogui.keyDown('shift')
                clicks = amount if direction.lower() == "right" else -amount
                pyautogui.scroll(clicks)
                pyautogui.keyUp('shift')
            
            return True
        except Exception as e:
            logger.error(f"Erreur scroll {direction} à ({x}, {y}): {e}")
            return False
    
    def get_mouse_position(self) -> Tuple[int, int]:
        """Retourne la position de la souris."""
        try:
            return pyautogui.position()
        except Exception as e:
            logger.error(f"Erreur récupération position souris: {e}")
            return (0, 0)
    
    # Contrôle du clavier
    
    def type_text(self, text: str) -> bool:
        """Tape du texte."""
        try:
            pyautogui.typewrite(text, interval=0.01)
            return True
        except Exception as e:
            logger.error(f"Erreur saisie texte '{text}': {e}")
            return False
    
    def key_press(self, key: str) -> bool:
        """Appuie sur une touche."""
        try:
            pyautogui.keyDown(key)
            return True
        except Exception as e:
            logger.error(f"Erreur appui touche '{key}': {e}")
            return False
    
    def key_release(self, key: str) -> bool:
        """Relâche une touche."""
        try:
            pyautogui.keyUp(key)
            return True
        except Exception as e:
            logger.error(f"Erreur relâchement touche '{key}': {e}")
            return False
    
    def hotkey(self, *keys: str) -> bool:
        """Effectue une combinaison de touches."""
        try:
            pyautogui.hotkey(*keys)
            return True
        except Exception as e:
            logger.error(f"Erreur hotkey {keys}: {e}")
            return False
    
    # Gestion des fenêtres
    
    def get_active_window(self) -> Optional[UiObject]:
        """Retourne la fenêtre active."""
        try:
            active_window = gw.getActiveWindow()
            if active_window:
                return self._window_to_ui_object(active_window)
            return None
        except Exception as e:
            logger.error(f"Erreur récupération fenêtre active: {e}")
            return None
    
    def get_all_windows(self) -> List[UiObject]:
        """Retourne toutes les fenêtres."""
        try:
            windows = gw.getAllWindows()
            return [self._window_to_ui_object(w) for w in windows if w.title]
        except Exception as e:
            logger.error(f"Erreur récupération toutes les fenêtres: {e}")
            return []
    
    def get_window_by_title(self, title: str, partial: bool = True) -> Optional[UiObject]:
        """Trouve une fenêtre par titre."""
        try:
            if partial:
                windows = gw.getAllWindows()
                matching = [w for w in windows if title.lower() in w.title.lower()]
                if matching:
                    return self._window_to_ui_object(matching[0])
            else:
                windows = gw.getWindowsWithTitle(title)
                if windows:
                    return self._window_to_ui_object(windows[0])
            
            return None
        except Exception as e:
            logger.error(f"Erreur recherche fenêtre '{title}': {e}")
            return None
    
    def set_window_position(self, window_id: str, x: int, y: int) -> bool:
        """Définit la position d'une fenêtre."""
        try:
            window = self._get_window_by_id(window_id)
            if window:
                window.moveTo(x, y)
                return True
            return False
        except Exception as e:
            logger.error(f"Erreur positionnement fenêtre {window_id}: {e}")
            return False
    
    def set_window_size(self, window_id: str, width: int, height: int) -> bool:
        """Définit la taille d'une fenêtre."""
        try:
            window = self._get_window_by_id(window_id)
            if window:
                window.resizeTo(width, height)
                return True
            return False
        except Exception as e:
            logger.error(f"Erreur redimensionnement fenêtre {window_id}: {e}")
            return False
    
    def minimize_window(self, window_id: str) -> bool:
        """Minimise une fenêtre."""
        try:
            window = self._get_window_by_id(window_id)
            if window:
                window.minimize()
                return True
            return False
        except Exception as e:
            logger.error(f"Erreur minimisation fenêtre {window_id}: {e}")
            return False
    
    def maximize_window(self, window_id: str) -> bool:
        """Maximise une fenêtre."""
        try:
            window = self._get_window_by_id(window_id)
            if window:
                window.maximize()
                return True
            return False
        except Exception as e:
            logger.error(f"Erreur maximisation fenêtre {window_id}: {e}")
            return False
    
    # API d'accessibilité
    
    def get_ui_elements(
        self,
        window_id: Optional[str] = None,
        recursive: bool = True
    ) -> List[UiObject]:
        """Retourne les éléments UI."""
        try:
            if window_id:
                # Récupérer les éléments d'une fenêtre spécifique
                window = self._get_window_by_id(window_id)
                if not window:
                    return []
                
                # Utiliser pywinauto pour l'accessibilité
                app = Application(backend="uia").connect(title_re=f".*{window.title}.*")
                dialog = app.top_window()
                
            else:
                # Utiliser la fenêtre active
                active_window = gw.getActiveWindow()
                if not active_window:
                    return []
                
                app = Application(backend="uia").connect(title_re=f".*{active_window.title}.*")
                dialog = app.top_window()
            
            elements = []
            if recursive:
                elements = self._get_all_controls_recursive(dialog)
            else:
                elements = [self._control_to_ui_object(ctrl) for ctrl in dialog.children()]
            
            return [elem for elem in elements if elem is not None]
            
        except Exception as e:
            logger.error(f"Erreur récupération éléments UI: {e}")
            return []
    
    def find_element_by_name(
        self,
        name: str,
        window_id: Optional[str] = None,
        partial: bool = True
    ) -> Optional[UiObject]:
        """Trouve un élément par nom."""
        try:
            elements = self.get_ui_elements(window_id, recursive=True)
            
            for element in elements:
                if partial:
                    if name.lower() in element.name.lower():
                        return element
                else:
                    if element.name == name:
                        return element
            
            return None
            
        except Exception as e:
            logger.error(f"Erreur recherche élément '{name}': {e}")
            return None
    
    def find_elements_by_role(
        self,
        role: str,
        window_id: Optional[str] = None
    ) -> List[UiObject]:
        """Trouve des éléments par rôle."""
        try:
            elements = self.get_ui_elements(window_id, recursive=True)
            return [elem for elem in elements if elem.role.value == role]
        except Exception as e:
            logger.error(f"Erreur recherche éléments par rôle '{role}': {e}")
            return []
    
    def click_element(self, element_id: str) -> bool:
        """Clique sur un élément UI."""
        try:
            # Pour l'instant, utiliser l'ID comme nom d'élément
            # Dans une implémentation complète, on garderait une map des éléments
            element = self.find_element_by_name(element_id)
            if element:
                center = element.bounds.center
                return self.click(center[0], center[1])
            return False
        except Exception as e:
            logger.error(f"Erreur clic élément '{element_id}': {e}")
            return False
    
    def set_element_text(self, element_id: str, text: str) -> bool:
        """Définit le texte d'un élément."""
        try:
            element = self.find_element_by_name(element_id)
            if element:
                # Cliquer sur l'élément puis taper le texte
                center = element.bounds.center
                self.click(center[0], center[1])
                time.sleep(0.1)
                
                # Sélectionner tout et remplacer
                self.hotkey('ctrl', 'a')
                time.sleep(0.1)
                return self.type_text(text)
            return False
        except Exception as e:
            logger.error(f"Erreur définition texte élément '{element_id}': {e}")
            return False
    
    # Gestion des fichiers
    
    def open_file_dialog(self, dialog_type: str = "open") -> Optional[str]:
        """Ouvre un dialogue de fichier."""
        try:
            if dialog_type == "open":
                self.hotkey('ctrl', 'o')
            elif dialog_type == "save":
                self.hotkey('ctrl', 's')
            else:
                return None
            
            # Attendre que le dialogue s'ouvre
            time.sleep(1.0)
            
            # TODO: Implémenter la sélection de fichier
            # Pour l'instant, retourner None
            return None
            
        except Exception as e:
            logger.error(f"Erreur ouverture dialogue fichier '{dialog_type}': {e}")
            return None
    
    def get_default_app_for_file(self, file_path: str) -> Optional[str]:
        """Retourne l'app par défaut pour un fichier."""
        try:
            import winreg
            
            # Obtenir l'extension
            _, ext = os.path.splitext(file_path)
            if not ext:
                return None
            
            # Chercher dans le registre
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, ext) as key:
                file_type = winreg.QueryValue(key, None)
            
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, 
                               f"{file_type}\\shell\\open\\command") as key:
                command = winreg.QueryValue(key, None)
            
            # Extraire le nom de l'application
            app_path = command.split('"')[1] if '"' in command else command.split()[0]
            return os.path.basename(app_path)
            
        except Exception as e:
            logger.error(f"Erreur récupération app par défaut pour {file_path}: {e}")
            return None
    
    # Utilitaires
    
    def take_screenshot(self, region: Optional[BoundingBox] = None) -> bytes:
        """Prend une capture d'écran."""
        try:
            if region:
                screenshot = pyautogui.screenshot(
                    region=(region.x, region.y, region.width, region.height)
                )
            else:
                screenshot = pyautogui.screenshot()
            
            # Convertir en bytes
            import io
            img_bytes = io.BytesIO()
            screenshot.save(img_bytes, format='PNG')
            return img_bytes.getvalue()
            
        except Exception as e:
            logger.error(f"Erreur capture d'écran: {e}")
            return b""
    
    def wait_for_element(
        self,
        element_name: str,
        timeout: float = 10.0,
        window_id: Optional[str] = None
    ) -> Optional[UiObject]:
        """Attend qu'un élément apparaisse."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            element = self.find_element_by_name(element_name, window_id)
            if element:
                return element
            time.sleep(0.5)
        
        return None
    
    def wait_for_window(
        self,
        window_title: str,
        timeout: float = 10.0
    ) -> Optional[UiObject]:
        """Attend qu'une fenêtre apparaisse."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            window = self.get_window_by_title(window_title)
            if window:
                return window
            time.sleep(0.5)
        
        return None
    
    # Méthodes privées
    
    def _normalize_app_name(self, name: str) -> str:
        """Normalise le nom d'une application."""
        # Mapping des noms communs
        app_mapping = {
            "chrome": "Google Chrome",
            "firefox": "Firefox",
            "edge": "Microsoft Edge",
            "notepad": "Notepad",
            "word": "Microsoft Word",
            "excel": "Microsoft Excel",
            "powerpoint": "Microsoft PowerPoint",
            "explorer": "File Explorer",
            "calculator": "Calculator",
            "paint": "Paint"
        }
        
        normalized = name.lower().strip()
        return app_mapping.get(normalized, name)
    
    def _is_app_running(self, app_name: str) -> bool:
        """Vérifie si une app est en cours d'exécution."""
        windows = gw.getAllWindows()
        return any(app_name.lower() in w.title.lower() for w in windows if w.title)
    
    def _open_via_start_menu(self, app_name: str) -> bool:
        """Tente d'ouvrir via le menu Démarrer."""
        try:
            # Ouvrir le menu Démarrer
            pyautogui.press('win')
            time.sleep(0.5)
            
            # Taper le nom de l'application
            pyautogui.typewrite(app_name)
            time.sleep(0.5)
            
            # Appuyer sur Entrée
            pyautogui.press('enter')
            return True
            
        except Exception as e:
            logger.warning(f"Échec ouverture via menu Démarrer: {e}")
            return False
    
    def _open_via_command(self, app_name: str) -> bool:
        """Tente d'ouvrir via ligne de commande."""
        try:
            # Commandes connues
            commands = {
                "Google Chrome": "chrome",
                "Firefox": "firefox",
                "Microsoft Edge": "msedge",
                "Notepad": "notepad",
                "Calculator": "calc",
                "Paint": "mspaint"
            }
            
            command = commands.get(app_name)
            if command:
                subprocess.Popen(command, shell=True)
                return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Échec ouverture via commande: {e}")
            return False
    
    def _open_via_executable(self, app_name: str) -> bool:
        """Tente d'ouvrir via exécutable."""
        try:
            # Chemins communs d'installation
            common_paths = [
                f"C:\\Program Files\\{app_name}",
                f"C:\\Program Files (x86)\\{app_name}",
                f"C:\\Users\\{os.getenv('USERNAME')}\\AppData\\Local\\{app_name}"
            ]
            
            for path in common_paths:
                if os.path.exists(path):
                    # Chercher l'exécutable
                    for file in os.listdir(path):
                        if file.endswith('.exe'):
                            subprocess.Popen(os.path.join(path, file))
                            return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Échec ouverture via exécutable: {e}")
            return False
    
    def _window_to_ui_object(self, window) -> UiObject:
        """Convertit une fenêtre en UiObject."""
        return UiObject(
            name=window.title,
            role=UiElementRole.WINDOW,
            bounds=BoundingBox(
                x=window.left,
                y=window.top,
                width=window.width,
                height=window.height
            ),
            visible=window.visible,
            properties={
                "minimized": window.isMinimized,
                "maximized": window.isMaximized,
                "handle": getattr(window, "_hWnd", None)
            }
        )
    
    def _get_window_by_id(self, window_id: str):
        """Récupère une fenêtre par ID."""
        # Pour simplifier, utiliser le titre comme ID
        windows = gw.getAllWindows()
        for window in windows:
            if window.title == window_id:
                return window
        return None
    
    def _control_to_ui_object(self, control) -> Optional[UiObject]:
        """Convertit un contrôle pywinauto en UiObject."""
        try:
            if not hasattr(control, 'window_text'):
                return None
            
            rect = control.rectangle()
            
            return UiObject(
                name=control.window_text(),
                role=self._map_control_type(control.element_info.control_type),
                bounds=BoundingBox(
                    x=rect.left,
                    y=rect.top,
                    width=rect.width(),
                    height=rect.height()
                ),
                text=getattr(control, 'window_text', lambda: "")(),
                enabled=control.is_enabled(),
                visible=control.is_visible(),
                properties={
                    "class_name": control.class_name(),
                    "control_type": control.element_info.control_type
                }
            )
            
        except Exception as e:
            logger.warning(f"Erreur conversion contrôle: {e}")
            return None
    
    def _get_all_controls_recursive(self, parent, max_depth: int = 3, current_depth: int = 0) -> List[UiObject]:
        """Récupère tous les contrôles récursivement."""
        if current_depth >= max_depth:
            return []
        
        controls = []
        
        try:
            for child in parent.children():
                ui_obj = self._control_to_ui_object(child)
                if ui_obj:
                    controls.append(ui_obj)
                
                # Récursion sur les enfants
                if current_depth < max_depth - 1:
                    controls.extend(
                        self._get_all_controls_recursive(child, max_depth, current_depth + 1)
                    )
        
        except Exception as e:
            logger.warning(f"Erreur parcours récursif: {e}")
        
        return controls
    
    def _map_control_type(self, control_type: int) -> UiElementRole:
        """Mappe les types de contrôles Windows vers UiElementRole."""
        # Mapping basique des types de contrôles UIAutomation
        mapping = {
            50000: UiElementRole.BUTTON,     # Button
            50004: UiElementRole.TEXT,       # Text
            50003: UiElementRole.TEXTBOX,    # Edit
            50032: UiElementRole.WINDOW,     # Window
            50009: UiElementRole.MENUITEM,   # MenuItem
            50005: UiElementRole.LINK,       # Hyperlink
            50006: UiElementRole.IMAGE,      # Image
            50008: UiElementRole.LIST,       # List
            50007: UiElementRole.LISTITEM,   # ListItem
        }
        
        return mapping.get(control_type, UiElementRole.UNKNOWN)