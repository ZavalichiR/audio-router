"""
Setup and configuration command handlers for the main bot.

This module contains commands related to server setup, role management,
and permission checking.
"""

import discord
from discord.ext import commands

from .base import BaseCommandHandler
from ..utils.embed_builder import EmbedBuilder


class SetupCommands(BaseCommandHandler):
    """Handles all setup and configuration commands."""

    async def setup_roles_command(self, ctx: commands.Context) -> None:
        """Create and configure the required roles for the audio router system."""
        try:
            if not self.audio_router or not hasattr(
                self.audio_router, "access_control"
            ):
                await ctx.send(
                    embed=EmbedBuilder.warning(
                        "System Loading",
                        "The access control system is still initializing. Please wait a moment and try again.",
                    )
                )
                return

            # Create roles and send comprehensive summary
            role_results = await self._create_roles(ctx)
            summary_embed = self._build_role_setup_summary(ctx, role_results)
            await ctx.send(embed=summary_embed)

        except Exception as e:
            await self._handle_command_error(ctx, e, "setup_roles")

    async def _create_roles(self, ctx: commands.Context) -> dict:
        """Create all required roles for the audio router system."""
        role_results = {}

        # Check if bot has permission to manage roles
        if not ctx.guild.me.guild_permissions.manage_roles:
            return role_results

        # Get role names from AccessControl configuration
        access_control = self.audio_router.access_control

        # 1. Create Broadcast Admin Role (highest priority)
        broadcast_admin_result = await self._create_single_role(
            ctx,
            access_control.broadcast_admin_role_name,
            "Required to use bot commands like !control_panel",
            discord.Color.red(),
        )
        role_results["broadcast_admin"] = broadcast_admin_result

        # 2. Create Speaker Role
        speaker_result = await self._create_single_role(
            ctx,
            access_control.speaker_role_name,
            "Required to join speaker channels and broadcast audio",
            discord.Color.green(),
        )
        role_results["speaker"] = speaker_result

        # 3. Create Listener Role
        listener_result = await self._create_single_role(
            ctx,
            access_control.listener_role_name,
            "Required to join listener channels and receive audio",
            discord.Color.blue(),
        )
        role_results["listener"] = listener_result

        return role_results

    async def _create_single_role(
        self, ctx: commands.Context, role_name: str, purpose: str, color: discord.Color
    ) -> dict:
        """Create a single role and return result information."""
        # Check if role already exists
        existing_role = discord.utils.get(ctx.guild.roles, name=role_name)
        if existing_role:
            return {
                "success": True,
                "role": existing_role,
                "created": False,
                "message": "Role already exists",
                "purpose": purpose,
            }

        # Try to create the role
        try:
            new_role = await ctx.guild.create_role(
                name=role_name, color=color, reason="Audio Router Bot setup"
            )
            return {
                "success": True,
                "role": new_role,
                "created": True,
                "message": "Successfully created",
                "purpose": purpose,
            }
        except discord.Forbidden:
            return {
                "success": False,
                "role": None,
                "created": False,
                "message": "Failed - insufficient permissions",
                "purpose": purpose,
            }
        except Exception as e:
            return {
                "success": False,
                "role": None,
                "created": False,
                "message": f"Failed - {str(e)}",
                "purpose": purpose,
            }

    def _build_role_setup_summary(
        self, ctx: commands.Context, role_results: dict
    ) -> discord.Embed:
        """Build a summary of all role creation results."""
        total_roles = len(role_results)
        successful_roles = sum(
            1 for result in role_results.values() if result["success"]
        )

        if successful_roles == total_roles:
            embed = EmbedBuilder.success(
                "🎉 Role Setup Complete!",
                f"All {total_roles} required roles are ready to use.",
            )
        elif successful_roles > 0:
            embed = EmbedBuilder.warning(
                "⚠️ Partial Setup Complete",
                f"{successful_roles} out of {total_roles} roles were set up successfully.",
            )
        else:
            embed = EmbedBuilder.error(
                "❌ Setup Failed",
                "No roles could be created. Please check bot permissions.",
            )

        # Add role details with proper formatting
        access_control = self.audio_router.access_control
        role_display_names = {
            "broadcast_admin": access_control.broadcast_admin_role_name,
            "speaker": access_control.speaker_role_name,
            "listener": access_control.listener_role_name,
        }

        for role_name, result in role_results.items():
            status_emoji = "✅" if result["success"] else "❌"
            display_name = role_display_names.get(
                role_name, role_name.replace("_", " ").title()
            )
            role_mention = (
                result["role"].mention if result["role"] else f"`{display_name}`"
            )

            # Create clean status message
            if result["created"]:
                status_text = "Successfully created"
            elif result["message"] == "Role already exists":
                status_text = "Already exists"
            else:
                status_text = result["message"]

            embed.add_field(
                name=f"{status_emoji} {display_name}",
                value=f"**Role:** {role_mention}\n**Status:** {status_text}\n**Purpose:** {result['purpose']}",
                inline=False,
            )

        # Add next steps
        if successful_roles > 0:
            access_control = self.audio_router.access_control
            embed.add_field(
                name="📝 Next Steps",
                value=f"Assign the {access_control.broadcast_admin_role_name} and {access_control.speaker_role_name} roles to the members that will join the speaker channel and start the broadcast",
                inline=False,
            )
        else:
            embed.add_field(
                name="🔧 How to Fix",
                value="1. **Check Permissions:** Ensure bot has 'Manage Roles' permission\n"
                "2. **Role Hierarchy:** Move bot's role higher in server settings\n"
                "3. **Try Again:** Run `!setup_roles` after fixing permissions",
                inline=False,
            )

        return embed
