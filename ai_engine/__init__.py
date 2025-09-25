"""
AI Engine Module

This module contains all AI-related functionality including:
- AI engine with provider management
- Configuration and settings
- Model caching and discovery
- Usage statistics and performance tracking
"""

from .ai_engine import AI_engine
from .config import AI_CONFIGS, ENGINE_SETTINGS, AUTODECIDE_CONFIG, verbose_print
from .model_cache import shared_model_cache
from .statistics_manager import StatisticsManager, get_stats_manager, save_statistics_now

__all__ = [
    'AI_engine',
    'AI_CONFIGS',
    'ENGINE_SETTINGS', 
    'AUTODECIDE_CONFIG',
    'verbose_print',
    'shared_model_cache',
    'StatisticsManager',
    'get_stats_manager',
    'save_statistics_now'
]