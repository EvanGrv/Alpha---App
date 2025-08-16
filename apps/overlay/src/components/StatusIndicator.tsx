import React from 'react';
import { Box, Tooltip } from '@mui/material';
import { motion } from 'framer-motion';

interface StatusIndicatorProps {
  status: 'connected' | 'disconnected' | 'processing' | 'error';
  tooltip?: string;
  size?: 'small' | 'medium' | 'large';
}

const STATUS_COLORS = {
  connected: '#4caf50',
  disconnected: '#f44336',
  processing: '#ff9800',
  error: '#e91e63'
};

const STATUS_LABELS = {
  connected: 'Connecté',
  disconnected: 'Déconnecté',
  processing: 'En traitement',
  error: 'Erreur'
};

export const StatusIndicator: React.FC<StatusIndicatorProps> = ({
  status,
  tooltip,
  size = 'small'
}) => {
  const sizeMap = {
    small: 8,
    medium: 12,
    large: 16
  };

  const indicatorSize = sizeMap[size];
  const color = STATUS_COLORS[status];
  const label = STATUS_LABELS[status];

  const pulseAnimation = {
    scale: [1, 1.2, 1],
    opacity: [1, 0.7, 1],
  };

  return (
    <Tooltip title={tooltip || label} arrow placement="top">
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
        }}
      >
        <motion.div
          animate={status === 'processing' ? pulseAnimation : {}}
          transition={{
            duration: 1.5,
            repeat: status === 'processing' ? Infinity : 0,
            ease: 'easeInOut'
          }}
        >
          <Box
            sx={{
              width: indicatorSize,
              height: indicatorSize,
              borderRadius: '50%',
              backgroundColor: color,
              boxShadow: `0 0 ${indicatorSize * 1.5}px ${color}40`,
              transition: 'all 0.3s ease',
            }}
          />
        </motion.div>
        
        {size !== 'small' && (
          <Box
            sx={{
              fontSize: size === 'medium' ? 12 : 14,
              color: 'rgba(255, 255, 255, 0.7)',
              fontWeight: 500,
            }}
          >
            {label}
          </Box>
        )}
      </Box>
    </Tooltip>
  );
};