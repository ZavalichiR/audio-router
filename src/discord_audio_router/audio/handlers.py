"""
Audio handling components for the Discord Audio Router system.

This module provides high-performance audio capture and playback handlers with
significant latency and quality improvements.
"""

import asyncio
from typing import Callable, Optional

import discord
from discord.ext import voice_recv
from discord_audio_router.audio.buffers import AudioBuffer
from discord_audio_router.infrastructure import setup_logging

logger = setup_logging("audio.handlers")


class OpusAudioSink(voice_recv.AudioSink):
    """
    High-performance Opus audio sink with direct callback processing.

    This implementation eliminates task creation overhead and provides
    direct audio packet processing for minimal latency.
    """

    def __init__(
        self,
        audio_callback_func: Callable[[bytes], None],  # Changed to synchronous
        event_loop: Optional[asyncio.AbstractEventLoop] = None,
    ):
        """
        Initialize the audio sink.

        Args:
            audio_callback_func: Synchronous function to call with audio data (bytes)
            event_loop: Asyncio event loop (for compatibility, but not used for callbacks)
        """
        self.audio_callback_func = audio_callback_func
        self.event_loop = event_loop or asyncio.get_running_loop()
        self._is_active = False

        # Performance tracking
        self._packet_count = 0
        self._filtered_packets = 0
        self._error_count = 0

    def wants_opus(self) -> bool:
        """Return True to indicate we want Opus-encoded audio packets."""
        return True

    def start(self):
        """Start processing audio packets."""
        self._is_active = True
        logger.debug("Audio sink started - ready to capture audio")

    def stop(self):
        """Stop processing audio packets."""
        self._is_active = False
        logger.debug("Audio sink stopped")

    def write(self, user: discord.Member, voice_data: voice_recv.VoiceData) -> None:
        """
        Process incoming audio data from Discord with optimized filtering.

        Args:
            user: Discord member who is speaking
            voice_data: Voice data containing audio packet
        """
        if not self._is_active or voice_data.packet is None:
            return

        self._packet_count += 1

        # Basic packet filtering - only filter out completely invalid packets
        if user is None or voice_data.packet.ssrc == 0:
            self._filtered_packets += 1
            return

        # Filter out bot voices - only capture audio from human members
        if user.bot:
            self._filtered_packets += 1
            logger.debug(f"Filtered out audio from bot: {user.display_name}")
            return

        # Only filter out packets with no audio data at all
        if (
            not voice_data.packet.decrypted_data
            or len(voice_data.packet.decrypted_data) == 0
        ):
            self._filtered_packets += 1
            return

        try:
            opus_audio_data = voice_data.packet.decrypted_data
            if opus_audio_data:
                # Direct callback without task creation for minimal latency
                self.audio_callback_func(opus_audio_data)
        except Exception as e:
            self._error_count += 1
            logger.error(
                f"Failed to process audio from {user.display_name}: {e}", exc_info=True
            )

    def cleanup(self):
        """Clean up resources and stop processing."""
        self.stop()
        logger.debug(
            f"Audio sink cleaned up - processed {self._packet_count} packets, "
            f"filtered {self._filtered_packets}, errors {self._error_count}"
        )

    def get_stats(self) -> dict:
        """Get performance statistics."""
        return {
            "packet_count": self._packet_count,
            "filtered_packets": self._filtered_packets,
            "error_count": self._error_count,
            "is_active": self._is_active,
        }


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
        logger.debug("OpusAudioSource started - ready to play audio")

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
            logger.warning(
                f"🎵 Audio source read() called but not playing (read #{self._read_count})"
            )
            return b""

        # Use thread-safe synchronous access to avoid deadlocks
        audio_packet = self.audio_buffer.get_sync(timeout=0.001)

        result = audio_packet if audio_packet else self.audio_buffer.get_silence_frame()

        return result

    def get_stats(self) -> dict:
        """Get performance statistics."""
        buffer_stats = self.audio_buffer.get_stats()
        return {
            "read_count": self._read_count,
            "is_playing": self._is_playing,
            "buffer_stats": buffer_stats,
        }


async def setup_audio_receiver(
    voice_client: voice_recv.VoiceRecvClient,
    audio_callback_func: Callable[[bytes], None],
) -> OpusAudioSink:
    """
    Set up Opus audio packet receiving from a Discord voice client.

    Args:
        voice_client: Connected VoiceRecvClient instance
        audio_callback_func: Synchronous function to call with received audio data (bytes)

    Returns:
        OpusAudioSink: Configured audio sink for receiving packets

    Raises:
        ValueError: If voice_client is not a VoiceRecvClient
        RuntimeError: If voice client is not connected or setup fails
    """
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
                    f"Error during audio sink cleanup: {cleanup_error}", exc_info=True
                )
        raise
