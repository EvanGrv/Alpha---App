import React, { useState, useEffect, useCallback } from 'react';
import { Box, Paper, TextField, IconButton, Tooltip, Chip } from '@mui/material';
import { 
  Mic, 
  MicOff, 
  Send, 
  Settings, 
  Close,
  KeyboardVoice,
  Search
} from '@mui/icons-material';
import { motion, AnimatePresence } from 'framer-motion';
import { useElectron } from './hooks/useElectron';
import { useVoiceRecognition } from './hooks/useVoiceRecognition';
import { CommandInput } from './components/CommandInput';
import { StatusIndicator } from './components/StatusIndicator';
import { NotificationToast } from './components/NotificationToast';
import './App.css';

interface CommandResult {
  success: boolean;
  message: string;
  stage: string;
  plan_id?: string;
  warnings?: string[];
  suggestions?: any;
}

const App: React.FC = () => {
  const [input, setInput] = useState('');
  const [isVisible, setIsVisible] = useState(true);
  const [isProcessing, setIsProcessing] = useState(false);
  const [lastResult, setLastResult] = useState<CommandResult | null>(null);
  const [showNotification, setShowNotification] = useState(false);
  const [systemStatus, setSystemStatus] = useState<any>(null);
  
  const { 
    sendCommand, 
    getSystemStatus, 
    showNotification: showSystemNotification,
    onVisibilityChanged,
    onPushToTalkStart,
    onPushToTalkEnd
  } = useElectron();
  
  const {
    isListening,
    isSupported,
    transcript,
    startListening,
    stopListening,
    resetTranscript
  } = useVoiceRecognition();

  // Gérer la visibilité de l'overlay
  useEffect(() => {
    const unsubscribe = onVisibilityChanged((visible: boolean) => {
      setIsVisible(visible);
      if (visible) {
        // Reset de l'état quand l'overlay devient visible
        setInput('');
        setIsProcessing(false);
        resetTranscript();
      }
    });

    return unsubscribe;
  }, [onVisibilityChanged, resetTranscript]);

  // Gérer le push-to-talk
  useEffect(() => {
    const unsubscribeStart = onPushToTalkStart(() => {
      if (isSupported && !isListening) {
        startListening();
      }
    });

    const unsubscribeEnd = onPushToTalkEnd(() => {
      if (isListening) {
        stopListening();
      }
    });

    return () => {
      unsubscribeStart();
      unsubscribeEnd();
    };
  }, [isSupported, isListening, startListening, stopListening, onPushToTalkStart, onPushToTalkEnd]);

  // Mettre à jour l'input avec la transcription vocale
  useEffect(() => {
    if (transcript) {
      setInput(transcript);
    }
  }, [transcript]);

  // Récupérer le statut système périodiquement
  useEffect(() => {
    const updateSystemStatus = async () => {
      try {
        const status = await getSystemStatus();
        setSystemStatus(status);
      } catch (error) {
        console.error('Error getting system status:', error);
      }
    };

    updateSystemStatus();
    const interval = setInterval(updateSystemStatus, 10000); // Toutes les 10 secondes

    return () => clearInterval(interval);
  }, [getSystemStatus]);

  const handleSubmit = useCallback(async (command?: string) => {
    const commandText = command || input.trim();
    
    if (!commandText) return;

    setIsProcessing(true);
    setLastResult(null);

    try {
      const result = await sendCommand({
        source: command ? 'voice' : 'text',
        text: commandText,
        require_confirmation: false
      });

      setLastResult(result);

      // Afficher une notification selon le résultat
      if (result.success) {
        if (result.stage === 'confirmation_required') {
          showSystemNotification({
            title: 'Confirmation requise',
            body: `Plan généré: ${result.message}`,
            type: 'warning'
          });
        } else {
          showSystemNotification({
            title: 'Commande exécutée',
            body: result.message,
            type: 'success'
          });
        }
      } else {
        showSystemNotification({
          title: 'Erreur',
          body: result.message,
          type: 'error'
        });
      }

      setShowNotification(true);
      setTimeout(() => setShowNotification(false), 5000);

    } catch (error) {
      console.error('Error sending command:', error);
      setLastResult({
        success: false,
        message: 'Erreur de connexion',
        stage: 'error'
      });
      setShowNotification(true);
    } finally {
      setIsProcessing(false);
      setInput('');
      resetTranscript();
    }
  }, [input, sendCommand, showSystemNotification, resetTranscript]);

  const handleKeyPress = useCallback((event: React.KeyboardEvent) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSubmit();
    } else if (event.key === 'Escape') {
      setInput('');
      resetTranscript();
    }
  }, [handleSubmit, resetTranscript]);

  const toggleVoiceRecognition = useCallback(() => {
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  }, [isListening, startListening, stopListening]);

  if (!isVisible) {
    return null;
  }

  return (
    <Box className="app-container">
      <motion.div
        initial={{ y: 100, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        exit={{ y: 100, opacity: 0 }}
        transition={{ type: "spring", stiffness: 300, damping: 30 }}
      >
        <Paper 
          elevation={8}
          sx={{
            width: '100%',
            height: 60,
            display: 'flex',
            alignItems: 'center',
            px: 2,
            backgroundColor: 'background.paper',
            backdropFilter: 'blur(10px)',
            borderRadius: '12px 12px 0 0',
          }}
        >
          {/* Indicateur de statut */}
          <StatusIndicator 
            status={systemStatus?.service?.running ? 'connected' : 'disconnected'}
            tooltip={systemStatus ? 
              `Agent ${systemStatus.service.running ? 'actif' : 'inactif'} - ${systemStatus.service.commands_processed} commandes` :
              'Statut inconnu'
            }
          />

          {/* Zone de saisie */}
          <Box sx={{ flexGrow: 1, mx: 2 }}>
            <CommandInput
              value={input}
              onChange={setInput}
              onSubmit={handleSubmit}
              onKeyPress={handleKeyPress}
              placeholder={
                isListening 
                  ? "🎤 En écoute..." 
                  : "Tapez votre commande ou utilisez Ctrl+` pour basculer"
              }
              disabled={isProcessing}
              isListening={isListening}
            />
          </Box>

          {/* Contrôles */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {/* Bouton microphone */}
            {isSupported && (
              <Tooltip title={isListening ? "Arrêter l'écoute" : "Commencer l'écoute"}>
                <IconButton
                  onClick={toggleVoiceRecognition}
                  color={isListening ? "secondary" : "default"}
                  size="small"
                  disabled={isProcessing}
                >
                  {isListening ? <KeyboardVoice /> : <Mic />}
                </IconButton>
              </Tooltip>
            )}

            {/* Bouton d'envoi */}
            <Tooltip title="Envoyer la commande">
              <IconButton
                onClick={() => handleSubmit()}
                color="primary"
                size="small"
                disabled={!input.trim() || isProcessing}
              >
                <Send />
              </IconButton>
            </Tooltip>

            {/* Indicateur de traitement */}
            {isProcessing && (
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
              >
                <Search color="primary" />
              </motion.div>
            )}
          </Box>
        </Paper>
      </motion.div>

      {/* Notification toast */}
      <AnimatePresence>
        {showNotification && lastResult && (
          <NotificationToast
            result={lastResult}
            onClose={() => setShowNotification(false)}
          />
        )}
      </AnimatePresence>

      {/* Indicateurs d'état en bas */}
      <AnimatePresence>
        {(isListening || transcript) && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 10 }}
            style={{
              position: 'absolute',
              bottom: -40,
              left: 16,
              right: 16,
              display: 'flex',
              justifyContent: 'center'
            }}
          >
            <Chip
              icon={<KeyboardVoice />}
              label={transcript || "En écoute..."}
              color="secondary"
              variant="filled"
              sx={{
                backgroundColor: 'rgba(245, 0, 87, 0.2)',
                backdropFilter: 'blur(10px)',
                color: 'white',
                maxWidth: 300,
                '& .MuiChip-label': {
                  overflow: 'hidden',
                  textOverflow: 'ellipsis'
                }
              }}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </Box>
  );
};

export default App;