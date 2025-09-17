"""
Simplified Access Control System for Discord Audio Router Bot.

This module provides a clean role-based access control system:
- Speaker role: Required to join speaker channels
- Custom role: Optional role for category visibility
"""

from typing import Optional, Dict

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
    """

    def __init__(self, config):
        self.config = config
        self.speaker_role_name = getattr(config, "speaker_role_name", "Speaker")

        logger.info(f"AccessControl initialized: speaker='{self.speaker_role_name}'")

    async def ensure_roles_exist(
        self, guild: discord.Guild, custom_role_name: Optional[str] = None
    ) -> Dict[str, Optional[discord.Role]]:
        """
        Ensure required roles exist, creating if allowed.
        Returns dict with role objects: speaker, custom
        """
        result = {"speaker": None, "custom": None}
        if not guild.me.guild_permissions.manage_roles:
            return result

        async def get_or_create(name: str, color: discord.Color):
            role = discord.utils.get(guild.roles, name=name)
            if not role:
                try:
                    role = await guild.create_role(
                        name=name, color=color, reason="AccessControl setup"
                    )
                    logger.info(f"Created role: {name}")
                except Exception as e:
                    logger.error(f"Failed to create role '{name}': {e}")
                    return None
            return role

        result["speaker"] = await get_or_create(
            self.speaker_role_name, discord.Color.green()
        )
        if custom_role_name:
            result["custom"] = discord.utils.get(guild.roles, name=custom_role_name)

        return result

    def get_category_overwrites(
        self,
        guild: discord.Guild,
        roles: Dict[str, Optional[discord.Role]],
    ) -> Dict[discord.Role, discord.PermissionOverwrite]:
        """
        Build overwrites for category: default, custom, bot
        """
        overwrites: Dict[discord.Role, discord.PermissionOverwrite] = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=not bool(roles.get("custom"))
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True, manage_channels=True
            ),
        }
        custom = roles.get("custom")
        if custom:
            overwrites[custom] = discord.PermissionOverwrite(view_channel=True)
        return overwrites

    def get_control_overwrites(
        self,
        guild: discord.Guild,
        roles: Dict[str, Optional[discord.Role]],
    ) -> Dict[discord.Role, discord.PermissionOverwrite]:
        """
        Build overwrites for control channel: default, bot
        """
        overwrites: Dict[discord.Role, discord.PermissionOverwrite] = {
            guild.default_role: discord.PermissionOverwrite(
                read_messages=False, send_messages=False
            ),
            guild.me: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                manage_messages=True,
                embed_links=True,
            ),
        }
        return overwrites

    def get_speaker_overwrites(
        self,
        guild: discord.Guild,
        roles: Dict[str, Optional[discord.Role]],
    ) -> Dict[discord.Role, discord.PermissionOverwrite]:
        """
        Build overwrites for speaker voice channel.
        """
        overwrites: Dict[discord.Role, discord.PermissionOverwrite] = {
            guild.default_role: discord.PermissionOverwrite(
                connect=False, speak=False, view_channel=not bool(roles.get("custom"))
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True, connect=True, speak=True, manage_channels=True
            ),
        }
        if roles.get("custom"):
            overwrites[roles["custom"]] = discord.PermissionOverwrite(
                view_channel=True, connect=False, speak=False
            )
        if roles.get("speaker"):
            overwrites[roles["speaker"]] = discord.PermissionOverwrite(
                connect=True, speak=True, view_channel=True
            )
        return overwrites

    def get_listener_overwrites(
        self,
        guild: discord.Guild,
        roles: Dict[str, Optional[discord.Role]],
    ) -> Dict[discord.Role, discord.PermissionOverwrite]:
        """
        Build overwrites for listener voice channels.
        """
        overwrites: Dict[discord.Role, discord.PermissionOverwrite] = {
            guild.default_role: discord.PermissionOverwrite(
                connect=not bool(roles.get("custom")),
                speak=not bool(roles.get("custom")),
                view_channel=not bool(roles.get("custom")),
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True, connect=True, speak=True, manage_channels=True
            ),
        }
        if roles.get("custom"):
            overwrites[roles["custom"]] = discord.PermissionOverwrite(
                view_channel=True, connect=True, speak=True
            )
        return overwrites


def is_administrator():
    """Check if user has administrator permissions."""

    def predicate(ctx):
        return ctx.author.guild_permissions.administrator

    return commands.check(predicate)
