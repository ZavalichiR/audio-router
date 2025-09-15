"""
Discord Audio Router - Professional audio routing system for Discord voice channels.

This package provides a comprehensive solution for routing audio from one voice channel
to multiple listener channels simultaneously, perfect for presentations, meetings, events, and more.

Key Features:
- One-to-Many Audio Routing
- Automatic Setup and Management
- Role-based Access Control
- Real-time Low-latency Audio Forwarding
- Multi-bot Architecture for Reliability
- WebSocket-based Communication
- Comprehensive Monitoring and Status

Architecture:
- Core: Business logic and orchestration
- Audio: Audio processing and handling
- Networking: WebSocket communication
- Bots: Discord bot implementations
- Commands: Command handlers and utilities
- Config: Configuration management
- Infrastructure: Logging, monitoring, exceptions
- Utils: Common utilities and helpers
"""

__version__ = "2.0.0"
__author__ = "Discord Audio Router Team"
__email__ = "team@discord-audio-router.com"

# Core components
from .core.audio_router import AudioRouter
from .core.section_manager import SectionManager, BroadcastSection
from .core.bot_manager import BotManager, BotProcess
from .core.access_control import AccessControl

# Audio components
from .audio.handlers import OpusAudioSink, OpusAudioSource, setup_audio_receiver
from .audio.buffers import AudioBuffer

# Networking components
from .websockets.server import AudioRelayServer

# Configuration
from .config.settings import SimpleConfig
from .config import SimpleConfigManager, config_manager

# Infrastructure
from .infrastructure.logging import setup_logging, get_logger
from .infrastructure.exceptions import (
    AudioRouterError,
    ConfigurationError,
    BotProcessError,
    AudioProcessingError,
    NetworkError,
)

# Bot implementations
from .bots.forwarder_bot import AudioForwarderBot
from .bots.receiver_bot import AudioReceiverBot

__all__ = [
    # Version info
    "__version__",
    "__author__",
    "__email__",
    # Core components
    "AudioRouter",
    "SectionManager",
    "BroadcastSection",
    "BotManager",
    "BotProcess",
    "AccessControl",
    # Audio components
    "OpusAudioSink",
    "OpusAudioSource",
    "AudioBuffer",
    "setup_audio_receiver",
    # Networking components
    "AudioRelayServer",
    "AudioRoute",
    # Configuration
    "SimpleConfig",
    "SimpleConfigManager",
    "config_manager",
    # Infrastructure
    "setup_logging",
    "get_logger",
    "AudioRouterError",
    "ConfigurationError",
    "BotProcessError",
    "AudioProcessingError",
    "NetworkError",
    # Bot implementations
    "AudioForwarderBot",
    "AudioReceiverBot",
]
