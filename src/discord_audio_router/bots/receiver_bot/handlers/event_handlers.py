"""Event handlers for the Audio Receiver Bot."""

import asyncio
import logging
from typing import Optional, Any

import discord
from discord.ext import commands, voice_recv

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
        audio_handlers: Any,
        config: BotConfig,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize event handlers."""
        self.bot_instance = bot
        self.bot: commands.Bot = bot.bot
        self.websocket_handlers = websocket_handlers
        self.audio_handlers = audio_handlers
        self.config = config
        self.logger = logger or logging.getLogger(__name__)

    def setup_events(self) -> None:
        """Setup bot event handlers."""

        @self.bot.event
        async def on_ready():
            self.logger.info(
                f"AudioReceiver bot {self.config.bot_id} ready: {self.bot.user}"
            )
            self.logger.info(
                f"Target channel: {self.config.channel_id}, Guild: {self.config.guild_id}"
            )

            # Ensure the bot has the Listener role
            await self._ensure_listener_role()

            # Connect to the listener channel with retry
            await self._connect_to_channel_with_retry()

            # Connect to AudioForwarder bot WebSocket
            await self.websocket_handlers.connect()

        @self.bot.event
        async def on_connect():
            self.logger.info(
                f"AudioReceiver bot {self.config.bot_id} connected to Discord"
            )

        @self.bot.event
        async def on_disconnect():
            self.logger.warning(
                f"AudioReceiver bot {self.config.bot_id} disconnected from Discord"
            )

    async def _ensure_listener_role(self) -> None:
        """Ensure the AudioReceiver bot has the Listener role to join listener channels."""
        try:
            guild = self.bot.get_guild(self.config.guild_id)
            if not guild:
                self.logger.error(f"Guild {self.config.guild_id} not found")
                return

            bot_member = guild.get_member(self.bot.user.id)
            if not bot_member:
                self.logger.error(f"Bot member not found in guild {guild.name}")
                return

            # Look for the Listener role
            listener_role = discord.utils.get(guild.roles, name="Listener")
            if not listener_role:
                self.logger.warning(
                    "Listener role not found - AudioReceiver bot may not be able to join listener channels"
                )
                return

            # Check if bot already has the Listener role
            if listener_role in bot_member.roles:
                self.logger.info(
                    f"AudioReceiver bot already has Listener role: {listener_role.name}"
                )
                return

            # Try to add the Listener role to the bot
            try:
                await bot_member.add_roles(
                    listener_role,
                    reason="AudioReceiver bot needs Listener role to join listener channels",
                )
                self.logger.info(
                    f"Added Listener role to AudioReceiver bot: {listener_role.name}"
                )
            except discord.Forbidden:
                self.logger.warning(
                    "Cannot add Listener role to AudioReceiver bot - insufficient permissions"
                )
            except Exception as e:
                self.logger.error(
                    f"Error adding Listener role to AudioReceiver bot: {e}",
                    exc_info=True,
                )

        except Exception as e:
            self.logger.error(
                f"Error ensuring Listener role for AudioReceiver bot: {e}",
                exc_info=True,
            )

    async def _connect_to_channel_with_retry(self) -> None:
        """Connect to voice channel with retry logic."""
        max_retries = 5
        retry_delay = 2.0

        for attempt in range(max_retries):
            try:
                success = await self.connect_to_channel()
                if success:
                    self.logger.info(
                        f"Successfully connected to voice channel on attempt {attempt + 1}"
                    )
                    return
                else:
                    self.logger.warning(
                        f"Failed to connect to voice channel on attempt {attempt + 1}"
                    )
            except Exception as e:
                self.logger.warning(
                    f"Exception connecting to voice channel on attempt {attempt + 1}: {e}"
                )

            if attempt < max_retries - 1:
                self.logger.info(
                    f"Retrying voice channel connection in {retry_delay} seconds..."
                )
                await asyncio.sleep(retry_delay)
                retry_delay *= 1.5  # Exponential backoff

        self.logger.error("Failed to connect to voice channel after all retries")

    async def connect_to_channel(self) -> bool:
        """Connect to the listener channel and start audio playback."""
        try:
            self.logger.info(
                f"Attempting to connect to voice channel {self.config.channel_id}"
            )

            guild = self.bot.get_guild(self.config.guild_id)
            if not guild:
                self.logger.warning(
                    f"Guild {self.config.guild_id} not found in cache, attempting to fetch..."
                )
                try:
                    # Try to fetch the guild directly from Discord
                    guild = await self.bot.fetch_guild(self.config.guild_id)
                    self.logger.info(f"Successfully fetched guild: {guild.name}")
                except discord.NotFound:
                    self.logger.error(
                        f"Guild {self.config.guild_id} not found on Discord"
                    )
                    return False
                except Exception as e:
                    self.logger.error(f"Error fetching guild: {e}")
                    return False

            self.logger.info(f"Found guild: {guild.name}")

            channel = guild.get_channel(self.config.channel_id)
            if not channel:
                self.logger.error(
                    f"Channel {self.config.channel_id} not found in guild {guild.name}"
                )
                # List available channels for debugging
                available_channels = [
                    f"{ch.name} (ID: {ch.id})" for ch in guild.voice_channels
                ]
                self.logger.info(f"Available voice channels: {available_channels}")
                return False

            self.logger.info(
                f"Found channel: {channel.name} (type: {type(channel).__name__})"
            )

            # Connect to voice channel
            self.logger.info("Attempting to connect to voice channel...")
            self.bot_instance.voice_client = await channel.connect(
                cls=voice_recv.VoiceRecvClient
            )
            self.logger.info("Voice client connected successfully")

            # Self-deafen to prevent hearing other audio, but don't self-mute (we need to play audio)
            await self.bot_instance.voice_client.guild.change_voice_state(
                channel=channel,
                self_deaf=True,  # Don't hear other audio in the channel
                self_mute=False,  # We need to play audio, so don't mute
            )

            # Setup audio buffer and source
            self.audio_handlers.setup_audio()

            # Start playing audio
            self.logger.info("Starting audio playback...")
            self.logger.info(
                f"Voice client state: {self.bot_instance.voice_client.is_connected()}"
            )
            self.logger.info(
                f"Audio source type: {type(self.audio_handlers.audio_source)}"
            )
            self.logger.info(
                f"Audio source is_opus: {self.audio_handlers.audio_source.is_opus()}"
            )

            # Start the audio playback
            success = self.audio_handlers.start_audio_playback(
                self.bot_instance.voice_client
            )
            if not success:
                return False

            # Wait a moment and check again
            await asyncio.sleep(0.1)
            self.logger.info(
                f"Voice client is_playing after delay: {self.bot_instance.voice_client.is_playing()}"
            )

            self.logger.info(
                f"Connected to listener channel: {channel.name} (ready to play audio)"
            )
            return True

        except Exception as e:
            self.logger.error(
                f"Failed to connect to listener channel: {e}", exc_info=True
            )
            return False
