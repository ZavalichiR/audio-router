"""
Permission and role management utilities for the Discord bot.

This module provides utilities for checking permissions, managing roles,
and handling access control for the audio router system.
"""

from typing import Optional
import logging
import discord
from discord.ext import commands

from discord_audio_router.core import is_broadcast_admin
from discord_audio_router.core.audio_router import AudioRouter


class PermissionUtils:
    """Utilities for permission and role management."""

    @staticmethod
    def is_admin() -> callable:
        """Decorator: Check if user has administrator permissions."""

        def predicate(ctx: commands.Context) -> bool:
            return ctx.author.guild_permissions.administrator

        return commands.check(predicate)

    @staticmethod
    def get_broadcast_admin_decorator(audio_router: Optional[AudioRouter] = None):
        """Get the broadcast admin decorator with the correct role name."""
        role_name = (
            audio_router.access_control.broadcast_admin_role_name
            if audio_router and hasattr(audio_router, "access_control")
            else "Broadcast Admin"
        )
        return is_broadcast_admin(role_name)

    @staticmethod
    async def get_available_receiver_bots_count(
        guild: discord.Guild, logger: Optional[logging.Logger] = None
    ) -> int:
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
            if logger:
                logger.info(
                    f"Found {receiver_bot_count} AudioReceiver bots in server '{guild.name}'"
                )
            return receiver_bot_count
        except Exception as e:
            if logger:
                logger.error(
                    f"Error counting AudioReceiver bots in guild {guild.id}: {e}",
                    exc_info=True,
                )
            return 0

    @staticmethod
    def check_bot_permissions(guild: discord.Guild) -> dict:
        """Check bot permissions in a guild."""
        bot_member = guild.me
        perms = bot_member.guild_permissions

        return {
            "administrator": perms.administrator,
            "manage_channels": perms.manage_channels,
            "manage_roles": perms.manage_roles,
            "connect": perms.connect,
            "speak": perms.speak,
            "send_messages": perms.send_messages,
            "read_message_history": perms.read_message_history,
            "embed_links": perms.embed_links,
        }

    @staticmethod
    def check_required_roles(guild: discord.Guild) -> dict:
        """Check if required roles exist in a guild."""
        speaker_role = discord.utils.get(guild.roles, name="Speaker")
        broadcast_admin_role = discord.utils.get(guild.roles, name="Broadcast Admin")

        return {
            "speaker_role": speaker_role,
            "broadcast_admin_role": broadcast_admin_role,
            "speaker_members": len(
                [m for m in guild.members if speaker_role in m.roles]
            )
            if speaker_role
            else 0,
            "admin_members": len(
                [m for m in guild.members if broadcast_admin_role in m.roles]
            )
            if broadcast_admin_role
            else 0,
        }

    @staticmethod
    def can_manage_role(bot_member: discord.Member, role: discord.Role) -> bool:
        """Check if bot can manage a specific role."""
        return bot_member.top_role > role

    @staticmethod
    def get_role_hierarchy_info(guild: discord.Guild) -> dict:
        """Get information about role hierarchy."""
        bot_member = guild.me
        bot_role = bot_member.top_role

        return {
            "bot_role": bot_role,
            "bot_position": bot_role.position,
            "total_roles": len(guild.roles),
            "is_high_enough": bot_role.position >= 3,
        }
