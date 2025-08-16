import { useEffect, useCallback } from 'react';

// Types pour les APIs Electron
interface ElectronAPI {
  getOverlayConfig: () => Promise<any>;
  toggleOverlay: () => Promise<void>;
  showOverlay: () => Promise<void>;
  hideOverlay: () => Promise<void>;
  getOverlayVisibility: () => Promise<boolean>;
  sendCommand: (commandData: any) => Promise<any>;
  getSystemStatus: () => Promise<any>;
  showNotification: (notificationData: any) => Promise<void>;
  onOverlayVisibilityChanged: (callback: (visible: boolean) => void) => void;
  onPushToTalkStart: (callback: () => void) => void;
  onPushToTalkEnd: (callback: () => void) => void;
  removeAllListeners: (channel: string) => void;
}

interface Utils {
  platform: string;
  version: string;
  isDev: boolean;
}

declare global {
  interface Window {
    electronAPI: ElectronAPI;
    utils: Utils;
  }
}

export const useElectron = () => {
  const isElectron = typeof window !== 'undefined' && window.electronAPI;

  const sendCommand = useCallback(async (commandData: {
    source: 'text' | 'voice';
    text: string;
    require_confirmation?: boolean;
  }) => {
    if (!isElectron) {
      // Fallback pour le développement web
      console.log('Sending command (fallback):', commandData);
      return {
        success: true,
        message: 'Mode développement - commande simulée',
        stage: 'completed'
      };
    }

    return await window.electronAPI.sendCommand(commandData);
  }, [isElectron]);

  const getSystemStatus = useCallback(async () => {
    if (!isElectron) {
      // Fallback pour le développement web
      return {
        service: { running: true, commands_processed: 0 },
        components: {},
        system: { platform: 'web' }
      };
    }

    return await window.electronAPI.getSystemStatus();
  }, [isElectron]);

  const showNotification = useCallback(async (notificationData: {
    title: string;
    body: string;
    type?: 'info' | 'success' | 'warning' | 'error';
  }) => {
    if (!isElectron) {
      console.log('Notification (fallback):', notificationData);
      return;
    }

    return await window.electronAPI.showNotification(notificationData);
  }, [isElectron]);

  const toggleOverlay = useCallback(async () => {
    if (!isElectron) return;
    return await window.electronAPI.toggleOverlay();
  }, [isElectron]);

  const showOverlay = useCallback(async () => {
    if (!isElectron) return;
    return await window.electronAPI.showOverlay();
  }, [isElectron]);

  const hideOverlay = useCallback(async () => {
    if (!isElectron) return;
    return await window.electronAPI.hideOverlay();
  }, [isElectron]);

  const getOverlayConfig = useCallback(async () => {
    if (!isElectron) {
      return {
        height: 60,
        opacity: 0.9,
        hotkey: 'CommandOrControl+`',
        pushToTalkKey: 'Alt+Space'
      };
    }

    return await window.electronAPI.getOverlayConfig();
  }, [isElectron]);

  const onVisibilityChanged = useCallback((callback: (visible: boolean) => void) => {
    if (!isElectron) {
      // En mode web, toujours visible
      callback(true);
      return () => {};
    }

    window.electronAPI.onOverlayVisibilityChanged(callback);
    
    return () => {
      window.electronAPI.removeAllListeners('overlay-visibility-changed');
    };
  }, [isElectron]);

  const onPushToTalkStart = useCallback((callback: () => void) => {
    if (!isElectron) {
      return () => {};
    }

    window.electronAPI.onPushToTalkStart(callback);
    
    return () => {
      window.electronAPI.removeAllListeners('push-to-talk-start');
    };
  }, [isElectron]);

  const onPushToTalkEnd = useCallback((callback: () => void) => {
    if (!isElectron) {
      return () => {};
    }

    window.electronAPI.onPushToTalkEnd(callback);
    
    return () => {
      window.electronAPI.removeAllListeners('push-to-talk-end');
    };
  }, [isElectron]);

  const getUtils = useCallback(() => {
    if (!isElectron) {
      return {
        platform: 'web',
        version: '0.0.0',
        isDev: process.env.NODE_ENV === 'development'
      };
    }

    return window.utils;
  }, [isElectron]);

  return {
    isElectron,
    sendCommand,
    getSystemStatus,
    showNotification,
    toggleOverlay,
    showOverlay,
    hideOverlay,
    getOverlayConfig,
    onVisibilityChanged,
    onPushToTalkStart,
    onPushToTalkEnd,
    getUtils
  };
};