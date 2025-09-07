"""
Audio processing components for the Discord Audio Router system.

This package contains all audio-related functionality including:
- Audio capture and playback handlers
- Audio buffering and queuing
- Audio source implementations
- Opus codec integration
"""

from .handlers import OpusAudioSink, OpusAudioSource, setup_audio_receiver
from .buffers import AudioBuffer

__all__ = [
    "OpusAudioSink",
    "OpusAudioSource", 
    "AudioBuffer",
    "setup_audio_receiver",
]
