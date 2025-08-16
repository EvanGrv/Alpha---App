"""
Package NLU (Natural Language Understanding) pour Desktop Agent.

Fournit les capacités de compréhension du langage naturel basées sur des règles.
"""

from .intent_parser import IntentParser
from .slot_extractor import SlotExtractor
from .nlu_manager import NLUManager

__all__ = [
    "IntentParser",
    "SlotExtractor", 
    "NLUManager"
]