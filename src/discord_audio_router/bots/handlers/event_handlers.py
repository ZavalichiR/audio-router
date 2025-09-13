"""
Event handlers for the main Discord bot.

This module contains all Discord event handlers separated from the main bot file
for better organization and maintainability.
"""

import logging
from typing import Optional, Any

import discord
from discord.ext import commands

from discord_audio_router.bots.utils.embed_builder import EmbedBuilder
from discord_audio_router.core.audio_router import AudioRouter
from discord_audio_router.subscription.subscription_manager import SubscriptionManager


class EventHandlers:
    """Handles all Discord bot events."""

    def __init__(
        self,
        bot: Any,
        audio_router: Optional[AudioRouter] = None,
        subscription_manager: Optional[SubscriptionManager] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize event handlers."""
        self.bot_instance = bot  # This is the AudioRouterBot instance
        self.bot = bot.bot  # This is the actual Discord bot
        self.audio_router = audio_router
        self.subscription_manager = subscription_manager
        self.logger = logger

    async def on_ready(self) -> None:
        """Bot ready event."""
        self.logger.info(f"AudioBroadcast Bot online: {self.bot.user}")

        try:
            config = self.bot_instance.config

            # Initialize subscription manager
            try:
                self.subscription_manager = SubscriptionManager(
                    bot_token=config.audio_broadcast_token
                )
            except Exception as e:
                self.logger.error(
                    f"Failed to initialize subscription manager: {e}", exc_info=True
                )

            # Initialize audio router
            try:
                self.audio_router = AudioRouter(config)
                await self.audio_router.initialize(self.bot)
            except Exception as e:
                self.logger.error(
                    f"Failed to initialize audio router: {e}", exc_info=True
                )

            # Update bot components
            self.bot_instance.update_components(
                audio_router=self.audio_router,
                subscription_manager=self.subscription_manager,
            )

            # Sync commands
            try:
                await self.bot.tree.sync()
            except Exception as e:
                self.logger.error(f"Command sync failed: {e}", exc_info=True)

        except Exception as e:
            self.logger.error(f"Error in on_ready: {e}", exc_info=True)

    async def on_message(self, message: discord.Message) -> None:
        """Message event handler."""
        if not message.author.bot:
            await self.bot.process_commands(message)

    async def on_command_error(self, ctx: commands.Context, error: Exception) -> None:
        """Command error handler."""
        try:
            if isinstance(error, commands.CheckFailure):
                embed = EmbedBuilder.no_permission()
                await ctx.send(embed=embed)
            else:
                embed = EmbedBuilder.command_error(str(error))
                await ctx.send(embed=embed)
                self.logger.error(
                    f"Command error in {getattr(ctx, 'command', None)}: {error}"
                )
        except discord.NotFound:
            self.logger.error(
                f"Command error in {getattr(ctx, 'command', None)}: {error} (channel was deleted)"
            )
        except Exception as send_error:
            self.logger.error(
                f"Command error in {getattr(ctx, 'command', None)}: {error}"
            )
            self.logger.error(f"Failed to send error message: {send_error}")

    def get_audio_router(self) -> Optional[object]:
        """Get the current audio router instance."""
        return self.audio_router

    def get_subscription_manager(self) -> Optional[object]:
        """Get the current subscription manager instance."""
        return self.subscription_manager
