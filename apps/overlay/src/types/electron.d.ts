export interface IElectronAPI {
  // Agent communication
  sendCommand: (command: string, source: 'text' | 'voice') => Promise<any>;
  
  // Window control
  hideWindow: () => void;
  showWindow: () => void;
  
  // System
  onGlobalHotkey: (callback: () => void) => void;
  onVoiceHotkey: (callback: () => void) => void;
  
  // Events
  onAgentStatus: (callback: (status: any) => void) => void;
  onAgentResponse: (callback: (response: any) => void) => void;
}

declare global {
  interface Window {
    electronAPI: IElectronAPI;
  }
}