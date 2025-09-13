"""Event handlers for the Audio Receiver Bot."""

import asyncio
import logging
from typing import Any

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
                self.logger.info(
                    f"AudioReceiver bot ready: {self.bot.user} (ID: {self.config.bot_id})"
                )
                # Ensure the bot has the correct role and connect websockets
                await self._ensure_listener_role()
                await self.websocket_handlers.connect()

                # Connect to the listener channel
                await asyncio.sleep(1)
                await self.connect_to_channel()

        @self.bot.event
        async def on_resumed():
            self.logger.info("Session resumed—reconnecting voice if needed")
            await self.connect_to_channel()

        @self.bot.event
        async def on_voice_state_update(member, before, after):
            # Only look at our bot in the right guild
            if member.id != self.bot.user.id or member.guild.id != self.config.guild_id:
                return

            # Disconnected
            if before.channel and not after.channel:
                self.logger.warning("Bot was disconnected from voice channel")
                await self.connect_to_channel()

            # Moved out or to wrong channel
            elif after.channel and after.channel.id != self.config.channel_id:
                self.logger.warning(f"Bot moved to wrong channel: {after.channel.name}")
                await self.connect_to_channel()

    async def _ensure_listener_role(self) -> None:
        """Ensure the AudioReceiver bot has the Listener role to join listener channels."""
        try:
            guild = self.bot.get_guild(self.config.guild_id)
            if not guild:
                self.logger.warning(
                    f"Guild {self.config.guild_id} not in cache, fetching..."
                )
                guild = await self.bot.fetch_guild(self.config.guild_id)
                self.logger.info(f"Fetched guild: {guild.name}")

            bot_member = guild.get_member(self.bot.user.id)
            if not bot_member:
                self.logger.error(f"Bot member not found in guild {guild.name}")
                return

            listener_role = discord.utils.get(guild.roles, name="Listener")
            if not listener_role:
                self.logger.warning("Listener role not found in guild roles")
                return

            if listener_role in bot_member.roles:
                self.logger.info("Bot already has Listener role")
                return

            try:
                await bot_member.add_roles(
                    listener_role,
                    reason="AudioReceiver bot needs Listener role",
                )
                self.logger.info("Added Listener role to bot")
            except discord.Forbidden:
                self.logger.warning("Insufficient permissions to add Listener role")
            except Exception as e:
                self.logger.error(f"Error adding role: {e}", exc_info=True)
        except Exception as e:
            self.logger.error(f"Error in _ensure_listener_role: {e}", exc_info=True)

    async def connect_to_channel(self) -> bool:
        """Connect to the listener channel and start audio playback."""
        if self._connecting:
            self.logger.info("Connection attempt already in progress")
            return False
        self._connecting = True
        try:
            guild = self.bot.get_guild(self.config.guild_id)
            if not guild:
                guild = await self.bot.fetch_guild(self.config.guild_id)

            channel = guild.get_channel(self.config.channel_id)
            if not channel:
                self.logger.error(f"Channel {self.config.channel_id} not found")
                return False

            # Debug: verify channel type and bot permissions
            self.logger.info(
                f"About to connect to channel {channel.name} ({channel.id}): "
                f"type={type(channel).__name__}, kind={channel.type}"
            )
            perms = channel.permissions_for(channel.guild.me)
            self.logger.info(
                f"Bot permissions in channel: connect={perms.connect}, "
                f"speak={perms.speak}, view_channel={perms.view_channel}"
            )

            voice_client = guild.voice_client
            if (
                voice_client
                and voice_client.is_connected()
                and voice_client.channel.id == self.config.channel_id
            ):
                self.logger.info("Already connected to target voice channel")
            else:
                if voice_client:
                    await voice_client.disconnect()

                # Give Discord a moment to propagate channel/permission changes
                await asyncio.sleep(1)

                try:
                    voice_client = await channel.connect(
                        cls=voice_recv.VoiceRecvClient,
                        timeout=30.0,
                    )
                except discord.errors.ConnectionClosed as e:
                    if e.code == 4006:
                        self.logger.warning("Voice session invalidated, retrying...")
                        await asyncio.sleep(5)
                        voice_client = await channel.connect(
                            cls=voice_recv.VoiceRecvClient,
                            timeout=30.0,
                        )
                    else:
                        raise

                await asyncio.sleep(1)
                if not voice_client.is_connected():
                    raise Exception("Failed to connect voice client")

                # Self-deafen to prevent hearing other audio, but don't self-mute (we need to play audio)
                await guild.change_voice_state(
                    channel=channel,
                    self_deaf=True,  # Don't hear other audio in the channel
                    self_mute=False,  # We need to play audio, so don't mute
                )

                self.logger.info("Voice client connected and self-deafened")

            # Setup audio buffer and source
            self.audio_handlers.setup_audio()

            # Start playing audio
            self.logger.info("Starting audio playback...")
            success = self.audio_handlers.start_audio_playback(guild.voice_client)
            if not success:
                self.logger.error("Failed to start audio playback")
                return False

            self.logger.info(
                f"Connected to listener channel: {channel.name} (ready to play audio)"
            )
            return True

        except Exception as e:
            self.logger.error(f"connect_to_channel error: {e}", exc_info=True)
            return False
        finally:
            self._connecting = False
