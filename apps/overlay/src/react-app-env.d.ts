/// <reference types="react-scripts" />

// Déclarations pour Electron
declare global {
  interface Window {
    electronAPI: {
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
    };
    utils: {
      platform: string;
      version: string;
      isDev: boolean;
    };
  }
}