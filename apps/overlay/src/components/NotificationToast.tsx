import React from 'react';
import { 
  Paper, 
  Box, 
  Typography, 
  IconButton, 
  Chip,
  Alert,
  AlertTitle,
  Collapse
} from '@mui/material';
import { 
  Close, 
  CheckCircle, 
  Error, 
  Warning, 
  Info,
  PlayArrow,
  Schedule
} from '@mui/icons-material';
import { motion } from 'framer-motion';

interface CommandResult {
  success: boolean;
  message: string;
  stage: string;
  plan_id?: string;
  warnings?: string[];
  suggestions?: any;
  duration?: number;
}

interface NotificationToastProps {
  result: CommandResult;
  onClose: () => void;
  onExecutePlan?: (planId: string) => void;
}

export const NotificationToast: React.FC<NotificationToastProps> = ({
  result,
  onClose,
  onExecutePlan
}) => {
  const getSeverity = () => {
    if (!result.success) return 'error';
    if (result.stage === 'confirmation_required') return 'warning';
    if (result.warnings && result.warnings.length > 0) return 'info';
    return 'success';
  };

  const getIcon = () => {
    switch (getSeverity()) {
      case 'success':
        return <CheckCircle />;
      case 'error':
        return <Error />;
      case 'warning':
        return <Warning />;
      case 'info':
        return <Info />;
      default:
        return <Info />;
    }
  };

  const getTitle = () => {
    switch (result.stage) {
      case 'completed':
        return result.success ? 'Commande exécutée' : 'Échec de la commande';
      case 'confirmation_required':
        return 'Confirmation requise';
      case 'nlu':
        return 'Erreur de compréhension';
      case 'planning':
        return 'Erreur de planification';
      case 'error':
        return 'Erreur système';
      default:
        return 'Notification';
    }
  };

  const handleExecutePlan = () => {
    if (result.plan_id && onExecutePlan) {
      onExecutePlan(result.plan_id);
      onClose();
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: -50, scale: 0.9 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -50, scale: 0.9 }}
      transition={{ type: "spring", stiffness: 300, damping: 30 }}
      className="notification-toast"
    >
      <Alert
        severity={getSeverity()}
        icon={getIcon()}
        action={
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {result.stage === 'confirmation_required' && result.plan_id && (
              <IconButton
                size="small"
                onClick={handleExecutePlan}
                sx={{ color: 'inherit' }}
                title="Exécuter le plan"
              >
                <PlayArrow />
              </IconButton>
            )}
            <IconButton
              size="small"
              onClick={onClose}
              sx={{ color: 'inherit' }}
            >
              <Close />
            </IconButton>
          </Box>
        }
        sx={{
          minWidth: 300,
          maxWidth: 500,
          backgroundColor: 'rgba(32, 32, 32, 0.95)',
          backdropFilter: 'blur(10px)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          color: 'white',
          '& .MuiAlert-icon': {
            color: 'inherit',
          },
          '& .MuiAlert-message': {
            width: '100%',
          },
        }}
      >
        <AlertTitle sx={{ fontSize: 14, fontWeight: 600 }}>
          {getTitle()}
        </AlertTitle>
        
        <Typography variant="body2" sx={{ mb: 1 }}>
          {result.message}
        </Typography>

        {/* Durée d'exécution */}
        {result.duration && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 1 }}>
            <Schedule sx={{ fontSize: 16 }} />
            <Typography variant="caption">
              Exécuté en {result.duration.toFixed(2)}s
            </Typography>
          </Box>
        )}

        {/* Avertissements */}
        {result.warnings && result.warnings.length > 0 && (
          <Box sx={{ mt: 1 }}>
            <Typography variant="caption" sx={{ fontWeight: 600, mb: 0.5, display: 'block' }}>
              Avertissements:
            </Typography>
            {result.warnings.map((warning, index) => (
              <Chip
                key={index}
                label={warning}
                size="small"
                variant="outlined"
                sx={{ 
                  mr: 0.5, 
                  mb: 0.5,
                  fontSize: 11,
                  height: 20,
                  color: 'rgba(255, 255, 255, 0.8)',
                  borderColor: 'rgba(255, 255, 255, 0.3)',
                }}
              />
            ))}
          </Box>
        )}

        {/* Suggestions */}
        {result.suggestions && Object.keys(result.suggestions).length > 0 && (
          <Box sx={{ mt: 1 }}>
            <Typography variant="caption" sx={{ fontWeight: 600, mb: 0.5, display: 'block' }}>
              Suggestions:
            </Typography>
            {Object.entries(result.suggestions).map(([key, value]) => (
              <Box key={key} sx={{ mb: 0.5 }}>
                <Typography variant="caption" sx={{ fontSize: 10, opacity: 0.8 }}>
                  {key}: {Array.isArray(value) ? value.join(', ') : String(value)}
                </Typography>
              </Box>
            ))}
          </Box>
        )}

        {/* Bouton d'action pour confirmation */}
        {result.stage === 'confirmation_required' && result.plan_id && (
          <Box sx={{ mt: 2, pt: 1, borderTop: '1px solid rgba(255, 255, 255, 0.1)' }}>
            <Typography variant="caption" sx={{ display: 'block', mb: 1, opacity: 0.8 }}>
              Cliquez sur ▶ pour exécuter le plan ou fermez pour annuler
            </Typography>
          </Box>
        )}
      </Alert>
    </motion.div>
  );
};