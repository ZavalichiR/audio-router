"""
Access Control System for Discord Audio Router Bot.

This module provides role-based access control for managing who can
start broadcasts and access private control channels.
"""

import logging
from typing import List, Optional, Set

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class AccessControl:
    """
    Manages access control for broadcast sections.

    This class handles role-based permissions for:
    - Who can start/stop broadcasts
    - Who can access private control channels
    - Who can manage broadcast sections
    """

    def __init__(self, config):
        """
        Initialize access control system.

        Args:
            config: Bot configuration containing access control settings
        """
        self.config = config

        # Default authorized roles (can be configured via environment)
        self.authorized_roles: Set[str] = set()
        self.authorized_users: Set[int] = set()

        # Load configuration
        self._load_access_config()

    def _load_access_config(self):
        """Load access control configuration from environment."""
        import os

        # Load authorized roles
        roles_env = os.getenv("AUTHORIZED_ROLES", "")
        if roles_env:
            self.authorized_roles = set(
                role.strip() for role in roles_env.split(",") if role.strip()
            )

        # Load authorized user IDs
        users_env = os.getenv("AUTHORIZED_USERS", "")
        if users_env:
            self.authorized_users = set(
                int(user_id.strip())
                for user_id in users_env.split(",")
                if user_id.strip()
            )

        logger.info(
            f"Loaded access control: {len(self.authorized_roles)} roles, {len(self.authorized_users)} users"
        )

    def is_authorized(self, member: discord.Member) -> bool:
        """
        Check if a member is authorized to control broadcasts.

        Args:
            member: Discord member to check

        Returns:
            True if member is authorized, False otherwise
        """
        # Check if user has administrator permissions
        if member.guild_permissions.administrator:
            return True

        # Check if user ID is in authorized users list
        if member.id in self.authorized_users:
            return True

        # Check if user has any authorized roles
        member_role_names = {role.name for role in member.roles}
        if self.authorized_roles.intersection(member_role_names):
            return True

        return False

    def get_authorized_members(self, guild: discord.Guild) -> List[discord.Member]:
        """
        Get all authorized members in a guild.

        Args:
            guild: Discord guild to check

        Returns:
            List of authorized members
        """
        authorized = []

        for member in guild.members:
            if self.is_authorized(member):
                authorized.append(member)

        return authorized

    async def create_authorized_role(
        self, guild: discord.Guild, role_name: str = "Broadcast Controller"
    ) -> Optional[discord.Role]:
        """
        Create an authorized role for broadcast control.

        Args:
            guild: Discord guild
            role_name: Name for the new role

        Returns:
            Created role or None if failed
        """
        try:
            # Check if role already exists
            existing_role = discord.utils.get(guild.roles, name=role_name)
            if existing_role:
                logger.info(f"Role '{role_name}' already exists")
                return existing_role

            # Create new role
            role = await guild.create_role(
                name=role_name,
                color=discord.Color.blue(),
                reason="Created for broadcast control access",
            )

            logger.info(f"Created authorized role: {role_name}")
            return role

        except Exception as e:
            logger.error(f"Failed to create authorized role: {e}")
            return None

    async def setup_private_channel_permissions(
        self,
        channel: discord.TextChannel,
        authorized_role: Optional[discord.Role] = None,
    ) -> bool:
        """
        Set up private channel permissions for authorized users only.

        Args:
            channel: Channel to set permissions for
            authorized_role: Role to give access (optional)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if bot has necessary permissions
            bot_member = channel.guild.me
            if not bot_member.guild_permissions.manage_channels:
                logger.warning(
                    f"Bot lacks 'Manage Channels' permission in {channel.guild.name}"
                )
                return False

            # Deny access to @everyone (this should always work)
            try:
                await channel.set_permissions(
                    channel.guild.default_role, read_messages=False, send_messages=False
                )
            except discord.Forbidden:
                logger.warning(
                    f"Cannot modify @everyone permissions for {channel.name}"
                )
                return False

            # Give bot full access (this should always work)
            try:
                await channel.set_permissions(
                    bot_member,
                    read_messages=True,
                    send_messages=True,
                    manage_messages=True,
                    embed_links=True,
                )
            except discord.Forbidden:
                logger.warning(f"Cannot set bot permissions for {channel.name}")
                return False

            # If authorized role provided, give it access (only if bot can modify it)
            if authorized_role:
                try:
                    # Check if bot's role is higher than the target role
                    if bot_member.top_role > authorized_role:
                        await channel.set_permissions(
                            authorized_role,
                            read_messages=True,
                            send_messages=True,
                            embed_links=True,
                        )
                        logger.info(f"Set permissions for role: {authorized_role.name}")
                    else:
                        logger.warning(
                            f"Cannot modify role {authorized_role.name} - bot role too low"
                        )
                except discord.Forbidden:
                    logger.warning(
                        f"Cannot set permissions for role: {authorized_role.name}"
                    )

            # Give access to all authorized members (only if bot can modify them)
            authorized_members = self.get_authorized_members(channel.guild)
            for member in authorized_members:
                try:
                    # Check if bot's role is higher than the member's top role
                    if bot_member.top_role > member.top_role:
                        await channel.set_permissions(
                            member,
                            read_messages=True,
                            send_messages=True,
                            embed_links=True,
                        )
                        logger.info(
                            f"Set permissions for member: {member.display_name}"
                        )
                    else:
                        logger.warning(
                            f"Cannot modify permissions for {member.display_name} - bot role too low"
                        )
                except discord.Forbidden:
                    logger.warning(
                        f"Cannot set permissions for member: {member.display_name}"
                    )

            logger.info(f"Set up private permissions for channel: {channel.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to set up private channel permissions: {e}")
            return False


def is_broadcast_authorized():
    """
    Decorator to check if user is authorized to control broadcasts.

    This replaces the simple is_admin() check with role-based access control.
    """

    def predicate(ctx):
        # Import here to avoid circular imports
        from main_bot import audio_router

        if not audio_router or not hasattr(audio_router, "access_control"):
            # Fallback to admin check if access control not available
            return ctx.author.guild_permissions.administrator

        return audio_router.access_control.is_authorized(ctx.author)

    return commands.check(predicate)


def is_admin_or_authorized():
    """
    Decorator that allows both administrators and authorized users.

    This provides backward compatibility while adding role-based access.
    """

    def predicate(ctx):
        # Check admin permissions first (backward compatibility)
        if ctx.author.guild_permissions.administrator:
            return True

        # Import here to avoid circular imports
        from main_bot import audio_router

        if not audio_router or not hasattr(audio_router, "access_control"):
            return False

        return audio_router.access_control.is_authorized(ctx.author)

    return commands.check(predicate)
