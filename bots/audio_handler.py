import asyncio
import logging
import queue
import threading
from typing import Any, Callable, Optional

import discord
from discord.ext import voice_recv

logger = logging.getLogger(__name__)


class AudioBuffer:
    """Thread-safe buffer for Opus packets using both async and sync interfaces."""

    def __init__(self, max_size: int = 100):
        self._async_buffer: list[bytes] = []
        self._sync_queue: queue.Queue[bytes] = queue.Queue(maxsize=max_size)
        self.max_size = max_size
        self._async_lock = asyncio.Lock()
        self._sync_lock = threading.Lock()

    async def put(self, data: bytes):
        """Add an Opus packet to the buffer (async interface)."""
        async with self._async_lock:
            if len(self._async_buffer) >= self.max_size:
                self._async_buffer.pop(0)
            self._async_buffer.append(data)

        # Also add to sync queue for synchronous access
        try:
            self._sync_queue.put_nowait(data)
            logger.debug(f"Audio buffer: Added {len(data)} bytes to sync queue")
        except queue.Full:
            # Remove oldest item and add new one
            try:
                self._sync_queue.get_nowait()
                self._sync_queue.put_nowait(data)
                logger.debug(f"Audio buffer: Replaced packet in full queue with {len(data)} bytes")
            except queue.Empty:
                pass

    async def get(self) -> Optional[bytes]:
        """Retrieve the oldest Opus packet, or None if empty (async interface)."""
        async with self._async_lock:
            return self._async_buffer.pop(0) if self._async_buffer else None

    def get_sync(self, timeout: float = 0.01) -> Optional[bytes]:
        """Retrieve the oldest Opus packet synchronously (for discord.py)."""
        try:
            return self._sync_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    async def clear(self):
        """Clear all buffered packets."""
        async with self._async_lock:
            self._async_buffer.clear()

        with self._sync_lock:
            while not self._sync_queue.empty():
                try:
                    self._sync_queue.get_nowait()
                except queue.Empty:
                    break


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
        logger.debug("OpusAudioSink started")

    def stop(self):
        """Stop processing audio packets."""
        self._is_active = False
        logger.debug("OpusAudioSink stopped")

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
            logger.debug("Ignoring invalid audio packet (ssrc=0 or no user)")
            return
        
        # Filter out silence/keep-alive packets (very small packets with no sequence)
        if voice_data.packet.sequence == 0 and voice_data.packet.timestamp == 0:
            logger.debug("Ignoring silence/keep-alive packet")
            return

        try:
            opus_audio_data = voice_data.packet.decrypted_data
            if opus_audio_data:
                logger.debug(
                    f"🎤 Captured audio from {user.display_name}: {len(opus_audio_data)} bytes"
                )
                # Schedule callback execution on the event loop
                self.event_loop.create_task(
                    self.audio_callback_func(opus_audio_data)
                )
            else:
                logger.debug(
                    f"Received voice data from {user.display_name} but no audio content"
                )
        except Exception as e:
            logger.error(
                f"Error processing audio data from {user.display_name}: {e}"
            )

    def cleanup(self):
        """Clean up resources and stop processing."""
        self.stop()
        logger.debug("OpusAudioSink cleaned up")


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

        logger.info(f"Created audio sink: {audio_sink}")
        logger.info(f"Audio sink wants Opus: {audio_sink.wants_opus()}")

        voice_client.listen(audio_sink)
        logger.info("Audio sink registered with voice client")

        audio_sink.start()
        logger.info("Audio sink started successfully")

        logger.info("Successfully started receiving Opus audio packets")
        return audio_sink
    except Exception as e:
        logger.error(f"Failed to set up audio receiving: {e}")
        if audio_sink:
            try:
                audio_sink.cleanup()
            except Exception as cleanup_error:
                logger.error(
                    f"Error during audio sink cleanup: {cleanup_error}"
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
        if self._read_count <= 5:  # Log first 5 calls to see if it's being called at all
            logger.info(f"Audio source read() called {self._read_count} times")
        elif self._read_count % 1000 == 0:  # Then log every 1000th call to avoid spam
            logger.info(f"Audio source read() called {self._read_count} times")
        
        if not self._is_playing:
            logger.debug(f"Audio source not playing, returning empty")
            return b""

        # Use thread-safe synchronous access to avoid deadlocks
        audio_packet = self.audio_buffer.get_sync(timeout=0.01)  # 10ms timeout
        if audio_packet:
            if self._read_count <= 5:  # Only log first 5 audio packets
                logger.info(f"🎵 Playing audio packet: {len(audio_packet)} bytes")
            else:
                logger.debug(f"🎵 Playing audio packet: {len(audio_packet)} bytes")
        else:
            if self._read_count <= 5:  # Only log silence for first 5 calls
                logger.info(f"Audio source returning silence frame (no data available)")
        return (
            audio_packet if audio_packet else b"\xf8\xff\xfe"
        )  # Opus silence frame


class SilentSource(discord.AudioSource):
    """
    Generates Opus silence frames to keep Discord voice connections alive.

    This source continuously provides silence frames to prevent Discord from
    disconnecting the bot due to inactivity.
    """

    def __init__(self):
        """Initialize the silent source."""
        self.frame_count = 0

    def is_opus(self) -> bool:
        """Return True to indicate we provide Opus-encoded audio."""
        return True

    def read(self) -> bytes:
        """
        Generate the next silence frame.

        Returns:
            bytes: Opus silence frame
        """
        self.frame_count += 1
        return b"\xf8\xff\xfe"  # Standard Opus silence frame
