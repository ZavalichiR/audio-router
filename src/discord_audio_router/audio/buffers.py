# buffers.py
"""
Audio buffering components for the Discord Audio Router system.

This module provides thread-safe audio buffering capabilities for handling
Opus audio packets with both async and synchronous interfaces.
"""

import asyncio
import logging
import queue
import threading
import time
from collections import deque
from typing import Optional

logger = logging.getLogger(__name__)


class AudioBuffer:
    """High-performance thread-safe buffer for Opus packets with optimized latency."""

    def __init__(self, max_size: int = 100):
        """
        Initialize the audio buffer.

        Args:
            max_size: Maximum number of packets to buffer (optimized for low latency)
        """
        # Use deque for O(1) operations on both ends
        self._async_buffer: deque[bytes] = deque(maxlen=max_size)
        self._sync_queue: queue.Queue[bytes] = queue.Queue(maxsize=max_size)
        self.max_size = max_size
        self._async_lock = asyncio.Lock()
        self._sync_lock = threading.Lock()

        # Performance tracking
        self._total_packets = 0
        self._dropped_packets = 0
        self._last_activity = time.time()

        # Pre-allocate silence frame for consistent performance
        self._silence_frame = b"\xf8\xff\xfe"

    async def put(self, data: bytes):
        """Add an Opus packet to the buffer (async interface)."""
        self._total_packets += 1
        self._last_activity = time.time()

        async with self._async_lock:
            if len(self._async_buffer) >= self.max_size:
                self._async_buffer.popleft()
                self._dropped_packets += 1
            self._async_buffer.append(data)

        # Also add to sync queue for synchronous access
        try:
            self._sync_queue.put_nowait(data)
        except queue.Full:
            # Remove oldest item and add new one
            try:
                self._sync_queue.get_nowait()
                self._sync_queue.put_nowait(data)
                self._dropped_packets += 1
                logger.debug("Audio buffer queue full, dropped oldest packet")
            except queue.Empty:
                pass

    async def get(self) -> Optional[bytes]:
        """Retrieve the oldest Opus packet, or None if empty (async interface)."""
        async with self._async_lock:
            return self._async_buffer.popleft() if self._async_buffer else None

    def get_sync(
        self, timeout: float = 0.001
    ) -> Optional[bytes]:  # Reduced timeout for lower latency (from 0.005 to 0.001)
        """Retrieve the oldest Opus packet synchronously (for discord.py)."""
        try:
            return self._sync_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def get_silence_frame(self) -> bytes:
        """Get pre-allocated silence frame for consistent performance."""
        return self._silence_frame

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

    def size(self) -> int:
        """Get the current number of buffered packets."""
        return len(self._async_buffer)

    def is_empty(self) -> bool:
        """Check if the buffer is empty."""
        return len(self._async_buffer) == 0

    def is_full(self) -> bool:
        """Check if the buffer is full."""
        return len(self._async_buffer) >= self.max_size

    def get_stats(self) -> dict:
        """Get performance statistics."""
        return {
            "total_packets": self._total_packets,
            "dropped_packets": self._dropped_packets,
            "current_size": len(self._async_buffer),
            "max_size": self.max_size,
            "last_activity": self._last_activity,
            "drop_rate": self._dropped_packets / max(self._total_packets, 1) * 100,
        }
