"""
Simplified Access Control System for Discord Audio Router Bot.

This module provides a clean role-based access control system:
- Speaker role: Required to join speaker channels
- Broadcast Admin role: Required to use bot commands
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
        self.broadcast_admin_role_name = getattr(
            config, "broadcast_admin_role_name", "Broadcast Admin"
        )
        self.listener_role_name = getattr(config, "listener_role_name", "Listener")
        self.auto_create_roles = getattr(config, "auto_create_roles", True)

        logger.info(
            f"AccessControl initialized: speaker='{self.speaker_role_name}', admin='{self.broadcast_admin_role_name}', listener='{self.listener_role_name}'"
        )

    async def ensure_roles_exist(
        self, guild: discord.Guild, custom_role_name: Optional[str] = None
    ) -> Dict[str, Optional[discord.Role]]:
        """
        Ensure required roles exist, creating if allowed.
        Returns dict with role objects: speaker, listener, admin, custom
        """
        result = {"speaker": None, "listener": None, "admin": None, "custom": None}
        if not self.auto_create_roles or not guild.me.guild_permissions.manage_roles:
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
        result["listener"] = await get_or_create(
            self.listener_role_name, discord.Color.blue()
        )
        result["admin"] = await get_or_create(
            self.broadcast_admin_role_name, discord.Color.red()
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
        Build overwrites for control channel: default, admin, bot
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
        admin = roles.get("admin")
        if admin:
            overwrites[admin] = discord.PermissionOverwrite(
                read_messages=True, send_messages=True, embed_links=True
            )
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
        if roles.get("admin"):
            overwrites[roles["admin"]] = discord.PermissionOverwrite(
                connect=True, speak=True, view_channel=True, manage_channels=True
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
        if roles.get("listener"):
            overwrites[roles["listener"]] = discord.PermissionOverwrite(
                connect=True, speak=True, view_channel=True
            )
        if roles.get("admin"):
            overwrites[roles["admin"]] = discord.PermissionOverwrite(
                connect=True, speak=True, manage_channels=True
            )
        return overwrites


def is_broadcast_admin(role_name: str = "Broadcast Admin"):
    def predicate(ctx):
        if ctx.author.guild_permissions.administrator:
            return True
        return role_name in {r.name for r in ctx.author.roles}

    return commands.check(predicate)
