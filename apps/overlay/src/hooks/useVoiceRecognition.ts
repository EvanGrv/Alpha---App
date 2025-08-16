import { useState, useEffect, useCallback, useRef } from 'react';

// Interface pour la reconnaissance vocale Web API
interface SpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  maxAlternatives: number;
  serviceURI: string;
  grammars: SpeechGrammarList;
  start(): void;
  stop(): void;
  abort(): void;
}

interface SpeechRecognitionEvent extends Event {
  results: SpeechRecognitionResultList;
  resultIndex: number;
}

interface SpeechRecognitionResultList {
  length: number;
  item(index: number): SpeechRecognitionResult;
  [index: number]: SpeechRecognitionResult;
}

interface SpeechRecognitionResult {
  length: number;
  item(index: number): SpeechRecognitionAlternative;
  [index: number]: SpeechRecognitionAlternative;
  isFinal: boolean;
}

interface SpeechRecognitionAlternative {
  transcript: string;
  confidence: number;
}

declare global {
  interface Window {
    SpeechRecognition: new () => SpeechRecognition;
    webkitSpeechRecognition: new () => SpeechRecognition;
  }
}

export const useVoiceRecognition = () => {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [interimTranscript, setInterimTranscript] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSupported, setIsSupported] = useState(false);
  
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Vérifier le support de la reconnaissance vocale
  useEffect(() => {
    const SpeechRecognition = 
      window.SpeechRecognition || window.webkitSpeechRecognition;
    
    if (SpeechRecognition) {
      setIsSupported(true);
      
      // Initialiser la reconnaissance vocale
      const recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = 'fr-FR'; // Français par défaut
      recognition.maxAlternatives = 1;
      
      // Gestion des résultats
      recognition.onresult = (event: SpeechRecognitionEvent) => {
        let finalTranscript = '';
        let interimTranscript = '';
        
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const result = event.results[i];
          const transcript = result[0].transcript;
          
          if (result.isFinal) {
            finalTranscript += transcript;
          } else {
            interimTranscript += transcript;
          }
        }
        
        if (finalTranscript) {
          setTranscript(prev => prev + finalTranscript);
          setInterimTranscript('');
          
          // Arrêter automatiquement après un résultat final
          setTimeout(() => {
            if (recognitionRef.current) {
              recognitionRef.current.stop();
            }
          }, 500);
        } else {
          setInterimTranscript(interimTranscript);
        }
      };
      
      // Gestion des erreurs
      recognition.onerror = (event: any) => {
        console.error('Speech recognition error:', event.error);
        setError(`Erreur reconnaissance vocale: ${event.error}`);
        setIsListening(false);
        
        // Erreurs spécifiques
        switch (event.error) {
          case 'no-speech':
            setError('Aucune parole détectée');
            break;
          case 'audio-capture':
            setError('Microphone non accessible');
            break;
          case 'not-allowed':
            setError('Permission microphone refusée');
            break;
          case 'network':
            setError('Erreur réseau pour la reconnaissance vocale');
            break;
          default:
            setError('Erreur de reconnaissance vocale');
        }
      };
      
      // Début de la reconnaissance
      recognition.onstart = () => {
        setIsListening(true);
        setError(null);
        console.log('Speech recognition started');
      };
      
      // Fin de la reconnaissance
      recognition.onend = () => {
        setIsListening(false);
        setInterimTranscript('');
        console.log('Speech recognition ended');
      };
      
      recognitionRef.current = recognition;
    } else {
      setIsSupported(false);
      console.warn('Speech recognition not supported in this browser');
    }
    
    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  const startListening = useCallback(() => {
    if (!isSupported || !recognitionRef.current || isListening) {
      return;
    }
    
    setError(null);
    setTranscript('');
    setInterimTranscript('');
    
    try {
      recognitionRef.current.start();
      
      // Timeout de sécurité (arrêt automatique après 30 secondes)
      timeoutRef.current = setTimeout(() => {
        if (recognitionRef.current && isListening) {
          recognitionRef.current.stop();
        }
      }, 30000);
      
    } catch (error) {
      console.error('Error starting speech recognition:', error);
      setError('Impossible de démarrer la reconnaissance vocale');
    }
  }, [isSupported, isListening]);

  const stopListening = useCallback(() => {
    if (!recognitionRef.current || !isListening) {
      return;
    }
    
    try {
      recognitionRef.current.stop();
      
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
    } catch (error) {
      console.error('Error stopping speech recognition:', error);
    }
  }, [isListening]);

  const resetTranscript = useCallback(() => {
    setTranscript('');
    setInterimTranscript('');
    setError(null);
  }, []);

  const toggleListening = useCallback(() => {
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  }, [isListening, startListening, stopListening]);

  // Nettoyage automatique du transcript après un délai
  useEffect(() => {
    if (transcript && !isListening) {
      const cleanupTimeout = setTimeout(() => {
        // Le transcript sera nettoyé par le composant parent après utilisation
      }, 5000);
      
      return () => clearTimeout(cleanupTimeout);
    }
  }, [transcript, isListening]);

  return {
    isListening,
    transcript: transcript + interimTranscript,
    finalTranscript: transcript,
    interimTranscript,
    error,
    isSupported,
    startListening,
    stopListening,
    toggleListening,
    resetTranscript
  };
};