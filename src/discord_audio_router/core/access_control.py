"""
Simplified Access Control System for Discord Audio Router Bot.

This module provides a clean role-based access control system:
- Speaker role: Required to join speaker channels
- Listener role: Required to join listener channels
- Broadcast Admin role: Required to use bot commands
"""

import logging
from typing import Optional

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class AccessControl:
    """
    Simplified access control system for broadcast sections.

    This class handles:
    - Speaker role management (who can join speaker channels)
    - Listener role management (who can join listener channels)
    - Broadcast admin role management (who can use bot commands)
    - Automatic role creation (but not assignment)
    """

    def __init__(self, config):
        """
        Initialize access control system.

        Args:
            config: Bot configuration containing access control settings
        """
        self.config = config

        # Role names (configurable)
        self.speaker_role_name = getattr(
            config, "speaker_role_name", "Speaker"
        )
        self.listener_role_name = getattr(
            config, "listener_role_name", "Listener"
        )
        self.broadcast_admin_role_name = getattr(
            config, "broadcast_admin_role_name", "Broadcast Admin"
        )

        # Auto-create roles if they don't exist
        self.auto_create_roles = getattr(config, "auto_create_roles", True)

        logger.info(
            f"Access control initialized - Speaker: '{self.speaker_role_name}', Listener: '{self.listener_role_name}', Admin: '{self.broadcast_admin_role_name}'"
        )

    def is_broadcast_admin(self, member: discord.Member) -> bool:
        """
        Check if a member is authorized to use bot commands.

        Args:
            member: Discord member to check

        Returns:
            True if member is authorized, False otherwise
        """
        # Check if user has administrator permissions (always allowed)
        if member.guild_permissions.administrator:
            return True

        # Check if user has the broadcast admin role
        member_role_names = {role.name for role in member.roles}
        if self.broadcast_admin_role_name in member_role_names:
            return True

        return False

    def has_speaker_role(self, member: discord.Member) -> bool:
        """
        Check if a member has the speaker role.

        Args:
            member: Discord member to check

        Returns:
            True if member has speaker role, False otherwise
        """
        member_role_names = {role.name for role in member.roles}
        return self.speaker_role_name in member_role_names

    def has_listener_role(self, member: discord.Member) -> bool:
        """
        Check if a member has the listener role.

        Args:
            member: Discord member to check

        Returns:
            True if member has listener role, False otherwise
        """
        member_role_names = {role.name for role in member.roles}
        return self.listener_role_name in member_role_names

    async def ensure_roles_exist(self, guild: discord.Guild) -> dict:
        """
        Ensure that required roles exist in the guild.
        Creates roles if they don't exist but doesn't assign them to anyone.

        Args:
            guild: Discord guild

        Returns:
            Dict with role information: {'speaker_role': role, 'listener_role': role, 'broadcast_admin_role': role}
        """
        if not self.auto_create_roles:
            return {"speaker_role": None, "listener_role": None, "broadcast_admin_role": None}

        result = {"speaker_role": None, "listener_role": None, "broadcast_admin_role": None}

        try:
            # Check if bot has necessary permissions
            bot_member = guild.me
            if not bot_member.guild_permissions.manage_roles:
                logger.warning(
                    f"Bot lacks 'Manage Roles' permission in {guild.name}"
                )
                return result

            # Ensure speaker role exists
            speaker_role = discord.utils.get(
                guild.roles, name=self.speaker_role_name
            )
            if not speaker_role:
                try:
                    speaker_role = await guild.create_role(
                        name=self.speaker_role_name,
                        color=discord.Color.green(),
                        reason="Created for speaker channel access",
                    )
                    logger.info(
                        f"Created speaker role: {self.speaker_role_name}"
                    )
                except Exception as e:
                    logger.error(f"Failed to create speaker role: {e}", exc_info=True)
            else:
                logger.info(
                    f"Speaker role '{self.speaker_role_name}' already exists"
                )
            result["speaker_role"] = speaker_role

            # Give the bot the speaker role so it can join speaker channels
            if speaker_role and bot_member:
                try:
                    if speaker_role not in bot_member.roles:
                        await bot_member.add_roles(
                            speaker_role,
                            reason="Bot needs speaker role to join speaker channels",
                        )
                        logger.info(
                            f"Added speaker role to bot: {self.speaker_role_name}"
                        )
                    else:
                        logger.info(
                            f"Bot already has speaker role: {self.speaker_role_name}"
                        )
                except Exception as e:
                    logger.warning(f"Could not add speaker role to bot: {e}")

            # Ensure listener role exists
            listener_role = discord.utils.get(
                guild.roles, name=self.listener_role_name
            )
            if not listener_role:
                try:
                    listener_role = await guild.create_role(
                        name=self.listener_role_name,
                        color=discord.Color.blue(),
                        reason="Created for listener channel access",
                    )
                    logger.info(
                        f"Created listener role: {self.listener_role_name}"
                    )
                except Exception as e:
                    logger.error(f"Failed to create listener role: {e}", exc_info=True)
            else:
                logger.info(
                    f"Listener role '{self.listener_role_name}' already exists"
                )
            result["listener_role"] = listener_role

            # Give the bot the listener role so it can join listener channels
            if listener_role and bot_member:
                try:
                    if listener_role not in bot_member.roles:
                        await bot_member.add_roles(
                            listener_role,
                            reason="Bot needs listener role to join listener channels",
                        )
                        logger.info(
                            f"Added listener role to bot: {self.listener_role_name}"
                        )
                    else:
                        logger.info(
                            f"Bot already has listener role: {self.listener_role_name}"
                        )
                except Exception as e:
                    logger.warning(f"Could not add listener role to bot: {e}")

            # Ensure broadcast admin role exists
            admin_role = discord.utils.get(
                guild.roles, name=self.broadcast_admin_role_name
            )
            if not admin_role:
                try:
                    admin_role = await guild.create_role(
                        name=self.broadcast_admin_role_name,
                        color=discord.Color.red(),
                        reason="Created for broadcast control access",
                    )
                    logger.info(
                        f"Created broadcast admin role: {self.broadcast_admin_role_name}"
                    )
                except Exception as e:
                    logger.error(f"Failed to create broadcast admin role: {e}", exc_info=True)
            else:
                logger.info(
                    f"Broadcast admin role '{self.broadcast_admin_role_name}' already exists"
                )
            result["broadcast_admin_role"] = admin_role

        except Exception as e:
            logger.error(f"Error ensuring roles exist: {e}", exc_info=True)

        return result

    async def setup_voice_channel_permissions(
        self,
        speaker_channel: discord.VoiceChannel,
        listener_channels: list[discord.VoiceChannel],
        broadcast_admin_role: Optional[discord.Role] = None,
        speaker_role: Optional[discord.Role] = None,
        listener_role: Optional[discord.Role] = None,
    ) -> bool:
        """
        Set up voice channel permissions for speaker and listener channels.

        Args:
            speaker_channel: Speaker voice channel (restricted to speaker role)
            listener_channels: List of listener voice channels (restricted to listener role)
            broadcast_admin_role: Role for broadcast admins
            speaker_role: Role for speakers
            listener_role: Role for listeners

        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if bot has necessary permissions
            bot_member = speaker_channel.guild.me
            if not bot_member.guild_permissions.manage_channels:
                logger.warning(
                    f"Bot lacks 'Manage Channels' permission in {speaker_channel.guild.name}"
                )
                return False

            # Set up speaker channel permissions (restricted to speaker role)
            if speaker_role:
                try:
                    # Deny access to @everyone
                    await speaker_channel.set_permissions(
                        speaker_channel.guild.default_role,
                        connect=False,
                        view_channel=True,  # Allow viewing but not connecting
                    )

                    # Allow speaker role to connect
                    await speaker_channel.set_permissions(
                        speaker_role,
                        connect=True,
                        speak=True,
                        view_channel=True,
                    )

                    # Allow broadcast admin role to connect (for management)
                    if broadcast_admin_role:
                        await speaker_channel.set_permissions(
                            broadcast_admin_role,
                            connect=True,
                            speak=True,
                            view_channel=True,
                        )

                    logger.info(
                        f"Set speaker channel permissions for: {speaker_channel.name}"
                    )
                except discord.Forbidden as e:
                    logger.warning(
                        f"Cannot set speaker channel permissions: {e}"
                    )

            # Set up listener channel permissions (restricted to listener role)
            for listener_channel in listener_channels:
                try:
                    if listener_role:
                        # Deny access to @everyone
                        await listener_channel.set_permissions(
                            listener_channel.guild.default_role,
                            connect=False,
                            view_channel=True,  # Allow viewing but not connecting
                        )

                        # Allow listener role to connect
                        await listener_channel.set_permissions(
                            listener_role,
                            connect=True,
                            speak=True,  # Listeners can speak in their channels
                            view_channel=True,
                        )

                        # Allow broadcast admin role to connect (for management)
                        if broadcast_admin_role:
                            await listener_channel.set_permissions(
                                broadcast_admin_role,
                                connect=True,
                                speak=True,
                                view_channel=True,
                            )

                    logger.info(
                        f"Set listener channel permissions for: {listener_channel.name}"
                    )
                except discord.Forbidden as e:
                    logger.warning(
                        f"Cannot set listener channel permissions: {e}"
                    )

            return True

        except Exception as e:
            logger.error(f"Failed to set up voice channel permissions: {e}", exc_info=True)
            return False


def is_broadcast_admin(role_name: str = "Broadcast Admin"):
    """
    Decorator to check if user is authorized to use bot commands.

    Allows users with:
    - Administrator permission
    - Broadcast Admin role (or specified role name)

    Args:
        role_name: Name of the broadcast admin role (defaults to "Broadcast Admin")
    """

    def predicate(ctx):
        # Check if user has administrator permissions (always allowed)
        if ctx.author.guild_permissions.administrator:
            return True

        # Check if user has the broadcast admin role
        member_role_names = {role.name for role in ctx.author.roles}
        return role_name in member_role_names

    return commands.check(predicate)
