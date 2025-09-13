"""Core Audio Forwarder Bot implementation."""

import asyncio
import logging
from typing import Optional

from discord.ext import commands, voice_recv

from discord_audio_router.infrastructure import setup_logging

from ..handlers.event_handlers import EventHandlers
from ..handlers.websocket_handlers import WebSocketHandlers
from ..utils.config import BotConfig
from ..utils.performance import PerformanceMonitor


class AudioForwarderBot:
    """Audio forwarder bot with binary protocol and performance improvements."""

    def __init__(self):
        """Initialize the audio forwarder bot."""
        # Setup logging
        self.logger = setup_logging(
            component_name="audioforwarder_bot",
            log_file="logs/audioforwarder_bot.log",
        )

        # Load configuration
        self.config = BotConfig()

        # Bot setup
        intents = self.config.get_discord_intents()
        self.bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

        # Audio handling
        self.voice_client: Optional[voice_recv.VoiceRecvClient] = None
        self.audio_sink: Optional[object] = None

        # Initialize handlers
        self.websocket_handlers = WebSocketHandlers(
            bot_id=self.config.bot_id,
            channel_id=self.config.channel_id,
            guild_id=self.config.guild_id,
            server_url=self.config.centralized_server_url,
            logger=self.logger,
        )

        self.event_handlers = EventHandlers(
            bot=self,
            websocket_handlers=self.websocket_handlers,
            config=self.config,
            logger=self.logger,
        )

        # Performance monitoring
        self.performance_monitor = PerformanceMonitor(logger=self.logger)

        # Setup bot events
        self.event_handlers.setup_events()

        # Start monitoring tasks
        self._monitoring_tasks = []

    async def start(self) -> None:
        """Start the audio forwarder bot."""
        try:
            self.logger.info(f"Starting AudioForwarder bot {self.config.bot_id}...")

            # Store the event loop for use in audio callbacks
            event_loop = asyncio.get_running_loop()
            self.websocket_handlers.set_event_loop(event_loop)

            # Start monitoring tasks
            self._start_monitoring_tasks()

            # Start the bot
            await self.bot.start(self.config.bot_token)

        except Exception as e:
            self.logger.error(f"Failed to start AudioForwarder bot: {e}", exc_info=True)
            raise

    def _start_monitoring_tasks(self) -> None:
        """Start background monitoring tasks."""
        # Voice connection monitoring
        self._monitoring_tasks.append(
            asyncio.create_task(self._monitor_voice_connection())
        )

        # Performance monitoring
        self._monitoring_tasks.append(asyncio.create_task(self._monitor_performance()))

    async def _monitor_voice_connection(self) -> None:
        """Monitor voice connection and reconnect if needed."""
        status_counter = 0
        while True:
            try:
                await asyncio.sleep(15)  # Check every 15 seconds
                status_counter += 1

                if not self.voice_client or not self.voice_client.is_connected():
                    self.logger.warning(
                        "Voice client disconnected, attempting to reconnect..."
                    )
                    # Only reconnect if we're not already trying to connect
                    if not self.event_handlers._connecting:
                        await self.event_handlers.connect_to_channel()
                else:
                    # Log status every 60 seconds (4 * 15 seconds)
                    if status_counter % 4 == 0:
                        self.logger.info(
                            f"Voice connection healthy, centralized server: {'Connected' if self.websocket_handlers.websocket else 'Disconnected'}"
                        )

            except Exception as e:
                self.logger.error(
                    f"Error in voice connection monitoring: {e}", exc_info=True
                )
                await asyncio.sleep(15)  # Wait before retrying

    async def _monitor_performance(self) -> None:
        """Monitor and log performance statistics."""
        while True:
            try:
                await asyncio.sleep(30)  # Log stats every 30 seconds
                await self.performance_monitor.log_performance_stats()

            except Exception as e:
                self.logger.error(
                    f"Error in performance monitoring: {e}", exc_info=True
                )
                await asyncio.sleep(30)

    async def stop(self) -> None:
        """Stop the audio forwarder bot."""
        try:
            self.logger.info(f"Stopping AudioForwarder bot {self.config.bot_id}...")

            # Cancel monitoring tasks
            for task in self._monitoring_tasks:
                task.cancel()

            # Disconnect and cleanup
            await self.disconnect()

            # Close the bot
            if not self.bot.is_closed():
                await self.bot.close()

            self.logger.info("AudioForwarder bot stopped")

        except Exception as e:
            self.logger.error(f"Error stopping AudioForwarder bot: {e}", exc_info=True)

    async def disconnect(self) -> None:
        """Disconnect from voice channel and cleanup."""
        try:
            if self.voice_client:
                await self.voice_client.disconnect()
                self.voice_client = None

            await self.websocket_handlers.disconnect()

            self.logger.info("AudioForwarder bot disconnected and cleaned up")

        except Exception as e:
            self.logger.error(f"Error during disconnect: {e}", exc_info=True)


async def main():
    """Main function to run the audio forwarder bot."""
    try:
        # Create and start the audio forwarder bot
        audioforwarder_bot = AudioForwarderBot()

        # Start the bot (connection to voice channel happens in on_ready)
        await audioforwarder_bot.start()

    except KeyboardInterrupt:
        logging.info("AudioForwarder bot shutdown requested")
    except Exception as e:
        logging.critical(f"Fatal error in AudioForwarder bot: {e}")
        raise
    finally:
        if "audioforwarder_bot" in locals():
            await audioforwarder_bot.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("AudioForwarder bot interrupted")
    except Exception as e:
        logging.critical(f"AudioForwarder bot crashed: {e}")
        import sys

        sys.exit(1)
