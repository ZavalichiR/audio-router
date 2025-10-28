"""Event handlers for the Audio Forwarder Bot."""

import asyncio
import logging
from typing import Any

import discord
from discord.ext import commands, voice_recv
from discord_audio_router.audio import setup_audio_receiver
from discord_audio_router.websockets.client import WebSocketClient
from discord_audio_router.bots.forwarder_bot.utils.config import BotConfig


class EventHandlers:
    """Handles Discord bot events for the Audio Forwarder Bot."""

    def __init__(
        self,
        bot: Any,
        websocket_client: WebSocketClient,
        config: BotConfig,
        logger: logging.Logger,
    ):
        """Initialize event handlers."""
        self.bot_instance = bot
        self.bot: commands.Bot = bot.bot
        self.websocket_client = websocket_client
        self.config = config
        self.logger = logger
        self._connecting = False
        self._initialized = False

    def setup_events(self) -> None:
        """Setup bot event handlers."""

        @self.bot.event
        async def on_ready():
            if not self._initialized:
                self._initialized = True
                self.logger.info(f"[{self.config.bot_id}] Bot ready to connect")
                # Connect websockets
                await self.websocket_client.connect()
                self.logger.info(f"[{self.config.bot_id}] Websocket connected")

                # First-time voice connection
                await asyncio.sleep(1)
                await self.connect_to_channel()
                self.logger.info(f"[{self.config.bot_id}] Voice connection established")

                self.logger.info(f"[{self.config.bot_id}] Bot ready")

        @self.bot.event
        async def on_resumed():
            self.logger.info(
                f"[{self.config.bot_id}] Session resumed—reconnecting WebSocket and voice"
            )
            # Reconnect WebSocket first (session resume often breaks WebSocket)
            await self.websocket_client.connect()
            await asyncio.sleep(0.5)
            await self.connect_to_channel()

    async def _setup_audio_sink(self, voice_client: voice_recv.VoiceRecvClient) -> None:
        """Setup audio sink."""
        if self.bot_instance.audio_sink:
            return

        try:
            self.logger.info(
                f"[{self.config.bot_id}] Setting up audio sink with callback: {self.websocket_client.forward_audio}"
            )
            self.bot_instance.audio_sink = await setup_audio_receiver(
                voice_client,
                self.websocket_client.forward_audio,
            )
            self.logger.info(f"[{self.config.bot_id}] Audio sink setup complete")
        except Exception as e:
            self.logger.error(f"[{self.config.bot_id}] Audio sink setup failed: {e}")
            self.bot_instance.audio_sink = None

    async def connect_to_channel(self) -> bool:
        """Connect to the speaker channel and start audio capture."""
        if not self._initialized:
            self.logger.debug(
                f"[{self.config.bot_id}] Bot not initialized, skipping connection"
            )
            return False

        if self._connecting:
            self.logger.debug(
                f"[{self.config.bot_id}] Connection attempt already in progress"
            )
            return False

        self._connecting = True
        try:
            guild = self.bot.get_guild(self.config.guild_id)
            if not guild:
                guild = await self.bot.fetch_guild(self.config.guild_id)

            channel = guild.get_channel(self.config.channel_id)
            if not channel:
                self.logger.error(
                    f"[{self.config.bot_id}] Channel {self.config.channel_id} not found"
                )
                return False

            try:
                voice_client = await channel.connect(
                    cls=voice_recv.VoiceRecvClient,
                    timeout=20.0,
                    reconnect=True,
                    self_deaf=True,
                    self_mute=False,
                )
            except discord.ClientException:
                # Already connected: retrieve the existing client
                voice_client = guild.voice_client
            except asyncio.TimeoutError:
                self.logger.error(f"[{self.config.bot_id}] Voice connection timed out")
                return False
            except Exception as e:
                self.logger.error(
                    f"[{self.config.bot_id}] Unexpected error connecting to voice: {e}",
                    exc_info=True,
                )
                return False

            await self._setup_audio_sink(voice_client)
            return True

        except Exception as e:
            self.logger.error(
                f"[{self.config.bot_id}] connect_to_channel error: {e}",
                exc_info=True,
            )
            return False
        finally:
            self._connecting = False
