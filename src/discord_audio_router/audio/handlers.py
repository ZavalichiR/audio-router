"""
Audio handling components for the Discord Audio Router system.

This module provides high-performance audio capture and playback handlers with
significant latency and quality improvements.
"""

import asyncio
import logging
import struct
import threading
import time
from collections import deque
from typing import Any, Callable, Optional, Tuple

import discord
from discord.ext import voice_recv

logger = logging.getLogger(__name__)


class AudioBuffer:
    """
    High-performance single-buffer system for Opus packets with adaptive jitter handling.
    
    This implementation eliminates the dual-buffer overhead and provides
    intelligent jitter buffering for improved audio quality.
    """

    def __init__(self, max_size: int = 50, initial_jitter_delay: float = 0.02):
        """
        Initialize the audio buffer.

        Args:
            max_size: Maximum number of packets to buffer (reduced for lower latency)
            initial_jitter_delay: Initial jitter buffer delay in seconds
        """
        self._buffer: deque[Tuple[float, bytes]] = deque(maxlen=max_size)
        self._lock = threading.RLock()  # Reentrant lock for better performance
        self.max_size = max_size
        
        # Performance tracking
        self._total_packets = 0
        self._dropped_packets = 0
        self._last_activity = time.time()
        self._read_count = 0
        self._write_count = 0
        
        # Jitter buffer management
        self.initial_jitter_delay = initial_jitter_delay
        self.current_jitter_delay = initial_jitter_delay
        self.max_jitter_delay = 0.1
        self._packet_times = deque(maxlen=20)  # Track recent packet timing
        
        # Pre-allocated silence frame for consistent performance
        self._silence_frame = b"\xf8\xff\xfe"

    def put(self, data: bytes) -> None:
        """Add an Opus packet to the buffer with jitter management."""
        self._write_count += 1
        self._last_activity = time.time()
        current_time = time.time()
        
        with self._lock:
            # Track packet timing for jitter analysis
            self._packet_times.append(current_time)
            
            # Add packet with timestamp
            if len(self._buffer) >= self.max_size:
                self._buffer.popleft()
                self._dropped_packets += 1
            self._buffer.append((current_time, data))
            
            # Adaptive jitter delay adjustment
            self._adjust_jitter_delay()

    def _adjust_jitter_delay(self) -> None:
        """Adjust buffer delay based on packet timing variance."""
        if len(self._packet_times) < 10:
            return
            
        # Calculate jitter (standard deviation of packet intervals)
        intervals = []
        for i in range(1, len(self._packet_times)):
            intervals.append(self._packet_times[i] - self._packet_times[i-1])
        
        if intervals:
            mean_interval = sum(intervals) / len(intervals)
            variance = sum((x - mean_interval) ** 2 for x in intervals) / len(intervals)
            jitter = variance ** 0.5
            
            # Adjust delay based on jitter
            if jitter > 0.01:  # High jitter
                self.current_jitter_delay = min(self.current_jitter_delay * 1.1, self.max_jitter_delay)
            elif jitter < 0.005:  # Low jitter
                self.current_jitter_delay = max(self.current_jitter_delay * 0.95, self.initial_jitter_delay)

    def get(self, timeout: float = 0.0005) -> Optional[bytes]:
        """
        Retrieve the next Opus packet with jitter buffering.
        
        Args:
            timeout: Maximum time to wait for a packet (reduced for lower latency)
            
        Returns:
            Opus audio packet or silence frame if no data available
        """
        self._read_count += 1
        current_time = time.time()
        
        with self._lock:
            # Look for packets that have been buffered long enough
            while self._buffer:
                packet_time, audio_data = self._buffer[0]
                if current_time - packet_time >= self.current_jitter_delay:
                    self._buffer.popleft()
                    return audio_data
                break  # Not enough time has passed for jitter buffering
            
            # Return silence frame if no suitable packet available
            return self._silence_frame

    def get_silence_frame(self) -> bytes:
        """Get pre-allocated silence frame for consistent performance."""
        return self._silence_frame

    def clear(self):
        """Clear all buffered packets."""
        with self._lock:
            self._buffer.clear()
            self._packet_times.clear()

    def size(self) -> int:
        """Get the current number of buffered packets."""
        return len(self._buffer)

    def is_empty(self) -> bool:
        """Check if the buffer is empty."""
        return len(self._buffer) == 0

    def is_full(self) -> bool:
        """Check if the buffer is full."""
        return len(self._buffer) >= self.max_size
    
    def get_stats(self) -> dict:
        """Get performance statistics."""
        return {
            "total_packets": self._total_packets,
            "dropped_packets": self._dropped_packets,
            "current_size": len(self._buffer),
            "max_size": self.max_size,
            "last_activity": self._last_activity,
            "drop_rate": self._dropped_packets / max(self._total_packets, 1) * 100,
            "jitter_delay": self.current_jitter_delay,
            "read_count": self._read_count,
            "write_count": self._write_count
        }


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
        logger.info("Audio sink started - ready to capture audio")

    def stop(self):
        """Stop processing audio packets."""
        self._is_active = False
        logger.info("Audio sink stopped")

    def write(
        self, user: discord.Member, voice_data: voice_recv.VoiceData
    ) -> None:
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
        
        # Only filter out packets with no audio data at all
        if not voice_data.packet.decrypted_data or len(voice_data.packet.decrypted_data) == 0:
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
                f"Failed to process audio from {user.display_name}: {e}",
                exc_info=True
            )

    def cleanup(self):
        """Clean up resources and stop processing."""
        self.stop()
        logger.info(f"Audio sink cleaned up - processed {self._packet_count} packets, "
                   f"filtered {self._filtered_packets}, errors {self._error_count}")

    def get_stats(self) -> dict:
        """Get performance statistics."""
        return {
            "packet_count": self._packet_count,
            "filtered_packets": self._filtered_packets,
            "error_count": self._error_count,
            "is_active": self._is_active
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
            logger.warning(f"🎵 Audio source read() called but not playing (read #{self._read_count})")
            return b""

        # Use thread-safe synchronous access to avoid deadlocks
        audio_packet = self.audio_buffer.get_sync(timeout=0.001)
        
        # Essential logging only
        if self._read_count == 1:
            logger.info("🎵 Audio source read() called for the first time - Discord is requesting audio!")
        elif self._read_count <= 5:  # Log first 5 calls only
            logger.info(f"🎵 Audio source read() #{self._read_count}: {len(audio_packet) if audio_packet else 0} bytes")
            
        result = audio_packet if audio_packet else self.audio_buffer.get_silence_frame()
            
        return result

    def get_stats(self) -> dict:
        """Get performance statistics."""
        buffer_stats = self.audio_buffer.get_stats()
        return {
            "read_count": self._read_count,
            "is_playing": self._is_playing,
            "buffer_stats": buffer_stats
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


class BinaryAudioMessage:
    """
    Binary message format for audio transmission over WebSocket.
    
    This eliminates JSON serialization and Base64 encoding overhead,
    providing significant latency and bandwidth improvements.
    """
    
    def __init__(self, speaker_id: str, channel_id: int, audio_data: bytes):
        self.speaker_id = speaker_id.encode('utf-8')
        self.channel_id = channel_id
        self.audio_data = audio_data
    
    def to_bytes(self) -> bytes:
        """
        Convert to binary format for transmission.
        
        Format: [4 bytes total_length][speaker_id_length][speaker_id][8 bytes channel_id][audio_data]
        """
        speaker_len = len(self.speaker_id)
        total_len = 4 + 1 + speaker_len + 8 + len(self.audio_data)
        
        return struct.pack(
            f'<IB{speaker_len}sQ{len(self.audio_data)}s',
            total_len,
            speaker_len,
            self.speaker_id,
            self.channel_id,
            self.audio_data
        )
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'BinaryAudioMessage':
        """Parse binary format message."""
        if len(data) < 13:  # Minimum size check (4 + 1 + 8 = 13)
            raise ValueError("Invalid binary message format")
        
        total_len = struct.unpack('<I', data[:4])[0]
        speaker_len = struct.unpack('<B', data[4:5])[0]
        
        if len(data) < 13 + speaker_len:
            raise ValueError("Invalid binary message format")
        
        speaker_id_bytes = data[5:5+speaker_len]
        channel_id = struct.unpack('<Q', data[5+speaker_len:13+speaker_len])[0]
        audio_data = data[13+speaker_len:]
        
        return cls(speaker_id_bytes.decode('utf-8'), channel_id, audio_data)
    
    @classmethod
    def get_message_type(cls) -> bytes:
        """Get the message type identifier for protocol negotiation."""
        return b'AUDIO'  # 5-byte message type identifier


