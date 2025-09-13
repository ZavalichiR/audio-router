"""
Custom exceptions for the Discord Audio Router system.

This module defines all custom exceptions used throughout the system,
providing clear error categorization and handling.
"""


class AudioRouterError(Exception):
    """Base exception for all Audio Router related errors."""

    pass


class ConfigurationError(AudioRouterError):
    """Raised when there are configuration-related errors."""

    pass


class BotProcessError(AudioRouterError):
    """Raised when there are bot process-related errors."""

    pass


class AudioProcessingError(AudioRouterError):
    """Raised when there are audio processing-related errors."""

    pass


class NetworkError(AudioRouterError):
    """Raised when there are network communication errors."""

    pass


class ValidationError(ConfigurationError):
    """Raised when configuration validation fails."""

    pass


class TokenError(ConfigurationError):
    """Raised when bot token configuration is invalid."""

    pass


class PermissionError(AudioRouterError):
    """Raised when there are permission-related errors."""

    pass


class ChannelError(AudioRouterError):
    """Raised when there are voice channel-related errors."""

    pass


class WebSocketError(NetworkError):
    """Raised when there are WebSocket communication errors."""

    pass


class AudioBufferError(AudioProcessingError):
    """Raised when there are audio buffer-related errors."""

    pass
