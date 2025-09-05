"""
Configuration package for the Discord Audio Router Bot.

This package provides configuration management for the audio routing system.
"""

from .simple_config import SimpleConfig, SimpleConfigManager, config_manager

__all__ = ["SimpleConfig", "SimpleConfigManager", "config_manager"]
