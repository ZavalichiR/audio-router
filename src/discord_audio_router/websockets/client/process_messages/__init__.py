"""
Client-side message processing modules.

This package contains handlers for different types of WebSocket messages
received by the client, mirroring the server's process_messages structure.
"""

from .control_message import ControlMessageHandler
from .audio_message import AudioMessageHandler

__all__ = ["ControlMessageHandler", "AudioMessageHandler"]
