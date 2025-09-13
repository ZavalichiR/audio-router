"""
Configuration management for the Discord Audio Router system.

This package provides comprehensive configuration management including:
- Configuration classes and data structures
- Configuration validation and loading
- Environment variable handling
- Default value management
"""

from .settings import SimpleConfig, SimpleConfigManager, config_manager

__all__ = [
    "SimpleConfig",
    "SimpleConfigManager",
    "config_manager",
]
