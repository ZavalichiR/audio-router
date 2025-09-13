"""
Base command handler class for Discord bot commands.

This module provides a base class that all command handlers can inherit from,
providing common functionality and utilities.
"""

import logging
from typing import Optional

import discord
from discord.ext import commands

from discord_audio_router.config.settings import SimpleConfig
from discord_audio_router.core import AudioRouter
from discord_audio_router.subscription import SubscriptionManager
from discord_audio_router.bots.utils.embed_builder import EmbedBuilder


class BaseCommandHandler:
    """Base class for command handlers with common functionality."""

    def __init__(
        self,
        audio_router: Optional[AudioRouter] = None,
        subscription_manager: Optional[SubscriptionManager] = None,
        logger: Optional[logging.Logger] = None,
        config: Optional[SimpleConfig] = None,
    ):
        """Initialize the base command handler."""
        self.audio_router = audio_router
        self.subscription_manager = subscription_manager
        self.logger = logger
        self.config = config

    async def _send_system_starting_embed(self, ctx: commands.Context) -> None:
        """Send embed when system is still starting up."""
        embed = EmbedBuilder.warning(
            "System Starting Up",
            "The audio router is still initializing. Please wait a moment and try again.\n\nIf this persists, contact the bot administrator.",
        )
        await ctx.send(embed=embed)

    async def _send_loading_embed(
        self, ctx: commands.Context, description: str
    ) -> discord.Message:
        """Send a loading embed and return the message."""
        embed = EmbedBuilder.info("Creating broadcast section...", description)
        return await ctx.send(embed=embed)

    async def _update_loading_embed(
        self, message: discord.Message, title: str, description: str
    ) -> None:
        """Update a loading message with new content."""
        embed = EmbedBuilder.info(title, description)
        await message.edit(embed=embed)

    async def _send_error_embed(
        self, message: discord.Message, title: str, description: str
    ) -> None:
        """Send an error embed by editing a message."""
        embed = EmbedBuilder.error(title, description)
        await message.edit(embed=embed)

    async def _handle_command_error(
        self, ctx: commands.Context, error: Exception, command_name: str
    ) -> None:
        """Handle command errors with appropriate logging and user feedback."""
        self.logger.error(f"Error in {command_name} command: {error}", exc_info=True)
        embed = EmbedBuilder.error(
            "Something Went Wrong",
            f"An unexpected error occurred. Please try again or contact the bot administrator if the issue persists.\n\n**Error:** {str(error)}",
        )
        try:
            await ctx.send(embed=embed)
        except discord.NotFound:
            self.logger.warning(
                f"Could not send error message for {command_name} - channel may have been deleted"
            )
        except Exception as send_error:
            self.logger.warning(
                f"Could not send error message for {command_name}: {send_error}"
            )

    async def _get_available_receiver_bots_count(self, guild: discord.Guild) -> int:
        """
        Count the number of AudioReceiver bots present in the Discord server.
        """
        try:
            members = [member async for member in guild.fetch_members(limit=None)]
            receiver_bot_count = sum(
                1
                for member in members
                if member.bot and member.display_name.startswith("Rcv-")
            )
            self.logger.info(
                f"Found {receiver_bot_count} AudioReceiver bots in server '{guild.name}'"
            )
            return receiver_bot_count
        except Exception as e:
            self.logger.error(
                f"Error counting AudioReceiver bots in guild {guild.id}: {e}",
                exc_info=True,
            )
            return 0
