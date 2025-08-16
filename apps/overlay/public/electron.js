const { app, BrowserWindow, globalShortcut, ipcMain, screen } = require('electron');
const path = require('path');
const isDev = require('electron-is-dev');

let mainWindow;
let overlayVisible = true;

// Configuration de l'overlay
const OVERLAY_CONFIG = {
  height: 60,
  opacity: 0.9,
  hotkey: 'CommandOrControl+`',
  pushToTalkKey: 'Alt+Space'
};

function createWindow() {
  // Obtenir les dimensions de l'écran principal
  const primaryDisplay = screen.getPrimaryDisplay();
  const { width: screenWidth, height: screenHeight } = primaryDisplay.workAreaSize;

  // Créer la fenêtre overlay
  mainWindow = new BrowserWindow({
    width: screenWidth,
    height: OVERLAY_CONFIG.height,
    x: 0,
    y: screenHeight - OVERLAY_CONFIG.height,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    movable: false,
    minimizable: false,
    maximizable: false,
    closable: true,
    focusable: true,
    opacity: OVERLAY_CONFIG.opacity,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      enableRemoteModule: false,
      preload: path.join(__dirname, 'preload.js')
    }
  });

  // Charger l'application React
  const startUrl = isDev 
    ? 'http://localhost:3000' 
    : `file://${path.join(__dirname, '../build/index.html')}`;
  
  mainWindow.loadURL(startUrl);

  // Ouvrir les DevTools en mode développement
  if (isDev) {
    mainWindow.webContents.openDevTools();
  }

  // Empêcher la fermeture de la fenêtre (la masquer à la place)
  mainWindow.on('close', (event) => {
    if (!app.isQuiting) {
      event.preventDefault();
      hideOverlay();
    }
  });

  // Gérer la perte de focus
  mainWindow.on('blur', () => {
    // Auto-masquer après un délai si configuré
    setTimeout(() => {
      if (overlayVisible && !mainWindow.isFocused()) {
        hideOverlay();
      }
    }, 5000); // 5 secondes
  });

  console.log('Overlay window created');
}

function showOverlay() {
  if (mainWindow && !overlayVisible) {
    mainWindow.show();
    mainWindow.focus();
    overlayVisible = true;
    
    // Notifier React de la visibilité
    mainWindow.webContents.send('overlay-visibility-changed', true);
    
    console.log('Overlay shown');
  }
}

function hideOverlay() {
  if (mainWindow && overlayVisible) {
    mainWindow.hide();
    overlayVisible = false;
    
    // Notifier React de la visibilité
    mainWindow.webContents.send('overlay-visibility-changed', false);
    
    console.log('Overlay hidden');
  }
}

function toggleOverlay() {
  if (overlayVisible) {
    hideOverlay();
  } else {
    showOverlay();
  }
}

// Gestion des raccourcis globaux
function registerGlobalShortcuts() {
  // Toggle overlay
  globalShortcut.register(OVERLAY_CONFIG.hotkey, () => {
    console.log('Toggle overlay hotkey pressed');
    toggleOverlay();
  });

  // Push-to-talk (maintenir enfoncé)
  let pushToTalkPressed = false;
  
  globalShortcut.register(OVERLAY_CONFIG.pushToTalkKey, () => {
    if (!pushToTalkPressed) {
      pushToTalkPressed = true;
      console.log('Push-to-talk started');
      
      // Notifier React du début d'enregistrement
      if (mainWindow) {
        mainWindow.webContents.send('push-to-talk-start');
      }
    }
  });

  // Note: La détection du relâchement nécessite une approche différente
  // Pour l'instant, on simule avec un timeout
  setInterval(() => {
    if (pushToTalkPressed) {
      // Vérifier si la touche est toujours enfoncée (simplification)
      // Dans une implémentation complète, utiliser des hooks système natifs
      pushToTalkPressed = false;
      console.log('Push-to-talk ended');
      
      if (mainWindow) {
        mainWindow.webContents.send('push-to-talk-end');
      }
    }
  }, 100);

  console.log('Global shortcuts registered');
}

// Événements de l'application
app.whenReady().then(() => {
  createWindow();
  registerGlobalShortcuts();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  globalShortcut.unregisterAll();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('will-quit', () => {
  // Désenregistrer tous les raccourcis globaux
  globalShortcut.unregisterAll();
  app.isQuiting = true;
});

// IPC handlers
ipcMain.handle('get-overlay-config', () => {
  return OVERLAY_CONFIG;
});

ipcMain.handle('toggle-overlay', () => {
  toggleOverlay();
});

ipcMain.handle('show-overlay', () => {
  showOverlay();
});

ipcMain.handle('hide-overlay', () => {
  hideOverlay();
});

ipcMain.handle('get-overlay-visibility', () => {
  return overlayVisible;
});

ipcMain.handle('send-command', async (event, commandData) => {
  console.log('Command received from renderer:', commandData);
  
  // Ici, on enverrait la commande à l'API FastAPI
  // Pour l'instant, on simule une réponse
  
  try {
    // Intégration avec l'API FastAPI
    const response = await fetch('http://localhost:8000/command', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(commandData)
    });
    
    const result = await response.json();
    return result;
  } catch (error) {
    console.error('Error sending command:', error);
    return {
      success: false,
      error: error.message,
      message: 'Erreur de connexion à l\'agent'
    };
  }
});

ipcMain.handle('get-system-status', async () => {
  try {
    const response = await fetch('http://localhost:8000/observation');
    const status = await response.json();
    return status;
  } catch (error) {
    console.error('Error getting system status:', error);
    return {
      error: error.message,
      message: 'Service agent non disponible'
    };
  }
});

// Gestion des notifications
ipcMain.handle('show-notification', (event, { title, body, type = 'info' }) => {
  // Utiliser les notifications système
  const { Notification } = require('electron');
  
  if (Notification.isSupported()) {
    new Notification({
      title: title || 'Desktop Agent',
      body: body,
      icon: path.join(__dirname, 'assets/icon.png') // TODO: Ajouter l'icône
    }).show();
  }
});

console.log('Electron main process started');