"""
Broadcast-related command handlers for the main bot.

This module contains all commands related to starting, stopping, and managing
audio broadcasts.
"""

import re
from typing import Optional

import discord
from discord.ext import commands

from .base import BaseCommandHandler
from ..utils.embed_builder import EmbedBuilder


class BroadcastCommands(BaseCommandHandler):
    """Handles all broadcast-related commands."""

    async def start_broadcast_command(
        self, ctx: commands.Context, *, args: str
    ) -> None:
        """
        🎵 Start audio broadcasting with automatic setup.
        Usage: !start_broadcast 'Section Name' [N] [--role 'RoleName']
        """
        try:
            if not self.audio_router:
                await self._send_system_starting_embed(ctx)
                return

            # Parse arguments: 'Section Name' [N] [--role 'RoleName']
            (
                role_name,
                section_name,
                requested_listener_count,
            ) = await self._parse_start_broadcast_args(ctx, args)
            if role_name is None and section_name is None:
                return  # Error already sent

            server_id = str(ctx.guild.id)
            available_bots = await self._get_available_receiver_bots_count(ctx.guild)

            # Validate subscription limits
            listener_count = await self._validate_listener_count(
                ctx, server_id, requested_listener_count, available_bots
            )
            if listener_count is None:
                return  # Error already sent

            # Show loading message
            loading_message = await self._send_loading_embed(
                ctx,
                f"Creating broadcast section '{section_name}' with {listener_count} listener channels...",
            )

            # Check if there's an existing section (active or recovered)
            section = self.audio_router.section_manager.active_sections.get(
                ctx.guild.id
            )
            if section:
                await self._update_loading_embed(
                    loading_message,
                    "Restarting Broadcast",
                    "Found existing channels, restarting bots...",
                )
                # Start the broadcast directly without creating new channels
                start_result = await self.audio_router.start_broadcast(ctx.guild)
                await self._handle_broadcast_start_result(
                    ctx,
                    loading_message,
                    section.section_name,
                    len(section.listener_channel_ids),
                    None,  # role_name not available in this context
                    start_result,
                )
                return

            # Clean up any old sections with the same name if needed
            if ctx.guild.id in self.audio_router.section_manager.active_sections:
                cleanup_result = await self._cleanup_existing_section(
                    ctx, loading_message
                )
                if not cleanup_result:
                    return

            # Create the broadcast section
            result = await self.audio_router.create_broadcast_section(
                ctx.guild,
                section_name,
                listener_count,
                custom_role_name=role_name,
            )

            if not result["success"]:
                await self._send_error_embed(
                    loading_message, "Failed to Create Section", result["message"]
                )
                return

            # Start the broadcast
            await self._update_loading_embed(
                loading_message,
                "Starting Audio Broadcasting",
                "Starting audio forwarding from speaker to all listener channels...",
            )

            start_result = await self.audio_router.start_broadcast(ctx.guild)
            await self._handle_broadcast_start_result(
                ctx,
                loading_message,
                section_name,
                listener_count,
                role_name,
                start_result,
            )

        except Exception as e:
            await self._handle_command_error(ctx, e, "start_broadcast")

    async def stop_broadcast_command(self, ctx: commands.Context) -> None:
        """
        ⏹️ Stop audio broadcasting and clean up the entire section.
        Usage: !stop_broadcast
        """
        try:
            if not self.audio_router:
                await self._send_system_starting_embed(ctx)
                return

            section = self.audio_router.section_manager.active_sections.get(
                ctx.guild.id
            )
            if not section:
                await ctx.send(
                    embed=EmbedBuilder.error(
                        "No Active Section",
                        "No active broadcast section found in this server.",
                    )
                )
                return

            section_name = section.section_name
            loading_message = await self._send_loading_embed(
                ctx, f"Stopping audio forwarding for '{section_name}'..."
            )

            stop_result = await self.audio_router.stop_broadcast(ctx.guild)
            await self._handle_broadcast_stop_result(
                ctx, loading_message, section_name, stop_result
            )

        except Exception as e:
            await self._handle_command_error(ctx, e, "stop_broadcast")

    async def _parse_start_broadcast_args(
        self, ctx: commands.Context, args: str
    ) -> tuple[Optional[str], Optional[str], Optional[int]]:
        """Parse start_broadcast command arguments."""
        # Check for --role parameter
        role_name = None
        if "--role" in args:
            role_match = re.search(r"--role\s+'([^']+)'", args)
            if role_match:
                role_name = role_match.group(1)
                args = re.sub(r"\s*--role\s+'[^']+'", "", args).strip()
            else:
                # Send error embed for invalid role parameter
                embed = discord.Embed(
                    title="❌ Invalid Role Parameter",
                    description="**Usage:** `!start_broadcast 'Section Name' [N] [--role 'RoleName']`\n\n"
                    "**Examples:**\n"
                    "• `!start_broadcast 'War Room' 5` - Create with 5 listeners, visible to everyone\n"
                    "• `!start_broadcast 'War Room' 5 --role 'VIP'` - Create with 5 listeners, only visible to VIP role\n"
                    "• `!start_broadcast 'War Room' --role 'Members'` - Create with max listeners, only visible to Members role\n\n"
                    "**Note:** Role name must be in quotes!",
                    color=discord.Color.red(),
                )
                await ctx.send(embed=embed)
                return None, None, None

        # Parse remaining arguments: 'Section Name' [N]
        match_with_count = re.match(r"'([^']+)'\s+(\d+)", args.strip())
        match_without_count = re.match(r"'([^']+)'", args.strip())

        if match_with_count:
            section_name = match_with_count.group(1)
            requested_listener_count = int(match_with_count.group(2))
        elif match_without_count:
            section_name = match_without_count.group(1)
            requested_listener_count = None
        else:
            # Send error embed for invalid arguments
            embed = discord.Embed(
                title="📝 How to Use This Command",
                description="**Usage:** `!start_broadcast 'Section Name' [N] [--role 'RoleName']`\n\n"
                "**Examples:**\n"
                "• `!start_broadcast 'War Room' 5` - Create with 5 listeners, visible to everyone\n"
                "• `!start_broadcast 'War Room' 5 --role 'VIP'` - Create with 5 listeners, only visible to VIP role\n"
                "• `!start_broadcast 'War Room' --role 'Members'` - Create with max listeners, only visible to Members role\n\n"
                "**Note:** Section name must be in quotes!",
                color=discord.Color.blue(),
            )
            await ctx.send(embed=embed)
            return None, None, None

        return role_name, section_name, requested_listener_count

    async def _validate_listener_count(
        self,
        ctx: commands.Context,
        server_id: str,
        requested_count: Optional[int],
        available_bots: int,
    ) -> Optional[int]:
        """Validate listener count against subscription limits."""
        if not self.subscription_manager:
            if requested_count is None:
                requested_count = 1
            listener_count = min(requested_count, available_bots)
            if requested_count > available_bots:
                await self._send_limited_bots_embed(
                    ctx, requested_count, available_bots
                )
            return listener_count

        max_allowed = self.subscription_manager.get_server_max_listeners(server_id)
        if requested_count is None:
            requested_count = max_allowed

        is_valid, _, validation_message = (
            self.subscription_manager.validate_listener_count(
                server_id, requested_count
            )
        )

        if not is_valid:
            await ctx.send(embed=EmbedBuilder.subscription_error(validation_message))
            return None

        if max_allowed == 0:
            listener_count = min(requested_count, available_bots)
            if requested_count > available_bots:
                await self._send_limited_bots_embed(
                    ctx, requested_count, available_bots
                )
        else:
            listener_count = min(requested_count, max_allowed)
            if listener_count > available_bots:
                listener_count = available_bots
                await self._send_limited_bots_embed(ctx, max_allowed, available_bots)
            elif requested_count > max_allowed:
                await ctx.send(
                    embed=EmbedBuilder.info(
                        "Using Maximum Allowed Listeners",
                        f"Requested {requested_count} listeners, but your subscription allows {max_allowed}. Creating {max_allowed} listener channels.",
                    )
                )

        return listener_count

    async def _cleanup_existing_section(
        self, ctx: commands.Context, loading_message
    ) -> bool:
        """Clean up existing section and return success status."""
        await self._update_loading_embed(
            loading_message,
            "Cleaning Up Existing Section",
            "Found an existing broadcast section. Cleaning it up first...",
        )

        cleanup_result = await self.audio_router.section_manager.stop_broadcast(
            ctx.guild
        )
        if not cleanup_result["success"]:
            await self._send_error_embed(
                loading_message,
                "Failed to Cleanup Existing Section",
                cleanup_result["message"],
            )
            return False
        return True

    async def _handle_broadcast_start_result(
        self,
        ctx: commands.Context,
        loading_message: discord.Message,
        section_name: str,
        listener_count: int,
        role_name: Optional[str],
        start_result: dict,
    ) -> None:
        """Handle the result of starting a broadcast."""
        section = self.audio_router.section_manager.active_sections[ctx.guild.id]
        control_channel_mention = (
            f"<#{section.control_channel_id}>"
            if section.control_channel_id
            else "the control channel"
        )
        section.original_message = loading_message

        if start_result["success"]:
            visibility_info = (
                f"✅ Category visible only to **{role_name}** role members\n"
                if role_name
                else "✅ Category visible to everyone\n"
            )

            embed = EmbedBuilder.success(
                "Broadcast Started Successfully!",
                f"**{section_name}** is now live!\n\n"
                f"✅ Section created with {listener_count} listener channels\n"
                f"✅ Audio forwarding is active\n"
                f"✅ Presenters can join the speaker channel\n"
                f"✅ Audience can join any listener channel\n"
                f"{visibility_info}\n"
                f"Go to {control_channel_mention} for more commands!",
            )
        else:
            embed = EmbedBuilder.warning(
                "Section Created but Broadcast Failed",
                f"**{section_name}** was created successfully, but starting the broadcast failed:\n\n"
                f"{start_result['message']}\n\n"
                f"Go to {control_channel_mention} to try `!start_broadcast` again or use `!stop_broadcast` to clean up.",
            )

        await loading_message.edit(embed=embed)

    async def _handle_broadcast_stop_result(
        self,
        ctx: commands.Context,
        loading_message: discord.Message,
        section_name: str,
        stop_result: dict,
    ) -> None:
        """Handle the result of stopping a broadcast."""
        if stop_result["success"]:
            embed = EmbedBuilder.success(
                "Broadcast Stopped and Cleaned Up!",
                f"**{section_name}** has been completely removed:\n\n"
                f"✅ Audio broadcasting stopped\n"
                f"✅ All broadcast channels deleted\n"
                f"✅ Category removed\n"
                f"✅ All resources cleaned up\n\n"
                f"Use `!start_broadcast 'Name'` or `!start_broadcast 'Name' N` to create a new section.",
            )
        else:
            embed = EmbedBuilder.warning(
                "Failed to Stop Broadcast",
                f"Could not stop broadcasting: {stop_result['message']}\n\n"
                f"Proceeding with cleanup anyway...",
            )

        try:
            await loading_message.edit(embed=embed)
        except discord.NotFound:
            self.logger.info(
                f"Cleanup completed for section '{section_name}', but control channel was deleted"
            )

        # Update original start_broadcast message if it exists
        section = self.audio_router.section_manager.active_sections.get(ctx.guild.id)
        if section and getattr(section, "original_message", None):
            try:
                ended_embed = EmbedBuilder.info(
                    "Broadcast Ended",
                    f"**{section_name}** broadcast has been stopped and cleaned up.\n\n"
                    f"✅ All channels and resources have been removed\n"
                    f"✅ Ready for a new broadcast section\n\n"
                    f"Use `!start_broadcast 'Name'` or `!start_broadcast 'Name' N` to create a new section.",
                )
                await section.original_message.edit(embed=ended_embed)
            except Exception as e:
                self.logger.warning(
                    f"Could not update original start_broadcast loading message: {e}"
                )

    async def _send_limited_bots_embed(
        self, ctx: commands.Context, requested: int, available: int
    ) -> None:
        """Send embed when limited by available receiver bots."""
        embed = EmbedBuilder.warning(
            "Limited by Available Receiver Bots",
            f"Requested {requested} listeners, but only {available} receiver bots are available.\n\n"
            f"**Please install additional receiver bots to support more listeners.**\n"
            f"Creating {available} listener channels.",
        )
        await ctx.send(embed=embed)
