"""
Audio Router for managing audio flow between channels.

This module handles the coordination of audio routing between speaker
and listener channels using the bot manager.
"""

from typing import Any, Dict, Optional

import discord
from discord.ext import commands

from discord_audio_router.infrastructure import setup_logging

from .access_control import AccessControl
from .bot_manager import BotManager
from .section_manager import SectionManager

logger = setup_logging(
    component_name="audio_router",
    log_file="logs/audio_router.log",
)


class AudioRouter:
    """
    Main audio router that coordinates audio flow between channels.

    This class manages the overall audio routing system, including
    section management and bot coordination.
    """

    def __init__(self, config):
        """
        Initialize the audio router.

        Args:
            config: Bot configuration
        """
        self.config = config
        self.bot_manager = BotManager(config)
        self.access_control = AccessControl(config)
        self.section_manager = SectionManager(
            self.bot_manager, self.access_control
        )

        # Main bot instance
        self.main_bot: Optional[commands.Bot] = None

    async def initialize(self, main_bot: commands.Bot):
        """
        Initialize the audio router with the main bot.

        Args:
            main_bot: Main Discord bot instance
        """
        self.main_bot = main_bot

        # Add available AudioReceiver bot tokens (required)
        if (
            hasattr(self.config, "audio_receiver_tokens")
            and self.config.audio_receiver_tokens
        ):
            self.bot_manager.add_available_tokens(
                self.config.audio_receiver_tokens
            )
            logger.info(
                f"Added {len(self.config.audio_receiver_tokens)} AudioReceiver bot tokens"
            )
        else:
            logger.error(
                "No AudioReceiver bot tokens configured - system cannot function without them"
            )
            raise ValueError(
                "AudioReceiver bot tokens are required. Configure AUDIO_RECEIVER_TOKENS in your .env file."
            )

        logger.info(
            "Using bot manager for true multi-channel audio"
        )

        logger.info("Audio router initialized")

    async def create_broadcast_section(
        self, guild: discord.Guild, section_name: str, listener_count: int, role_name: str = None
    ) -> Dict[str, Any]:
        """
        Create a broadcast section.

        Args:
            guild: Discord guild
            section_name: Name of the section
            listener_count: Number of listener channels
            role_name: Optional role name for category visibility restriction

        Returns:
            Dict with creation results
        """
        return await self.section_manager.create_broadcast_section(
            guild, section_name, listener_count, role_name=role_name
        )

    async def start_broadcast(self, guild: discord.Guild) -> Dict[str, Any]:
        """
        Start audio broadcasting for a section.

        Args:
            guild: Discord guild

        Returns:
            Dict with start results
        """
        return await self.section_manager.start_broadcast(guild)

    async def stop_broadcast(self, guild: discord.Guild) -> Dict[str, Any]:
        """
        Stop audio broadcasting for a section.

        Args:
            guild: Discord guild

        Returns:
            Dict with stop results
        """
        return await self.section_manager.stop_broadcast(guild)

    async def cleanup_section(self, guild: discord.Guild) -> Dict[str, Any]:
        """
        Clean up a broadcast section.

        Args:
            guild: Discord guild

        Returns:
            Dict with cleanup results
        """
        return await self.section_manager.cleanup_section(guild)

    async def get_section_status(self, guild: discord.Guild) -> Dict[str, Any]:
        """
        Get the status of a broadcast section.

        Args:
            guild: Discord guild

        Returns:
            Dict with status information
        """
        return await self.section_manager.get_section_status(guild)

    async def get_system_status(self) -> Dict[str, Any]:
        """
        Get the overall system status.

        Returns:
            Dict with system status information
        """
        return {
            "active_sections": len(self.section_manager.active_sections),
            "bot_status": self.bot_manager.get_status(),
            "available_tokens": len(self.bot_manager.available_tokens),
            "used_tokens": len(self.bot_manager.used_tokens),
        }
