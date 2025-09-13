"""
Discord bot implementations for the Audio Router system.

This package contains all Discord bot implementations including:
- Main control bot (AudioBroadcast)
- Audio forwarder bot (AudioForwarder)
- Audio receiver bot (AudioReceiver)
- Base bot classes and utilities
"""

from .forwarder_bot import AudioForwarderBot
from .receiver_bot import AudioReceiverBot

__all__ = [
    "AudioForwarderBot",
    "AudioReceiverBot",
]
