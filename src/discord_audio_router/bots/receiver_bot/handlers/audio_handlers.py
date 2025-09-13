"""Audio processing handlers for the Audio Receiver Bot."""

import logging
from typing import Optional

from discord_audio_router.audio import AudioBuffer, OpusAudioSource


class AudioHandlers:
    """Handles audio processing for the receiver bot."""

    def __init__(
        self,
        performance_monitor: Optional[object] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize audio handlers."""
        self.performance_monitor = performance_monitor
        self.logger = logger or logging.getLogger(__name__)
        self.audio_buffer: Optional[AudioBuffer] = None
        self.audio_source: Optional[OpusAudioSource] = None

    def setup_audio(self) -> None:
        """Setup audio buffer and source."""
        self.audio_buffer = AudioBuffer()
        self.audio_source = OpusAudioSource(self.audio_buffer)
        self.logger.info("Audio buffer and source created")

    async def process_audio_data(self, audio_data: bytes) -> None:
        """Process received audio data."""
        if not self.audio_buffer:
            self.logger.warning("Received audio data but no buffer available")
            return

        # Add audio data to buffer
        await self.audio_buffer.put(audio_data)

        # Record performance metrics
        if self.performance_monitor:
            self.performance_monitor.record_audio_packet(len(audio_data))

        # Debug logging for first few packets only
        if hasattr(self.performance_monitor, "_audio_packets_received"):
            if self.performance_monitor._audio_packets_received <= 3:
                buffer_stats = self.audio_buffer.get_stats()
                self.logger.debug(
                    f"🎵 Received audio packet #{self.performance_monitor._audio_packets_received}: "
                    f"{len(audio_data)} bytes. Buffer stats: {buffer_stats}"
                )

    def start_audio_playback(self, voice_client) -> bool:
        """Start audio playback on the voice client."""
        try:
            if not self.audio_source:
                self.logger.error("Audio source not initialized")
                return False

            # Start the audio source first
            self.audio_source.start()
            self.logger.info("Audio source started successfully")

            # Then start playing
            voice_client.play(self.audio_source)
            self.logger.info("Voice client play() called")

            # Check if the voice client is actually playing
            self.logger.info(f"Voice client is_playing: {voice_client.is_playing()}")

            return True

        except Exception as e:
            self.logger.error(f"Error starting audio playback: {e}", exc_info=True)
            return False

    def stop_audio_playback(self) -> None:
        """Stop audio playback and cleanup."""
        try:
            if self.audio_source:
                self.audio_source.stop()
                self.audio_source = None
                self.logger.info("Audio source stopped")

            if self.audio_buffer:
                self.audio_buffer.clear()
                self.audio_buffer = None
                self.logger.info("Audio buffer cleared")

        except Exception as e:
            self.logger.error(f"Error stopping audio playback: {e}", exc_info=True)

    def get_buffer_stats(self) -> dict:
        """Get audio buffer statistics."""
        if self.audio_buffer:
            return self.audio_buffer.get_stats()
        return {}
