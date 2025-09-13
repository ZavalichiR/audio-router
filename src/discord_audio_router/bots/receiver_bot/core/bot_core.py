"""Core Audio Receiver Bot implementation."""

import asyncio
import logging
from typing import Optional

from discord.ext import commands, voice_recv

from discord_audio_router.infrastructure import setup_logging

from ..handlers.event_handlers import EventHandlers
from ..handlers.websocket_handlers import WebSocketHandlers
from ..handlers.audio_handlers import AudioHandlers
from ..utils.config import BotConfig
from ..utils.performance import PerformanceMonitor


class AudioReceiverBot:
    """Audio receiver bot with binary protocol and performance improvements."""

    def __init__(self):
        """Initialize the audio receiver bot."""
        # Setup logging
        self.logger = setup_logging(
            component_name="audioreceiver_bot",
            log_file="logs/audioreceiver_bot.log",
        )

        # Load configuration
        self.config = BotConfig()

        # Log configuration for debugging
        self.logger.info("AudioReceiver bot configuration:")
        self.logger.info(f"  Bot ID: {self.config.bot_id}")
        self.logger.info(f"  Channel ID: {self.config.channel_id}")
        self.logger.info(f"  Guild ID: {self.config.guild_id}")
        self.logger.info(f"  Speaker Channel ID: {self.config.speaker_channel_id}")

        # Bot setup
        intents = self.config.get_discord_intents()
        self.bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

        # Audio handling
        self.voice_client: Optional[voice_recv.VoiceRecvClient] = None

        # Initialize handlers
        self.performance_monitor = PerformanceMonitor(logger=self.logger)

        self.audio_handlers = AudioHandlers(
            performance_monitor=self.performance_monitor,
            logger=self.logger,
        )

        self.websocket_handlers = WebSocketHandlers(
            bot_id=self.config.bot_id,
            channel_id=self.config.channel_id,
            guild_id=self.config.guild_id,
            speaker_channel_id=self.config.speaker_channel_id,
            server_url=self.config.centralized_server_url,
            logger=self.logger,
        )

        # Set the audio callback for WebSocket handlers
        self.websocket_handlers.set_audio_callback(
            self.audio_handlers.process_audio_data
        )

        self.event_handlers = EventHandlers(
            bot=self,
            websocket_handlers=self.websocket_handlers,
            audio_handlers=self.audio_handlers,
            config=self.config,
            logger=self.logger,
        )

        # Setup bot events
        self.event_handlers.setup_events()

        # Start monitoring tasks
        self._monitoring_tasks = []

    async def start(self) -> None:
        """Start the audio receiver bot."""
        try:
            self.logger.info(f"Starting AudioReceiver bot {self.config.bot_id}...")

            # Start monitoring tasks
            self._start_monitoring_tasks()

            # Start the bot
            await self.bot.start(self.config.bot_token)

        except Exception as e:
            self.logger.error(f"Failed to start AudioReceiver bot: {e}", exc_info=True)
            raise

    def _start_monitoring_tasks(self) -> None:
        """Start background monitoring tasks."""
        # Performance monitoring
        self._monitoring_tasks.append(asyncio.create_task(self._monitor_performance()))

    async def _monitor_performance(self) -> None:
        """Monitor and log performance statistics."""
        while True:
            try:
                await asyncio.sleep(30)  # Log stats every 30 seconds

                # Get audio buffer stats
                buffer_stats = self.audio_handlers.get_buffer_stats()
                await self.performance_monitor.log_performance_stats(buffer_stats)

            except Exception as e:
                self.logger.error(
                    f"Error in performance monitoring: {e}", exc_info=True
                )
                await asyncio.sleep(30)

    async def stop(self) -> None:
        """Stop the audio receiver bot."""
        try:
            self.logger.info(f"Stopping AudioReceiver bot {self.config.bot_id}...")

            # Cancel monitoring tasks
            for task in self._monitoring_tasks:
                task.cancel()

            # Disconnect and cleanup
            await self.disconnect()

            # Close the bot
            if not self.bot.is_closed():
                await self.bot.close()

            self.logger.info("AudioReceiver bot stopped")

        except Exception as e:
            self.logger.error(f"Error stopping AudioReceiver bot: {e}", exc_info=True)

    async def disconnect(self) -> None:
        """Disconnect from voice channel and cleanup."""
        try:
            if self.voice_client:
                await self.voice_client.disconnect()
                self.voice_client = None

            # Stop audio playback
            self.audio_handlers.stop_audio_playback()

            # Disconnect from WebSocket
            await self.websocket_handlers.disconnect()

            self.logger.info("AudioReceiver bot disconnected and cleaned up")

        except Exception as e:
            self.logger.error(f"Error during disconnect: {e}", exc_info=True)


async def main():
    """Main function to run the audio receiver bot."""
    try:
        # Create and start the audio receiver bot
        audioreceiver_bot = AudioReceiverBot()

        # Start the bot (connection to voice channel happens in on_ready)
        await audioreceiver_bot.start()

    except KeyboardInterrupt:
        logging.info("AudioReceiver bot shutdown requested")
    except Exception as e:
        logging.critical(f"Fatal error in AudioReceiver bot: {e}")
        raise
    finally:
        if "audioreceiver_bot" in locals():
            await audioreceiver_bot.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("AudioReceiver bot interrupted")
    except Exception as e:
        logging.critical(f"AudioReceiver bot crashed: {e}")
        import sys

        sys.exit(1)
