"""
Infrastructure components for the Discord Audio Router system.

This package contains infrastructure concerns including:
- Logging configuration and utilities with production controls
- Health monitoring and metrics
- Custom exception definitions
- System utilities
"""

from .logging import setup_logging, get_logger, LoggingContext
from .logging_manager import (
    LoggingManager,
    LogLevel,
    Environment,
    is_production,
    get_environment,
)
from .exceptions import (
    AudioRouterError,
    ConfigurationError,
    BotProcessError,
    AudioProcessingError,
    NetworkError,
    ValidationError,
    TokenError,
    PermissionError,
    ChannelError,
    WebSocketError,
    AudioBufferError,
)

__all__ = [
    # Logging
    "setup_logging",
    "get_logger",
    "LoggingContext",
    "LoggingManager",
    "LogLevel",
    "Environment",
    "is_production",
    "get_environment",
    # Exceptions
    "AudioRouterError",
    "ConfigurationError",
    "BotProcessError",
    "AudioProcessingError",
    "NetworkError",
    "ValidationError",
    "TokenError",
    "PermissionError",
    "ChannelError",
    "WebSocketError",
    "AudioBufferError",
]
