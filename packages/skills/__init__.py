"""
Package de compétences (skills) pour Desktop Agent.

Fournit les actions primitives et composites pour l'automatisation du bureau.
"""

from .base_skill import BaseSkill, SkillResult
from .app_skills import OpenAppSkill, FocusAppSkill, CloseAppSkill
from .interaction_skills import ClickTextSkill, TypeTextSkill, HotkeySkill
from .file_skills import SaveFileSkill, WriteTextFileSkill
from .skill_manager import SkillManager

__all__ = [
    "BaseSkill",
    "SkillResult", 
    "OpenAppSkill",
    "FocusAppSkill",
    "CloseAppSkill",
    "ClickTextSkill",
    "TypeTextSkill",
    "HotkeySkill",
    "SaveFileSkill",
    "WriteTextFileSkill",
    "SkillManager"
]