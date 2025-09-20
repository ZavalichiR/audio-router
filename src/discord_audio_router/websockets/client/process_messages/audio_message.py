"""
Client-side audio message handler.

This module handles audio message processing for WebSocket clients.
"""

import logging
from typing import Callable, Optional


class AudioMessageHandler:
    """Handles audio message processing for WebSocket clients."""

    def __init__(
        self,
        logger: logging.Logger,
        audio_callback: Optional[Callable] = None,
        track_audio_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        """
        Initialize the audio message handler.

        Args:
            logger: Logger instance
            audio_callback: Callback for audio data (for receiver clients)
            track_audio_callback: Callback to track received audio packets
        """
        self.logger: logging.Logger = logger
        self.audio_callback: Optional[Callable[[bytes], None]] = audio_callback
        self.track_audio_callback: Optional[Callable[[], None]] = track_audio_callback

    async def process_audio_message(self, audio_data: bytes) -> None:
        """
        Process binary audio messages.

        Args:
            audio_data: Binary audio data
        """
        if self.audio_callback:
            try:
                await self.audio_callback(audio_data)
                if self.track_audio_callback:
                    self.track_audio_callback()
            except Exception as e:
                self.logger.error(f"Error processing audio data: {e}", exc_info=True)
        else:
            self.logger.warning("No audio callback set, ignoring audio data")
