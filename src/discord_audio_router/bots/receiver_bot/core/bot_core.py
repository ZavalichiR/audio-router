"""Core Audio Receiver Bot implementation."""

import asyncio
import logging

from discord.ext import commands

from discord_audio_router.infrastructure import setup_logging

from ..handlers.event_handlers import EventHandlers
from ..handlers.websocket_handlers import WebSocketHandlers
from ..handlers.audio_handlers import AudioHandlers
from ..utils.config import BotConfig
from ..utils.performance import PerformanceMonitor


class AudioReceiverBot:
    """Audio receiver bot with simplified connection logic."""

    def __init__(self):
        """Initialize the audio receiver bot."""
        # Setup logging
        self.logger = setup_logging(
            component_name="audioreceiver_bot",
            log_file="logs/audioreceiver_bot.log",
        )

        # Load configuration
        self.config = BotConfig()

        # Bot setup
        intents = self.config.get_discord_intents()
        self.bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

        # Initialize handlers
        self.performance_monitor = PerformanceMonitor(logger=self.logger)

        self.audio_handlers = AudioHandlers(
            logger=self.logger,
            performance_monitor=self.performance_monitor,
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

        # Single monitoring task
        self._performance_monitoring_task = None

        # Single monitoring task
        self._voice_monitoring_task = None

    async def start(self) -> None:
        """Start the audio receiver bot."""
        try:
            self.logger.info(f"Starting AudioReceiver bot {self.config.bot_id}...")

            # Start monitoring task
            self._start_monitoring_performance_task()
            self._start_monitoring_voice_task()

            # Start the bot
            await self.bot.start(self.config.bot_token)

        except Exception as e:
            self.logger.error(f"Failed to start AudioReceiver bot: {e}", exc_info=True)
            raise

    def _start_monitoring_performance_task(self) -> None:
        """Start background monitoring task."""
        self._performance_monitoring_task = asyncio.create_task(
            self._monitor_performance()
        )

    async def _monitor_performance(self) -> None:
        """Monitor and log performance statistics."""
        while True:
            try:
                await asyncio.sleep(60)  # Log stats every 60 seconds

                # Get audio buffer stats
                buffer_stats = self.audio_handlers.get_buffer_stats()
                await self.performance_monitor.log_performance_stats(buffer_stats)

            except Exception as e:
                self.logger.error(
                    f"Error in performance monitoring: {e}", exc_info=True
                )
                await asyncio.sleep(60)

    def _start_monitoring_voice_task(self) -> None:
        """Start background monitoring task."""
        self._voice_monitoring_task = asyncio.create_task(
            self._monitor_voice_connection()
        )

    async def _monitor_voice_connection(self) -> None:
        """Monitor voice connection and reconnect if needed."""
        while True:
            try:
                await asyncio.sleep(20)  # Check every 20 seconds

                guild = self.bot.get_guild(self.config.guild_id)
                if not guild:
                    self.logger.warning(f"Guild {self.config.guild_id} not found")
                    continue

                voice_client = guild.voice_client
                target_channel_id = self.config.channel_id

                # Determine if reconnect is needed
                should_reconnect = (
                    not voice_client
                    or not voice_client.is_connected()
                    or voice_client.channel.id != target_channel_id
                )

                if should_reconnect and not self.event_handlers._connecting:
                    self.logger.info("Voice monitoring detected need to reconnect")
                    await self.event_handlers.connect_to_channel()
                elif voice_client and voice_client.is_connected():
                    # Log status every 5 minutes (5 * 60 seconds)
                    if hasattr(self, "_status_counter"):
                        self._status_counter += 1
                    else:
                        self._status_counter = 1

                    if self._status_counter % 5 == 0:
                        connected = (
                            "Connected"
                            if self.websocket_handlers.websocket
                            else "Disconnected"
                        )
                        self.logger.info(
                            f"Voice connection healthy, centralized server: {connected}"
                        )

            except Exception as e:
                self.logger.error(
                    f"Error in voice connection monitoring: {e}", exc_info=True
                )
                await asyncio.sleep(20)

    async def stop(self) -> None:
        """Stop the audio receiver bot."""
        try:
            self.logger.info(f"Stopping AudioReceiver bot {self.config.bot_id}...")

            # Cancel monitoring task
            if self._performance_monitoring_task:
                self._performance_monitoring_task.cancel()

            if self._voice_monitoring_task:
                self._voice_monitoring_task.cancel()

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
            guild = self.bot.get_guild(self.config.guild_id)
            if guild and guild.voice_client:
                await guild.voice_client.disconnect()

            # Stop audio playback
            self.audio_handlers.stop_audio_playback()

            # Disconnect from WebSocket
            await self.websocket_handlers.disconnect()

            self.logger.info("AudioReceiver bot disconnected and cleaned up")

        except Exception as e:
            self.logger.error(f"Error during disconnect: {e}", exc_info=True)


async def main():
    """Main function to run the audio receiver bot."""
    audioreceiver_bot = None
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
        if audioreceiver_bot:
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
