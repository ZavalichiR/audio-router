"""
Control Panel command handlers for the main bot.

This module contains commands for managing the control panel UI,
including creating, updating, and managing control panel settings.
"""

from typing import Optional

import discord
from discord.ext import commands

from .base import BaseCommandHandler
from ..utils.control_panel_storage import get_storage, ControlPanelSettings
from ..utils.control_panel_ui import ControlPanelView, create_control_panel_embed
from ..utils.embed_builder import EmbedBuilder


class ControlPanelCommands(BaseCommandHandler):
    """Handles all control panel related commands."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.storage = get_storage()
        self.active_panels: dict[int, discord.Message] = {}  # guild_id -> message

    async def control_panel_command(self, ctx: commands.Context) -> None:
        """
        🎛️ Create or update the control panel UI.
        Usage: !control_panel
        """
        try:
            if not self.audio_router:
                await self._send_system_starting_embed(ctx)
                return

            guild_id = ctx.guild.id

            # Get max available listeners for this guild
            max_listeners = await self._get_available_receiver_bots_count(ctx.guild)

            # Get current settings with max_listeners for proper default
            settings = self.storage.get_settings(guild_id, max_listeners)
            if max_listeners == 0:
                await ctx.send(
                    embed=EmbedBuilder.error(
                        "No Receiver Bots Available",
                        "No AudioReceiver bots are available in this server. Please install at least one receiver bot to use the control panel.",
                    )
                )
                return

            # Update listener count if it exceeds max
            if settings.listener_channels > max_listeners:
                self.storage.update_settings(guild_id, listener_channels=max_listeners)

            # Check if there's an active broadcast
            is_active = guild_id in self.audio_router.section_manager.active_sections

            # Create the control panel embed
            embed = create_control_panel_embed(settings, is_active, max_listeners)

            # Create the control panel view
            view = ControlPanelView(
                settings=settings,
                max_listeners=max_listeners,
                start_broadcast_callback=self._start_broadcast_from_panel,
                stop_broadcast_callback=self._stop_broadcast_from_panel,
            )

            # Set up the callback function
            view._update_all_settings = (
                lambda section_name,
                listener_count,
                role_name: self._update_all_settings(
                    ctx, section_name, listener_count, role_name
                )
            )

            # Send or update the control panel
            if guild_id in self.active_panels:
                try:
                    # Update existing panel
                    await self.active_panels[guild_id].edit(embed=embed, view=view)
                except discord.NotFound:
                    # Panel message was deleted, create new one
                    message = await ctx.send(embed=embed, view=view)
                    self.active_panels[guild_id] = message
            else:
                # Create new panel
                message = await ctx.send(embed=embed, view=view)
                self.active_panels[guild_id] = message

        except Exception as e:
            await self._handle_command_error(ctx, e, "control_panel")

    async def _update_all_settings(
        self,
        ctx: commands.Context,
        section_name: str,
        listener_count: int,
        role_name: Optional[str],
    ) -> None:
        """Update all settings at once and refresh panel."""
        try:
            guild_id = ctx.guild.id
            max_listeners = await self._get_available_receiver_bots_count(ctx.guild)

            # Validate listener count
            if listener_count > max_listeners:
                listener_count = max_listeners

            # Validate role if provided
            if role_name:
                role = discord.utils.get(ctx.guild.roles, name=role_name)
                if not role:
                    await ctx.send(
                        f"❌ Role '{role_name}' not found in this server!",
                        ephemeral=True,
                    )
                    return

            # Update all settings at once
            self.storage.update_settings(
                guild_id,
                section_name=section_name,
                listener_channels=listener_count,
                permission_role=role_name,
            )
            await self._refresh_control_panel(ctx.guild)
        except Exception as e:
            await ctx.send(f"❌ Failed to update settings: {str(e)}", ephemeral=True)

    def _log_settings(self, settings: ControlPanelSettings) -> None:
        """Log current settings in a consistent format."""
        self.logger.info(
            f"Using settings: section_name={settings.section_name}, "
            f"listener_channels={settings.listener_channels}, "
            f"permission_role={settings.permission_role}"
        )

    def _log_broadcast_creation(self, settings: ControlPanelSettings) -> None:
        """Log broadcast section creation in a consistent format."""
        self.logger.info(
            f"Creating broadcast section: {settings.section_name} "
            f"with {settings.listener_channels} listeners"
        )

    async def _refresh_control_panel(self, guild: discord.Guild) -> None:
        """Refresh the control panel for a guild."""
        try:
            guild_id = guild.id
            if guild_id not in self.active_panels:
                return

            # Get max available listeners
            max_listeners = await self._get_available_receiver_bots_count(guild)

            # Get current settings with max_listeners for proper default
            settings = self.storage.get_settings(guild_id, max_listeners)

            # Check if there's an active broadcast
            is_active = guild_id in self.audio_router.section_manager.active_sections

            # Create updated embed
            embed = create_control_panel_embed(settings, is_active, max_listeners)

            # Create updated view
            view = ControlPanelView(
                settings=settings,
                max_listeners=max_listeners,
                start_broadcast_callback=lambda ctx: self._start_broadcast_from_panel_guild(
                    guild
                ),  # Fixed
                stop_broadcast_callback=lambda ctx: self._stop_broadcast_from_panel_guild(
                    guild
                ),  # Fixed
            )

            # Set up callback function
            view._update_all_settings = (
                lambda section_name,
                listener_count,
                role_name: self._update_all_settings_guild(
                    guild, section_name, listener_count, role_name
                )
            )

            # Update the panel
            await self.active_panels[guild_id].edit(embed=embed, view=view)
        except Exception as e:
            self.logger.error(
                f"Failed to refresh control panel for guild {guild_id}: {e}",
                exc_info=True,
            )

    async def _start_broadcast_from_panel(self, ctx: commands.Context) -> None:
        """Start broadcast using current panel settings."""
        try:
            self.logger.info(f"Starting broadcast from panel for guild {ctx.guild.id}")

            # Check if audio router is available (same as commands)
            if not self.audio_router:
                self.logger.warning("Audio router not available")
                await ctx.send(
                    "⚠️ System is still starting up. Please try again in a moment.",
                    ephemeral=True,
                )
                return

            guild_id = ctx.guild.id
            settings = self.storage.get_settings(guild_id)
            self._log_settings(settings)

            # Check if there's already an active broadcast
            if guild_id in self.audio_router.section_manager.active_sections:
                self.logger.info(f"Broadcast already active for guild {guild_id}")
                await ctx.send(
                    "⚠️ A broadcast is already active in this server!", ephemeral=True
                )
                return

            # Clean up existing section if needed (same as command)
            if ctx.guild.id in self.audio_router.section_manager.active_sections:
                self.logger.info("Cleaning up existing section before creating new one")
                cleanup_result = await self._cleanup_existing_section(ctx, None)
                if not cleanup_result:
                    return

            # Create broadcast section directly
            self._log_broadcast_creation(settings)
            result = await self.audio_router.create_broadcast_section(
                ctx.guild,
                settings.section_name,
                settings.listener_channels,
                custom_role_name=settings.permission_role,
            )

            if not result["success"]:
                self.logger.error(
                    f"Failed to create broadcast section: {result['message']}"
                )
                return

            # Start the broadcast
            self.logger.info("Starting audio broadcast")
            start_result = await self.audio_router.start_broadcast(ctx.guild)
            if not start_result["success"]:
                self.logger.error(
                    f"Failed to start broadcast: {start_result['message']}"
                )
                return

            # Refresh the panel
            await self._refresh_control_panel(ctx.guild)

        except Exception as e:
            self.logger.error(
                f"Error in _start_broadcast_from_panel: {e}", exc_info=True
            )
            await ctx.send(f"❌ Failed to start broadcast: {str(e)}", ephemeral=True)

    async def _stop_broadcast_from_panel(self, ctx: commands.Context) -> None:
        """Stop broadcast from panel."""
        try:
            self.logger.info(f"Stopping broadcast from panel for guild {ctx.guild.id}")

            # Check if audio router is available (same as commands)
            if not self.audio_router:
                self.logger.warning("Audio router not available")
                await ctx.send(
                    "⚠️ System is still starting up. Please try again in a moment.",
                    ephemeral=True,
                )
                return

            guild_id = ctx.guild.id

            # Check if there's an active broadcast (same as command)
            section = self.audio_router.section_manager.active_sections.get(guild_id)
            if not section:
                self.logger.info(f"No active broadcast found for guild {guild_id}")
                await ctx.send(
                    "⚠️ No active broadcast found in this server!", ephemeral=True
                )
                return

            section_name = section.section_name
            self.logger.info(f"Stopping broadcast for section: {section_name}")

            # Stop the broadcast directly
            stop_result = await self.audio_router.stop_broadcast(ctx.guild)
            if not stop_result["success"]:
                self.logger.error(f"Failed to stop broadcast: {stop_result['message']}")
                return

            # Refresh the panel
            await self._refresh_control_panel(ctx.guild)

        except Exception as e:
            self.logger.error(
                f"Error in _stop_broadcast_from_panel: {e}", exc_info=True
            )
            await ctx.send(f"❌ Failed to stop broadcast: {str(e)}", ephemeral=True)

    async def _cleanup_existing_section(
        self, ctx: commands.Context, loading_message=None
    ) -> bool:
        """Clean up existing section and return success status."""
        cleanup_result = await self.audio_router.section_manager.stop_broadcast(
            ctx.guild
        )
        if not cleanup_result["success"]:
            self.logger.error(
                f"Failed to cleanup existing section: {cleanup_result['message']}"
            )
            return False
        return True

    # Guild-based versions for callbacks
    async def _start_broadcast_from_panel_guild(self, guild: discord.Guild) -> None:
        """Start broadcast using current panel settings (guild version)."""
        try:
            self.logger.info(
                f"Starting broadcast from panel (guild) for guild {guild.id}"
            )

            # Check if audio router is available
            if not self.audio_router:
                self.logger.warning("Audio router not available for guild start")
                return

            guild_id = guild.id
            settings = self.storage.get_settings(guild_id)
            self._log_settings(settings)

            # Check if there's already an active broadcast
            if guild_id in self.audio_router.section_manager.active_sections:
                self.logger.info(f"Broadcast already active for guild {guild.id}")
                return

            # Clean up existing section if needed
            if guild.id in self.audio_router.section_manager.active_sections:
                self.logger.info("Cleaning up existing section before creating new one")
                cleanup_result = await self.audio_router.section_manager.stop_broadcast(
                    guild
                )
                if not cleanup_result["success"]:
                    self.logger.error(
                        f"Failed to cleanup existing section: {cleanup_result['message']}"
                    )
                    return

            # Create broadcast section directly
            self._log_broadcast_creation(settings)
            result = await self.audio_router.create_broadcast_section(
                guild,
                settings.section_name,
                settings.listener_channels,
                custom_role_name=settings.permission_role,
            )

            if not result["success"]:
                self.logger.error(
                    f"Failed to create broadcast section: {result['message']}"
                )
                return

            # Start the broadcast
            self.logger.info("Starting audio broadcast")
            start_result = await self.audio_router.start_broadcast(guild)
            if not start_result["success"]:
                self.logger.error(
                    f"Failed to start broadcast: {start_result['message']}"
                )
                return

            self.logger.info(f"Successfully started broadcast for guild {guild.id}")

            # Refresh the panel
            await self._refresh_control_panel(guild)
        except Exception as e:
            self.logger.error(
                f"Failed to start broadcast from panel for guild {guild.id}: {e}",
                exc_info=True,
            )

    async def _stop_broadcast_from_panel_guild(self, guild: discord.Guild) -> None:
        """Stop broadcast from panel (guild version)."""
        try:
            self.logger.info(
                f"Stopping broadcast from panel (guild) for guild {guild.id}"
            )

            # Check if audio router is available
            if not self.audio_router:
                self.logger.warning("Audio router not available for guild stop")
                return

            guild_id = guild.id

            # Check if there's an active broadcast
            section = self.audio_router.section_manager.active_sections.get(guild_id)
            if not section:
                self.logger.info(f"No active broadcast found for guild {guild.id}")
                return

            section_name = section.section_name
            self.logger.info(f"Stopping broadcast for section: {section_name}")

            # Stop the broadcast directly
            stop_result = await self.audio_router.stop_broadcast(guild)
            if not stop_result["success"]:
                self.logger.error(f"Failed to stop broadcast: {stop_result['message']}")
                return

            self.logger.info(f"Successfully stopped broadcast for guild {guild.id}")

            # Refresh the panel
            await self._refresh_control_panel(guild)
        except Exception as e:
            self.logger.error(
                f"Failed to stop broadcast from panel for guild {guild.id}: {e}",
                exc_info=True,
            )

    async def _update_all_settings_guild(
        self,
        guild: discord.Guild,
        section_name: str,
        listener_count: int,
        role_name: Optional[str],
    ) -> None:
        """Update all settings at once (guild version)."""
        try:
            guild_id = guild.id
            max_listeners = await self._get_available_receiver_bots_count(guild)

            # Validate listener count
            if listener_count > max_listeners:
                listener_count = max_listeners

            # Update all settings at once
            self.storage.update_settings(
                guild_id,
                section_name=section_name,
                listener_channels=listener_count,
                permission_role=role_name,
            )
            await self._refresh_control_panel(guild)
        except Exception as e:
            self.logger.error(
                f"Failed to update all settings for guild {guild.id}: {e}",
                exc_info=True,
            )
