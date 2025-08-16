const { contextBridge, ipcRenderer } = require('electron');

// Exposer les APIs sécurisées au renderer process
contextBridge.exposeInMainWorld('electronAPI', {
  // Configuration de l'overlay
  getOverlayConfig: () => ipcRenderer.invoke('get-overlay-config'),
  
  // Contrôle de la visibilité
  toggleOverlay: () => ipcRenderer.invoke('toggle-overlay'),
  showOverlay: () => ipcRenderer.invoke('show-overlay'),
  hideOverlay: () => ipcRenderer.invoke('hide-overlay'),
  getOverlayVisibility: () => ipcRenderer.invoke('get-overlay-visibility'),
  
  // Communication avec l'agent
  sendCommand: (commandData) => ipcRenderer.invoke('send-command', commandData),
  getSystemStatus: () => ipcRenderer.invoke('get-system-status'),
  
  // Notifications
  showNotification: (notificationData) => ipcRenderer.invoke('show-notification', notificationData),
  
  // Événements
  onOverlayVisibilityChanged: (callback) => {
    ipcRenderer.on('overlay-visibility-changed', (event, visible) => callback(visible));
  },
  
  onPushToTalkStart: (callback) => {
    ipcRenderer.on('push-to-talk-start', () => callback());
  },
  
  onPushToTalkEnd: (callback) => {
    ipcRenderer.on('push-to-talk-end', () => callback());
  },
  
  // Nettoyage des listeners
  removeAllListeners: (channel) => {
    ipcRenderer.removeAllListeners(channel);
  }
});

// Log pour debugging
console.log('Preload script loaded');

// Exposer des utilitaires supplémentaires
contextBridge.exposeInMainWorld('utils', {
  platform: process.platform,
  version: process.versions.electron,
  isDev: process.env.NODE_ENV === 'development'
});