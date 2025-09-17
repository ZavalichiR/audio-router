"""Event handlers for the Audio Receiver Bot."""

import asyncio
import logging
from typing import Any

import discord
from discord.ext import commands, voice_recv

from discord_audio_router.bots.receiver_bot.handlers.audio_handlers import AudioHandlers
from discord_audio_router.bots.receiver_bot.handlers.websocket_handlers import (
    WebSocketHandlers,
)
from discord_audio_router.bots.receiver_bot.utils.config import BotConfig


class EventHandlers:
    """Handles Discord bot events for the Audio Receiver Bot."""

    def __init__(
        self,
        bot: Any,
        websocket_handlers: WebSocketHandlers,
        audio_handlers: AudioHandlers,
        config: BotConfig,
        logger: logging.Logger,
    ):
        """Initialize event handlers."""
        self.bot_instance = bot
        self.bot: commands.Bot = bot.bot
        self.websocket_handlers = websocket_handlers
        self.audio_handlers = audio_handlers
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

                # Ensure the bot has the correct role and connect websockets
                await self._ensure_listener_role()
                await self.websocket_handlers.connect()

                # Connect to the listener channel
                await asyncio.sleep(1)
                await self.connect_to_channel()

                self.logger.info(f"[{self.config.bot_id}] Bot ready")

        @self.bot.event
        async def on_resumed():
            self.logger.info(
                f"[{self.config.bot_id}] Session resumed—reconnecting voice if needed"
            )
            await self.connect_to_channel()

    async def _ensure_listener_role(self) -> None:
        """Ensure the AudioReceiver bot has the Listener role to join listener channels."""
        try:
            guild = self.bot.get_guild(self.config.guild_id)
            if not guild:
                self.logger.warning(
                    f"[{self.config.bot_id}] Guild {self.config.guild_id} not in cache, fetching..."
                )
                guild = await self.bot.fetch_guild(self.config.guild_id)

            bot_member = guild.get_member(self.bot.user.id)
            if not bot_member:
                self.logger.error(
                    f"[{self.config.bot_id}] Bot member not found in guild {guild.name}"
                )
                return

            listener_role = discord.utils.get(guild.roles, name="Listener")
            if not listener_role:
                self.logger.warning(
                    f"[{self.config.bot_id}] Listener role not found in guild roles"
                )
                return

            if listener_role in bot_member.roles:
                self.logger.debug(
                    f"[{self.config.bot_id}] Bot already has Listener role"
                )
                return

            try:
                await bot_member.add_roles(
                    listener_role,
                    reason="AudioReceiver bot needs Listener role",
                )
                self.logger.info(f"[{self.config.bot_id}] Added Listener role to bot")
            except discord.Forbidden:
                self.logger.warning(
                    f"[{self.config.bot_id}] Insufficient permissions to add Listener role"
                )
            except Exception as e:
                self.logger.error(
                    f"[{self.config.bot_id}] Error adding role: {e}", exc_info=True
                )
        except Exception as e:
            self.logger.error(
                f"[{self.config.bot_id}] Error in _ensure_listener_role: {e}",
                exc_info=True,
            )

    def _setup_audio_playback(self, voice_client: voice_recv.VoiceRecvClient) -> None:
        """Setup audio playback."""
        success = self.audio_handlers.start_audio_playback(voice_client)
        if not success:
            self.logger.error(f"[{self.config.bot_id}] Failed to start audio playback")

    async def connect_to_channel(self) -> bool:
        """Connect to the listener channel and start audio playback."""
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
                    timeout=30.0,
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

            self._setup_audio_playback(voice_client)
            return True

        except Exception as e:
            self.logger.error(
                f"[{self.config.bot_id}] connect_to_channel error: {e}",
                exc_info=True,
            )
            return False
        finally:
            self._connecting = False
