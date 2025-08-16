import React, { useState, useEffect } from 'react';
import { 
  TextField, 
  Box, 
  List, 
  ListItem, 
  ListItemText, 
  Paper,
  Fade
} from '@mui/material';
import { motion } from 'framer-motion';

interface CommandInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (command?: string) => void;
  onKeyPress: (event: React.KeyboardEvent) => void;
  placeholder?: string;
  disabled?: boolean;
  isListening?: boolean;
}

interface Suggestion {
  text: string;
  description: string;
  type: 'command' | 'example' | 'correction';
}

const COMMAND_SUGGESTIONS: Suggestion[] = [
  {
    text: "Ouvre Google Chrome",
    description: "Ouvre le navigateur Chrome",
    type: "example"
  },
  {
    text: "Crée un fichier texte et écris Bonjour",
    description: "Crée un nouveau fichier avec du contenu",
    type: "example"
  },
  {
    text: "Clique sur OK",
    description: "Clique sur un bouton ou texte visible",
    type: "example"
  },
  {
    text: "Recherche Python sur Google",
    description: "Effectue une recherche web",
    type: "example"
  },
  {
    text: "Lance Calculator",
    description: "Ouvre la calculatrice",
    type: "example"
  },
  {
    text: "Écris mon email",
    description: "Saisit du texte dans le champ actif",
    type: "example"
  },
  {
    text: "Sauvegarde le fichier",
    description: "Sauvegarde le document actuel",
    type: "example"
  }
];

export const CommandInput: React.FC<CommandInputProps> = ({
  value,
  onChange,
  onSubmit,
  onKeyPress,
  placeholder = "Tapez votre commande...",
  disabled = false,
  isListening = false
}) => {
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [filteredSuggestions, setFilteredSuggestions] = useState<Suggestion[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(-1);

  // Filtrer les suggestions basées sur l'input
  useEffect(() => {
    if (value.length > 1 && !isListening) {
      const filtered = COMMAND_SUGGESTIONS.filter(suggestion =>
        suggestion.text.toLowerCase().includes(value.toLowerCase()) ||
        suggestion.description.toLowerCase().includes(value.toLowerCase())
      ).slice(0, 5); // Limiter à 5 suggestions

      setFilteredSuggestions(filtered);
      setShowSuggestions(filtered.length > 0);
      setSelectedIndex(-1);
    } else {
      setShowSuggestions(false);
      setFilteredSuggestions([]);
      setSelectedIndex(-1);
    }
  }, [value, isListening]);

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (showSuggestions && filteredSuggestions.length > 0) {
      switch (event.key) {
        case 'ArrowDown':
          event.preventDefault();
          setSelectedIndex(prev => 
            prev < filteredSuggestions.length - 1 ? prev + 1 : 0
          );
          break;
        
        case 'ArrowUp':
          event.preventDefault();
          setSelectedIndex(prev => 
            prev > 0 ? prev - 1 : filteredSuggestions.length - 1
          );
          break;
        
        case 'Tab':
        case 'Enter':
          if (selectedIndex >= 0) {
            event.preventDefault();
            const selectedSuggestion = filteredSuggestions[selectedIndex];
            onChange(selectedSuggestion.text);
            setShowSuggestions(false);
            
            if (event.key === 'Enter') {
              onSubmit(selectedSuggestion.text);
            }
            return;
          }
          break;
        
        case 'Escape':
          event.preventDefault();
          setShowSuggestions(false);
          setSelectedIndex(-1);
          return;
      }
    }

    onKeyPress(event);
  };

  const handleSuggestionClick = (suggestion: Suggestion) => {
    onChange(suggestion.text);
    setShowSuggestions(false);
    onSubmit(suggestion.text);
  };

  const handleFocus = () => {
    if (value.length > 1) {
      setShowSuggestions(filteredSuggestions.length > 0);
    }
  };

  const handleBlur = () => {
    // Délai pour permettre le clic sur les suggestions
    setTimeout(() => {
      setShowSuggestions(false);
      setSelectedIndex(-1);
    }, 200);
  };

  return (
    <Box sx={{ position: 'relative', width: '100%' }}>
      <TextField
        fullWidth
        variant="outlined"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        onFocus={handleFocus}
        onBlur={handleBlur}
        placeholder={placeholder}
        disabled={disabled}
        className="command-input"
        sx={{
          '& .MuiOutlinedInput-root': {
            height: 40,
            borderRadius: '20px',
            backgroundColor: isListening 
              ? 'rgba(245, 0, 87, 0.1)' 
              : 'rgba(255, 255, 255, 0.05)',
            transition: 'all 0.3s ease',
            border: isListening 
              ? '1px solid rgba(245, 0, 87, 0.3)' 
              : '1px solid transparent',
            '&:hover': {
              backgroundColor: 'rgba(255, 255, 255, 0.08)',
            },
            '&.Mui-focused': {
              backgroundColor: 'rgba(255, 255, 255, 0.1)',
              boxShadow: isListening 
                ? '0 0 0 2px rgba(245, 0, 87, 0.3)'
                : '0 0 0 2px rgba(33, 150, 243, 0.3)',
            },
          },
          '& .MuiOutlinedInput-input': {
            padding: '10px 16px',
            fontSize: 14,
            color: 'white',
            '&::placeholder': {
              color: 'rgba(255, 255, 255, 0.5)',
              opacity: 1,
            },
          },
          '& .MuiOutlinedInput-notchedOutline': {
            border: 'none',
          },
        }}
      />

      {/* Suggestions dropdown */}
      <Fade in={showSuggestions}>
        <Paper
          sx={{
            position: 'absolute',
            top: '100%',
            left: 0,
            right: 0,
            backgroundColor: 'rgba(32, 32, 32, 0.95)',
            backdropFilter: 'blur(10px)',
            borderRadius: '0 0 12px 12px',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            borderTop: 'none',
            maxHeight: 200,
            overflow: 'hidden',
            zIndex: 1000,
            display: showSuggestions ? 'block' : 'none',
          }}
        >
          <List sx={{ py: 0 }}>
            {filteredSuggestions.map((suggestion, index) => (
              <motion.div
                key={`${suggestion.text}-${index}`}
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.05 }}
              >
                <ListItem
                  button
                  selected={index === selectedIndex}
                  onClick={() => handleSuggestionClick(suggestion)}
                  sx={{
                    py: 1.5,
                    px: 2,
                    borderBottom: index < filteredSuggestions.length - 1 
                      ? '1px solid rgba(255, 255, 255, 0.05)' 
                      : 'none',
                    '&:hover': {
                      backgroundColor: 'rgba(255, 255, 255, 0.1)',
                    },
                    '&.Mui-selected': {
                      backgroundColor: 'rgba(33, 150, 243, 0.2)',
                      '&:hover': {
                        backgroundColor: 'rgba(33, 150, 243, 0.3)',
                      },
                    },
                  }}
                >
                  <ListItemText
                    primary={suggestion.text}
                    secondary={suggestion.description}
                    primaryTypographyProps={{
                      fontSize: 14,
                      fontWeight: 500,
                      color: 'white',
                    }}
                    secondaryTypographyProps={{
                      fontSize: 12,
                      color: 'rgba(255, 255, 255, 0.7)',
                    }}
                  />
                </ListItem>
              </motion.div>
            ))}
          </List>
        </Paper>
      </Fade>
    </Box>
  );
};