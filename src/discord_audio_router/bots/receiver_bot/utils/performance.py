"""Performance monitoring utilities for the Audio Receiver Bot."""

import time
import logging


class PerformanceMonitor:
    """Performance monitoring for the Audio Receiver Bot."""

    def __init__(self, logger: logging.Logger):
        """Initialize performance monitor."""
        self.logger = logger
        self._audio_packets_received = 0
        self._bytes_received = 0
        self._start_time = time.time()
        self._last_stats_time = time.time()
        self._binary_protocol_enabled = False

    def record_audio_packet(self, data_size: int) -> None:
        """Record an audio packet being received."""
        self._audio_packets_received += 1
        self._bytes_received += data_size

    def set_binary_protocol_enabled(self, enabled: bool) -> None:
        """Set whether binary protocol is enabled."""
        self._binary_protocol_enabled = enabled

    async def log_performance_stats(self, audio_buffer_stats: dict = None) -> None:
        """Log current performance statistics."""
        current_time = time.time()
        uptime = current_time - self._start_time
        time_since_last = current_time - self._last_stats_time

        if time_since_last > 0:
            packets_per_second = self._audio_packets_received / time_since_last
            bytes_per_second = self._bytes_received / time_since_last

            buffer_info = ""
            if audio_buffer_stats:
                buffer_info = (
                    f", Buffer size: {audio_buffer_stats.get('current_size', 0)}, "
                    f"Jitter delay: {audio_buffer_stats.get('jitter_delay', 0):.3f}s"
                )

            self.logger.info(
                f"Performance stats - Uptime: {uptime:.1f}s, "
                f"Packets/sec: {packets_per_second:.1f}, "
                f"Bytes/sec: {bytes_per_second:.1f}, "
                f"Total packets: {self._audio_packets_received}"
                f"{buffer_info}, "
                f"Binary protocol: {self._binary_protocol_enabled}"
            )

            # Reset counters
            self._audio_packets_received = 0
            self._bytes_received = 0
            self._last_stats_time = current_time

    def get_stats(self) -> dict:
        """Get current performance statistics."""
        current_time = time.time()
        uptime = current_time - self._start_time
        time_since_last = current_time - self._last_stats_time

        stats = {
            "uptime": uptime,
            "total_packets": self._audio_packets_received,
            "total_bytes": self._bytes_received,
            "binary_protocol_enabled": self._binary_protocol_enabled,
        }

        if time_since_last > 0:
            stats.update(
                {
                    "packets_per_second": self._audio_packets_received
                    / time_since_last,
                    "bytes_per_second": self._bytes_received / time_since_last,
                }
            )

        return stats
