"""
Simplified Access Control System for Discord Audio Router Bot.

This module provides a clean role-based access control system:
- Speaker role: Required to join speaker channels
- Broadcast Admin role: Required to use bot commands
- Custom role: Optional role for category visibility
"""

from typing import Optional

import discord
from discord.ext import commands

from discord_audio_router.infrastructure import setup_logging

# Configure logging
logger = setup_logging(
    component_name="access_control",
    log_file="logs/access_control.log",
)

class AccessControl:
    """
    Simplified access control system for broadcast sections.

    Handles:
    - Speaker role management (who can join speaker channels)
    - Broadcast admin role management (who can use bot commands)
    - Custom role management (who can view the section)
    """

    def __init__(self, config):
        """
        Initialize access control system.

        Args:
            config: Bot configuration containing access control settings
        """
        self.config = config
        self.speaker_role_name = getattr(config, "speaker_role_name", "Speaker")
        self.broadcast_admin_role_name = getattr(config, "broadcast_admin_role_name", "Broadcast Admin")
        self.auto_create_roles = getattr(config, "auto_create_roles", True)

        logger.info(
            f"Access control initialized - Speaker: '{self.speaker_role_name}', "
            f"Admin: '{self.broadcast_admin_role_name}'"
        )

    async def ensure_roles_exist(self, guild: discord.Guild, custom_role_name: Optional[str] = None) -> dict:
        """
        Ensure that required roles exist in the guild.
        Creates roles if they don't exist but doesn't assign them to anyone.

        Args:
            guild: Discord guild
            custom_role_name: Optional custom role name for category visibility

        Returns:
            Dict with role information: {'speaker_role': role, 'listener_role': role, 'broadcast_admin_role': role, 'custom_role': role}
        """
        if not self.auto_create_roles:
            return {"speaker_role": None, "listener_role": None, "broadcast_admin_role": None, "custom_role": None}

        result = {"speaker_role": None, "listener_role": None, "broadcast_admin_role": None, "custom_role": None}

        try:
            if not guild.me.guild_permissions.manage_roles:
                logger.warning(f"Bot lacks 'Manage Roles' permission in {guild.name}")
                return result

            # Ensure speaker role exists
            speaker_role = discord.utils.get(guild.roles, name=self.speaker_role_name)
            if not speaker_role:
                try:
                    speaker_role = await guild.create_role(
                        name=self.speaker_role_name,
                        color=discord.Color.green(),
                        reason="Created for speaker channel access",
                    )
                    logger.info(f"Created speaker role: {self.speaker_role_name}")
                except discord.Forbidden:
                    logger.error("Bot lacks permissions to create speaker role")
                except Exception as e:
                    logger.error(f"Failed to create speaker role: {e}", exc_info=True)
            else:
                logger.info(f"Speaker role '{self.speaker_role_name}' already exists")
            result["speaker_role"] = speaker_role

            # Ensure bot has speaker role
            if speaker_role and guild.me:
                try:
                    if speaker_role not in guild.me.roles:
                        if speaker_role.position >= guild.me.top_role.position:
                            logger.warning(f"Cannot assign speaker role '{self.speaker_role_name}' (higher than bot's role)")
                        else:
                            await guild.me.add_roles(speaker_role, reason="Bot needs speaker role to join speaker channels")
                            logger.info(f"Added speaker role to bot: {self.speaker_role_name}")
                    else:
                        logger.info(f"Bot already has speaker role: {self.speaker_role_name}")
                except discord.Forbidden:
                    logger.warning("Bot lacks permissions to assign speaker role to itself")
                except Exception as e:
                    logger.warning(f"Could not add speaker role to bot: {e}")

            # Ensure listener role exists
            listener_role = discord.utils.get(guild.roles, name="Listener")
            if not listener_role:
                try:
                    listener_role = await guild.create_role(
                        name="Listener",
                        color=discord.Color.blue(),
                        reason="Created for listener channel access",
                    )
                    logger.info("Created listener role: Listener")
                except discord.Forbidden:
                    logger.error("Bot lacks permissions to create listener role")
                except Exception as e:
                    logger.error(f"Failed to create listener role: {e}", exc_info=True)
            else:
                logger.info("Listener role 'Listener' already exists")
            result["listener_role"] = listener_role

            # Ensure bot has listener role
            if listener_role and guild.me:
                try:
                    if listener_role not in guild.me.roles:
                        if listener_role.position >= guild.me.top_role.position:
                            logger.warning(f"Cannot assign listener role 'Listener' (higher than bot's role)")
                        else:
                            await guild.me.add_roles(listener_role, reason="Bot needs listener role to join listener channels")
                            logger.info("Added listener role to bot: Listener")
                    else:
                        logger.info("Bot already has listener role: Listener")
                except discord.Forbidden:
                    logger.warning("Bot lacks permissions to assign listener role to itself")
                except Exception as e:
                    logger.warning(f"Could not add listener role to bot: {e}")

            # Ensure broadcast admin role exists
            admin_role = discord.utils.get(guild.roles, name=self.broadcast_admin_role_name)
            if not admin_role:
                try:
                    admin_role = await guild.create_role(
                        name=self.broadcast_admin_role_name,
                        color=discord.Color.red(),
                        reason="Created for broadcast control access",
                    )
                    logger.info(f"Created broadcast admin role: {self.broadcast_admin_role_name}")
                except discord.Forbidden:
                    logger.error("Bot lacks permissions to create broadcast admin role")
                except Exception as e:
                    logger.error(f"Failed to create broadcast admin role: {e}", exc_info=True)
            else:
                logger.info(f"Broadcast admin role '{self.broadcast_admin_role_name}' already exists")
            result["broadcast_admin_role"] = admin_role

            if custom_role_name:
                custom_role = discord.utils.get(guild.roles, name=custom_role_name)
                result["custom_role"] = custom_role

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
        custom_role: Optional[discord.Role] = None,
    ) -> bool:
        """
        Set up voice channel permissions for speaker and listener channels.

        Args:
            speaker_channel: Speaker voice channel (restricted to speaker role)
            listener_channels: List of listener voice channels (restricted to listener role)
            broadcast_admin_role: Role for broadcast admins
            speaker_role: Role for speakers
            listener_role: Role for listeners
            custom_role: Optional role for section visibility

        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if bot has necessary permissions
            if not speaker_channel.guild.me.guild_permissions.manage_channels:
                logger.error(
                    f"Bot lacks 'Manage Channels' permission in {speaker_channel.guild.name}"
                )
                return False

            # Speaker channel: Restrict to speaker_role and broadcast_admin_role
            speaker_overwrites = {
                speaker_channel.guild.default_role: discord.PermissionOverwrite(
                    connect=False,
                    speak=False,
                    view_channel=True if not custom_role else False,
                ),
                custom_role: discord.PermissionOverwrite(
                    connect=False,
                    speak=False,
                    view_channel=True,
                ) if custom_role else None,
                speaker_role: discord.PermissionOverwrite(
                    connect=True,
                    speak=True,
                    view_channel=True,
                ) if speaker_role else None,
                broadcast_admin_role: discord.PermissionOverwrite(
                    connect=True,
                    speak=True,
                    view_channel=True,
                    manage_channels=True,
                ) if broadcast_admin_role else None,
                speaker_channel.guild.me: discord.PermissionOverwrite(
                    view_channel=True,
                    connect=True,
                    speak=True,
                    manage_channels=True,
                ),
            }
            for role, overwrite in speaker_overwrites.items():
                if role and overwrite:
                    await speaker_channel.set_permissions(role, overwrite=overwrite)
            logger.info(f"Set speaker channel permissions for: {speaker_channel.name}")

            # Listener channels: Restrict to listener_role and broadcast_admin_role
            for listener_channel in listener_channels:
                if not listener_channel.guild.me.guild_permissions.manage_channels:
                    logger.error(
                        f"Bot lacks 'Manage Channels' permission in {listener_channel.guild.name}"
                    )
                    return False

                listener_overwrites = {
                    listener_channel.guild.default_role: discord.PermissionOverwrite(
                        connect=True if not custom_role else False,
                        speak=True if not custom_role else False,
                        view_channel=True if not custom_role else False,
                    ),
                    custom_role: discord.PermissionOverwrite(
                        connect=True,
                        speak=True,
                        view_channel=True,
                    ) if custom_role else None,
                    listener_role: discord.PermissionOverwrite(
                        connect=True,
                        speak=True,
                        view_channel=True,
                    ) if listener_role else None,
                    broadcast_admin_role: discord.PermissionOverwrite(
                        connect=True,
                        speak=True,
                        manage_channels=True,
                    ) if broadcast_admin_role else None,
                    listener_channel.guild.me: discord.PermissionOverwrite(
                        view_channel=True,  # Ensure bot can see the channel
                        connect=True,
                        speak=True,
                        manage_channels=True,
                    ),
                }
                for role, overwrite in listener_overwrites.items():
                    if role and overwrite:
                        await listener_channel.set_permissions(role, overwrite=overwrite)
                logger.info(f"Set listener channel permissions for: {listener_channel.name}")

            return True

        except discord.Forbidden:
            logger.error("Bot lacks permissions to set voice channel permissions")
            return False
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
        if ctx.author.guild_permissions.administrator:
            return True
        return role_name in {role.name for role in ctx.author.roles}
    return commands.check(predicate)