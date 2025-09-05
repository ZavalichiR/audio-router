"""
Infrastructure components for the Discord Audio Router system.

This package contains infrastructure concerns including:
- Logging configuration and utilities
- Health monitoring and metrics
- Custom exception definitions
- System utilities
"""

from .logging import setup_logging, get_logger
from .exceptions import (
    AudioRouterError,
    ConfigurationError,
    BotProcessError,
    AudioProcessingError,
    NetworkError,
)

__all__ = [
    "setup_logging",
    "get_logger",
    "AudioRouterError",
    "ConfigurationError", 
    "BotProcessError",
    "AudioProcessingError",
    "NetworkError",
]
