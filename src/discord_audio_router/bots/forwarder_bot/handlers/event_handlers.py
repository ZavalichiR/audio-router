"""Event handlers for the Audio Forwarder Bot."""

import asyncio
import logging
from typing import Any

import discord
from discord.ext import commands

from discord_audio_router.audio import setup_audio_receiver
from discord_audio_router.bots.forwarder_bot.handlers.websocket_handlers import (
    WebSocketHandlers,
)
from discord_audio_router.bots.forwarder_bot.utils.config import BotConfig


class EventHandlers:
    """Handles Discord bot events for the Audio Forwarder Bot."""

    def __init__(
        self,
        bot: Any,
        websocket_handlers: WebSocketHandlers,
        config: BotConfig,
        logger: logging.Logger,
    ):
        """Initialize event handlers."""
        self.bot_instance = bot
        self.bot: commands.Bot = bot.bot
        self.websocket_handlers = websocket_handlers
        self.config = config
        self.logger = logger
        self._connecting = False

    def setup_events(self) -> None:
        """Setup bot event handlers."""

        @self.bot.event
        async def on_ready():
            self.logger.info(
                f"AudioForwarder bot {self.config.bot_id} ready: {self.bot.user}"
            )
            self.logger.info(
                f"Target channel: {self.config.channel_id}, Guild: {self.config.guild_id}"
            )

            # Ensure bot has Speaker role to join speaker channels
            await self._ensure_speaker_role()

            # Connect to centralized WebSocket server
            await self.websocket_handlers.connect()

            # Connect to the speaker channel
            await self.connect_to_channel()

        @self.bot.event
        async def on_connect():
            self.logger.info(
                f"AudioForwarder bot {self.config.bot_id} connected to Discord"
            )

        @self.bot.event
        async def on_disconnect():
            self.logger.warning(
                f"AudioForwarder bot {self.config.bot_id} disconnected from Discord"
            )

        @self.bot.event
        async def on_voice_state_update(member, before, after):
            """Handle voice state updates to prevent bot from leaving when users mute/unmute."""
            # Only care about voice state changes for our bot
            if member.id == self.bot.user.id:
                # Check if the bot was actually disconnected (moved to no channel)
                if before.channel and after.channel is None:
                    self.logger.warning("Bot was disconnected from voice channel!")
                    # Only reconnect if we're not already trying to connect
                    if not self._connecting:
                        await asyncio.sleep(2)
                        await self.connect_to_channel()
                # Check if the bot was moved to a different channel
                elif (
                    before.channel
                    and after.channel
                    and before.channel.id != after.channel.id
                ):
                    self.logger.warning(
                        f"Bot was moved from {before.channel.name} to {after.channel.name}"
                    )
                    # If moved away from our target channel, try to reconnect
                    if (
                        after.channel.id != self.config.channel_id
                        and not self._connecting
                    ):
                        await asyncio.sleep(2)
                        await self.connect_to_channel()
                # If bot just connected (before.channel is None, after.channel exists)
                elif not before.channel and after.channel:
                    self.logger.info(f"Bot connected to channel: {after.channel.name}")

    async def _ensure_speaker_role(self) -> None:
        """Ensure the AudioForwarder bot has the Speaker role to join speaker channels."""
        try:
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
                    return
                except Exception as e:
                    self.logger.error(f"Error fetching guild: {e}")
                    return

            bot_member = guild.get_member(self.bot.user.id)
            if not bot_member:
                self.logger.error(f"Bot member not found in guild {guild.name}")
                return

            # Look for the Speaker role
            speaker_role = discord.utils.get(guild.roles, name="Speaker")
            if not speaker_role:
                self.logger.warning(
                    "Speaker role not found - AudioForwarder bot may not be able to join speaker channels"
                )
                return

            # Check if bot already has the Speaker role
            if speaker_role in bot_member.roles:
                self.logger.info(
                    f"AudioForwarder bot already has Speaker role: {speaker_role.name}"
                )
                return

            # Try to add the Speaker role to the bot
            try:
                await bot_member.add_roles(
                    speaker_role,
                    reason="AudioForwarder bot needs Speaker role to join speaker channels",
                )
                self.logger.info(
                    f"Added Speaker role to AudioForwarder bot: {speaker_role.name}"
                )
            except discord.Forbidden:
                self.logger.warning(
                    "Cannot add Speaker role to AudioForwarder bot - insufficient permissions"
                )
            except Exception as e:
                self.logger.error(
                    f"Error adding Speaker role to AudioForwarder bot: {e}",
                    exc_info=True,
                )

        except Exception as e:
            self.logger.error(
                f"Error ensuring Speaker role for AudioForwarder bot: {e}",
                exc_info=True,
            )

    async def connect_to_channel(self) -> bool:
        """Connect to the speaker channel and start audio capture."""
        try:
            # Prevent multiple simultaneous connection attempts
            if self._connecting:
                self.logger.info("Connection already in progress, skipping...")
                return False

            self._connecting = True
            self.logger.info(
                f"Attempting to connect to voice channel {self.config.channel_id}"
            )

            try:
                # Check if already connected and working properly
                if (
                    self.bot_instance.voice_client
                    and self.bot_instance.voice_client.is_connected()
                ):
                    # Check if we're in the right channel
                    if (
                        hasattr(self.bot_instance.voice_client, "channel")
                        and self.bot_instance.voice_client.channel
                        and self.bot_instance.voice_client.channel.id
                        == self.config.channel_id
                    ):
                        self.logger.info("Already connected to correct voice channel")
                        return True
                    else:
                        self.logger.info("Connected to wrong channel, reconnecting...")
                        await self.bot_instance.voice_client.disconnect()
                        self.bot_instance.voice_client = None

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

                channel = guild.get_channel(self.config.channel_id)
                if not channel:
                    self.logger.error(f"Channel {self.config.channel_id} not found")
                    return False

                # Connect to voice channel
                try:
                    from discord.ext import voice_recv

                    self.bot_instance.voice_client = await channel.connect(
                        cls=voice_recv.VoiceRecvClient
                    )
                except Exception as connect_error:
                    if "Already connected to a voice channel" in str(connect_error):
                        self.logger.warning(
                            "Already connected to a voice channel, disconnecting first..."
                        )
                        # Try to disconnect from any existing connection
                        if hasattr(self.bot, "voice_clients"):
                            for vc in self.bot.voice_clients:
                                await vc.disconnect()
                        # Wait a moment and try again
                        await asyncio.sleep(1)
                        from discord.ext import voice_recv

                        self.bot_instance.voice_client = await channel.connect(
                            cls=voice_recv.VoiceRecvClient
                        )
                    else:
                        raise connect_error

                self.logger.info(
                    f"Voice client connected: {self.bot_instance.voice_client}"
                )

                # Self-deafen to prevent hearing our own audio (prevents feedback)
                await self.bot_instance.voice_client.guild.change_voice_state(
                    channel=channel,
                    self_deaf=True,
                    self_mute=False,  # We want to capture audio, so don't mute
                )
                self.logger.info("Voice state updated: self-deafened")

                # Setup audio capture with direct callback
                self.bot_instance.audio_sink = await setup_audio_receiver(
                    self.bot_instance.voice_client,
                    self.websocket_handlers.forward_audio,
                )

                self.logger.info(
                    f"Connected to speaker channel: {channel.name} (self-deafened)"
                )
                self.logger.info(
                    f"Audio sink setup complete: {self.bot_instance.audio_sink is not None}"
                )
                return True

            finally:
                # Always reset the connecting flag
                self._connecting = False

        except Exception as e:
            self.logger.error(
                f"Failed to connect to speaker channel: {e}", exc_info=True
            )
            self._connecting = False
            return False
