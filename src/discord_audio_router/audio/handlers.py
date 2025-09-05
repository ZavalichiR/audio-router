"""
Audio handling components for the Discord Audio Router system.

This module provides audio capture and playback handlers for Discord voice channels,
including Opus audio sink and source implementations.
"""

import asyncio
import logging
from typing import Any, Callable, Optional

import discord
from discord.ext import voice_recv

from .buffers import AudioBuffer

logger = logging.getLogger(__name__)


class OpusAudioSink(voice_recv.AudioSink):
    """
    Captures Opus-encoded audio from Discord voice channels and forwards it via callback.

    This sink receives raw Opus audio packets from Discord's voice system and passes
    them to a callback function for further processing (e.g., WebSocket forwarding).
    """

    def __init__(
        self,
        audio_callback_func: Callable[[bytes], Any],
        event_loop: Optional[asyncio.AbstractEventLoop] = None,
    ):
        """
        Initialize the audio sink.

        Args:
            audio_callback_func: Async function to call with audio data (bytes)
            event_loop: Asyncio event loop (defaults to current loop)
        """
        self.audio_callback_func = audio_callback_func
        self.event_loop = event_loop or asyncio.get_running_loop()
        self._is_active = False

    def wants_opus(self) -> bool:
        """Return True to indicate we want Opus-encoded audio packets."""
        return True

    def start(self):
        """Start processing audio packets."""
        self._is_active = True
        logger.info("Audio sink started - ready to capture audio")

    def stop(self):
        """Stop processing audio packets."""
        self._is_active = False
        logger.info("Audio sink stopped")

    def write(
        self, user: discord.Member, voice_data: voice_recv.VoiceData
    ) -> None:
        """
        Process incoming audio data from Discord.

        Args:
            user: Discord member who is speaking
            voice_data: Voice data containing audio packet
        """
        if not self._is_active or voice_data.packet is None:
            return

        # Filter out invalid packets (ssrc=0 or no user)
        if user is None or voice_data.packet.ssrc == 0:
            return
        
        # Filter out silence/keep-alive packets (very small packets with no sequence)
        if voice_data.packet.sequence == 0 and voice_data.packet.timestamp == 0:
            return

        try:
            opus_audio_data = voice_data.packet.decrypted_data
            if opus_audio_data:
                # Schedule callback execution on the event loop
                self.event_loop.create_task(
                    self.audio_callback_func(opus_audio_data)
                )
        except Exception as e:
            logger.error(
                f"Failed to process audio from {user.display_name}: {e}",
                exc_info=True
            )

    def cleanup(self):
        """Clean up resources and stop processing."""
        self.stop()
        logger.info("Audio sink cleaned up")


async def setup_audio_receiver(
    voice_client: voice_recv.VoiceRecvClient,
    audio_callback_func: Callable[[bytes], Any],
) -> OpusAudioSink:
    """
    Set up Opus audio packet receiving from a Discord voice client.

    Args:
        voice_client: Connected VoiceRecvClient instance
        audio_callback_func: Async function to call with received audio data (bytes)

    Returns:
        OpusAudioSink: Configured audio sink for receiving packets

    Raises:
        ValueError: If voice_client is not a VoiceRecvClient
        RuntimeError: If voice client is not connected or setup fails
    """
    if not isinstance(voice_client, voice_recv.VoiceRecvClient):
        raise ValueError(
            "Voice client must be VoiceRecvClient for audio receive"
        )
    if not voice_client.is_connected():
        logger.error("VoiceRecvClient is not connected")
        raise RuntimeError("Voice client not connected")

    audio_sink: Optional[OpusAudioSink] = None
    try:
        event_loop = asyncio.get_running_loop()
        audio_sink = OpusAudioSink(
            audio_callback_func=audio_callback_func, event_loop=event_loop
        )

        voice_client.listen(audio_sink)
        audio_sink.start()

        logger.info("Audio sink setup complete - ready to receive Opus packets")
        return audio_sink
    except Exception as e:
        logger.error(f"Failed to set up audio receiving: {e}", exc_info=True)
        if audio_sink:
            try:
                audio_sink.cleanup()
            except Exception as cleanup_error:
                logger.error(
                    f"Error during audio sink cleanup: {cleanup_error}",
                    exc_info=True
                )
        raise


class OpusAudioSource(discord.AudioSource):
    """
    Audio source that plays Opus packets to Discord voice channels.

    This source reads Opus audio packets from an AudioBuffer and provides them
    to Discord's voice system, making the bot appear as if it's speaking.
    """

    def __init__(self, audio_buffer: AudioBuffer):
        """
        Initialize the audio source.

        Args:
            audio_buffer: AudioBuffer containing Opus packets to play
        """
        self.audio_buffer = audio_buffer
        self._is_playing = False
        self._read_count = 0

    def is_opus(self) -> bool:
        """Return True to indicate we provide Opus-encoded audio."""
        return True

    def start(self):
        """Start playing audio packets."""
        self._is_playing = True
        logger.info("OpusAudioSource started - ready to play audio")

    def stop(self):
        """Stop playing audio packets."""
        self._is_playing = False
        logger.debug("OpusAudioSource stopped")

    def read(self) -> bytes:
        """
        Called by discord.py to retrieve the next Opus packet.

        Returns:
            bytes: Opus audio packet or silence frame if no data available
        """
        self._read_count += 1
        
        if not self._is_playing:
            return b""

        # Use thread-safe synchronous access to avoid deadlocks
        audio_packet = self.audio_buffer.get_sync(timeout=0.01)  # 10ms timeout
        
        # Log startup and periodic status
        if self._read_count == 1:
            logger.info("Audio source started - ready to play audio")
        elif self._read_count % 10000 == 0:  # Log every 10k calls for health check
            logger.debug(f"Audio source health check: {self._read_count} calls processed")
            
        return (
            audio_packet if audio_packet else b"\xf8\xff\xfe"
        )  # Opus silence frame
