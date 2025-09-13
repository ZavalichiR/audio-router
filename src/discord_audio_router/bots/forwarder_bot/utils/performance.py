"""Performance monitoring utilities for the Audio Forwarder Bot."""

import time
import logging


class PerformanceMonitor:
    """Performance monitoring for the Audio Forwarder Bot."""

    def __init__(self, logger: logging.Logger):
        """Initialize performance monitor."""
        self.logger = logger
        self._audio_packets_sent = 0
        self._bytes_sent = 0
        self._start_time = time.time()
        self._last_stats_time = time.time()

    def record_audio_packet(self, data_size: int) -> None:
        """Record an audio packet being sent."""
        self._audio_packets_sent += 1
        self._bytes_sent += data_size

    async def log_performance_stats(self) -> None:
        """Log current performance statistics."""
        current_time = time.time()
        uptime = current_time - self._start_time
        time_since_last = current_time - self._last_stats_time

        if time_since_last > 0:
            packets_per_second = self._audio_packets_sent / time_since_last
            bytes_per_second = self._bytes_sent / time_since_last

            self.logger.info(
                f"Performance stats - Uptime: {uptime:.1f}s, "
                f"Packets/sec: {packets_per_second:.1f}, "
                f"Bytes/sec: {bytes_per_second:.1f}, "
                f"Total packets: {self._audio_packets_sent}"
            )

            # Reset counters
            self._audio_packets_sent = 0
            self._bytes_sent = 0
            self._last_stats_time = current_time

    def get_stats(self) -> dict:
        """Get current performance statistics."""
        current_time = time.time()
        uptime = current_time - self._start_time
        time_since_last = current_time - self._last_stats_time

        stats = {
            "uptime": uptime,
            "total_packets": self._audio_packets_sent,
            "total_bytes": self._bytes_sent,
        }

        if time_since_last > 0:
            stats.update(
                {
                    "packets_per_second": self._audio_packets_sent / time_since_last,
                    "bytes_per_second": self._bytes_sent / time_since_last,
                }
            )

        return stats
