"""
Audio buffering components for the Discord Audio Router system.

This module provides thread-safe audio buffering capabilities for handling
Opus audio packets with both async and synchronous interfaces.
"""

import asyncio
import logging
import queue
import threading
from typing import Optional

logger = logging.getLogger(__name__)


class AudioBuffer:
    """Thread-safe buffer for Opus packets using both async and sync interfaces."""

    def __init__(self, max_size: int = 100):
        """
        Initialize the audio buffer.

        Args:
            max_size: Maximum number of packets to buffer
        """
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
        except queue.Full:
            # Remove oldest item and add new one
            try:
                self._sync_queue.get_nowait()
                self._sync_queue.put_nowait(data)
                logger.warning("Audio buffer queue full, dropped oldest packet")
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

    def size(self) -> int:
        """Get the current number of buffered packets."""
        return len(self._async_buffer)

    def is_empty(self) -> bool:
        """Check if the buffer is empty."""
        return len(self._async_buffer) == 0

    def is_full(self) -> bool:
        """Check if the buffer is full."""
        return len(self._async_buffer) >= self.max_size
