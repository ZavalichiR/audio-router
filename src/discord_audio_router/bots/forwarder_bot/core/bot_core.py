"""Core Audio Forwarder Bot implementation."""

import asyncio
import logging
from typing import Optional

from discord.ext import commands, voice_recv
from discord_audio_router.infrastructure import setup_logging

from discord_audio_router.core.types import WS_CLIENT_TYPE_FWD
from discord_audio_router.websockets.client import WebSocketClient

from ..handlers.event_handlers import EventHandlers
from ..utils.config import BotConfig


class AudioForwarderBot:
    """Audio forwarder bot with simplified connection logic."""

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

        # Audio handling - removed local voice_client storage
        self.audio_sink: Optional[object] = None

        # Initialize WebSocket client
        client_id = f"{self.config.guild_id}_{self.config.channel_id}"

        self.websocket_client = WebSocketClient(
            client_id=client_id,
            client_type=WS_CLIENT_TYPE_FWD,
            server_url=self.config.centralized_server_url,
            logger=self.logger,
        )

        self.event_handlers = EventHandlers(
            bot=self,
            websocket_client=self.websocket_client,
            config=self.config,
            logger=self.logger,
        )

        # Setup bot events
        self.event_handlers.setup_events()

        # Single monitoring task
        self._voice_monitoring_task = None

    async def start(self) -> None:
        """Start the audio forwarder bot."""
        try:
            self.logger.info(f"[{self.config.bot_id}] Starting bot ...")

            # Start the bot
            await self.bot.start(self.config.bot_token)

            # Start monitoring task
            self._start_monitoring_task()
            self.logger.info(f"[{self.config.bot_id}] Bot started!")

        except Exception as e:
            self.logger.error(
                f"[{self.config.bot_id}] Failed to start bot: {e}",
                exc_info=True,
            )
            raise

    def _start_monitoring_task(self) -> None:
        """Start background monitoring task."""
        self.logger.info(f"[{self.config.bot_id}] Starting voice monitoring")
        self._voice_monitoring_task = asyncio.create_task(
            self._monitor_voice_connection()
        )

    async def _monitor_voice_connection(self) -> None:
        """Monitor voice connection and reconnect if needed."""
        check_interval = 20
        while True:
            try:
                await asyncio.sleep(check_interval)
                self.logger.debug(
                    f"[{self.config.bot_id}] Checking voice connection ..."
                )

                guild = self.bot.get_guild(self.config.guild_id)
                if not guild:
                    self.logger.warning(
                        f"[{self.config.bot_id}] Guild {self.config.guild_id} not found"
                    )
                    continue

                voice_client: voice_recv.VoiceRecvClient = guild.voice_client
                target_channel_id = self.config.channel_id

                # Check if we need to connect/reconnect
                should_reconnect = (
                    not voice_client
                    or not voice_client.is_connected()
                    or voice_client.channel.id != target_channel_id
                )

                if should_reconnect and not self.event_handlers._connecting:
                    self.logger.warning(
                        f"[{self.config.bot_id}] VoiceClient is not connected or is in the wrong channel, reconnecting..."
                    )
                    await self.event_handlers.connect_to_channel()
                    check_interval = 10
                elif voice_client and voice_client.is_connected():
                    check_interval = 20
                    # Log status every 5 minutes (5 * 60 seconds)
                    if hasattr(self, "_status_counter"):
                        self._status_counter += 1
                    else:
                        self._status_counter = 1

                    if self._status_counter % 5 == 0:
                        status = (
                            "Connected"
                            if self.websocket_client.is_connected
                            else "Disconnected"
                        )
                        self.logger.info(
                            f"[{self.config.bot_id}] Voice connection healthy, centralized server: {status}"
                        )

            except Exception as e:
                self.logger.error(
                    f"[{self.config.bot_id}] Error in voice connection monitoring: {e}",
                    exc_info=True,
                )
                await asyncio.sleep(check_interval)

    async def stop(self) -> None:
        """Stop the audio forwarder bot."""
        try:
            self.logger.info(f"[{self.config.bot_id}] Stopping bot...")

            # Cancel monitoring task
            if self._voice_monitoring_task:
                self._voice_monitoring_task.cancel()

            # Disconnect and cleanup
            await self._disconnect()

            # Close the bot
            if not self.bot.is_closed():
                await self.bot.close()

            self.logger.info(f"[{self.config.bot_id}] Bot stopped")

        except Exception as e:
            self.logger.error(
                f"[{self.config.bot_id}] Error stopping bot: {e}",
                exc_info=True,
            )

    async def _disconnect(self) -> None:
        """Disconnect from voice channel and cleanup."""
        try:
            guild = self.bot.get_guild(self.config.guild_id)
            if guild and guild.voice_client:
                await guild.voice_client.disconnect()

            await self.websocket_client.disconnect()

            self.logger.info(
                f"[{self.config.bot_id}] Bot disconnected from {guild.name} and cleaned up"
            )

        except Exception as e:
            self.logger.error(
                f"[{self.config.bot_id}] Error during disconnect: {e}", exc_info=True
            )


async def main():
    """Main function to run the audio forwarder bot."""
    audioforwarder_bot = None
    try:
        # Create and start the audio forwarder bot
        audioforwarder_bot = AudioForwarderBot()

        # Start the bot (connection to voice channel happens in on_ready)
        await audioforwarder_bot.start()

    except KeyboardInterrupt:
        logging.info(f"[{audioforwarder_bot.config.bot_id}] Bot shutdown requested")
    except Exception as e:
        logging.critical(
            f"[{audioforwarder_bot.config.bot_id}] Fatal error in bot: {e}"
        )
        raise
    finally:
        if audioforwarder_bot:
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
