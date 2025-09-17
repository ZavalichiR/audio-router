"""
Control Panel UI Components

This module contains Discord View UI components for the control panel,
including buttons, modals, and the main control panel view.
"""

import discord
from typing import Optional, Callable

from .control_panel_storage import ControlPanelSettings


class SetupModal(discord.ui.Modal, title="⚙️ Broadcast Setup"):
    """Comprehensive setup modal for all broadcast settings."""

    def __init__(
        self,
        settings: ControlPanelSettings,
        max_listeners: int,
        callback: Callable[[str, int, Optional[str]], None],
    ):
        super().__init__()
        self.callback_func = callback
        self.max_listeners = max_listeners

        # Section Name
        self.section_name_input = discord.ui.TextInput(
            label="Section Name",
            placeholder="Enter a descriptive name for your broadcast...",
            default=settings.section_name,
            max_length=50,
            required=True,
            style=discord.TextStyle.short,
        )
        self.add_item(self.section_name_input)

        # Listener Channels
        self.listener_count_input = discord.ui.TextInput(
            label=f"Listener Channels (Max: {max_listeners})",
            placeholder=f"Enter number of listener channels (1-{max_listeners})...",
            default=str(settings.listener_channels),
            max_length=3,
            required=True,
            style=discord.TextStyle.short,
        )
        self.add_item(self.listener_count_input)

        # Permission Role
        self.role_input = discord.ui.TextInput(
            label="Permission Role",
            placeholder="Enter role name (leave empty for 'Everyone')...",
            default=settings.permission_role or "",
            max_length=100,
            required=False,
            style=discord.TextStyle.short,
        )
        self.add_item(self.role_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle modal submission."""
        try:
            # Get values, using defaults if empty
            section_name = self.section_name_input.value.strip()
            if not section_name:
                await interaction.response.send_message(
                    "⚠️ **Invalid Input**\nSection name cannot be empty. Please enter a valid name.",
                    ephemeral=True,
                )
                return

            # Parse listener count
            try:
                listener_count = int(self.listener_count_input.value.strip())
                if listener_count < 1 or listener_count > self.max_listeners:
                    await interaction.response.send_message(
                        f"⚠️ **Invalid Range**\nListener count must be between **1** and **{self.max_listeners}**.\nYou entered: `{listener_count}`",
                        ephemeral=True,
                    )
                    return
            except ValueError:
                await interaction.response.send_message(
                    "⚠️ **Invalid Input**\nPlease enter a valid number for listener channels.",
                    ephemeral=True,
                )
                return

            # Get role (can be empty)
            role_name = self.role_input.value.strip() or None

            # Call the callback with all values
            await self.callback_func(section_name, listener_count, role_name)
            await interaction.response.defer()

        except Exception as e:
            await interaction.response.send_message(
                f"⚠️ **Error**\nAn error occurred while saving settings: {str(e)}",
                ephemeral=True,
            )


class StartBroadcastConfirmationView(discord.ui.View):
    """Confirmation dialog for starting broadcast when one is already active."""

    def __init__(self, callback: Callable):
        super().__init__(timeout=30)
        self.callback = callback

    async def on_timeout(self):
        """Handle timeout by disabling all buttons."""
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(view=self)
        except Exception:
            pass  # Message might be deleted or inaccessible

    @discord.ui.button(label="Continue", style=discord.ButtonStyle.danger, emoji="⚠️")
    async def confirm_start(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Confirm restart of broadcast."""
        # Disable all buttons immediately
        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(view=self)
        await self.callback(interaction)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_start(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Cancel the restart."""
        # Disable all buttons immediately
        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(
            content="✅ Broadcast restart cancelled.", view=self
        )
        self.stop()


class StopBroadcastConfirmationView(discord.ui.View):
    """Confirmation dialog for stopping broadcast."""

    def __init__(self, callback: Callable):
        super().__init__(timeout=30)
        self.callback = callback

    async def on_timeout(self):
        """Handle timeout by disabling all buttons."""
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(view=self)
        except Exception:
            pass  # Message might be deleted or inaccessible

    @discord.ui.button(
        label="Stop Broadcast", style=discord.ButtonStyle.danger, emoji="⏹️"
    )
    async def confirm_stop(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Confirm stopping broadcast."""
        # Disable all buttons immediately
        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(view=self)
        await self.callback(interaction)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_stop(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Cancel stopping broadcast."""
        # Disable all buttons immediately
        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(
            content="✅ Broadcast stop cancelled.", view=self
        )
        self.stop()


class ControlPanelView(discord.ui.View):
    """Main control panel view with all interactive elements."""

    def __init__(
        self,
        settings: ControlPanelSettings,
        max_listeners: int,
        start_broadcast_callback: Callable[[], None],
        stop_broadcast_callback: Callable[[], None],
        audio_router=None,
    ):
        super().__init__(timeout=None)  # Persistent view
        self.settings = settings
        self.max_listeners = max_listeners
        self.start_broadcast_callback = start_broadcast_callback
        self.stop_broadcast_callback = stop_broadcast_callback
        self.audio_router = audio_router
        self._setup_buttons()

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item
    ) -> None:
        """Handle errors in button interactions."""
        # Try to send an error message to the user
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"❌ An error occurred: {str(error)}", ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"❌ An error occurred: {str(error)}", ephemeral=True
                )
        except Exception:
            pass  # If we can't send an error message, just continue

    def _setup_buttons(self) -> None:
        """Setup all buttons for the control panel with optimal UX design."""
        # Row 0: Start Broadcast, Stop Broadcast, and Setup buttons (all controls)
        # Buttons are defined using @discord.ui.button decorators
        pass

    @discord.ui.button(
        label="Start Broadcast",
        style=discord.ButtonStyle.success,
        emoji="▶️",
        row=0,
        custom_id="start_broadcast",
    )
    async def start_broadcast_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Handle start broadcast button click."""
        try:
            # Get guild directly from interaction
            guild = interaction.guild
            if not guild:
                await interaction.response.send_message(
                    "❌ This command can only be used in a server", ephemeral=True
                )
                return

            # Check if broadcast section exists (regardless of active status)
            bot = interaction.client
            audio_router = self.audio_router
            if audio_router and audio_router.section_manager.active_sections.get(
                guild.id
            ):
                # Show confirmation dialog for restart
                section = audio_router.section_manager.active_sections.get(guild.id)
                status_text = (
                    "active" if section.is_active else "created but not yet active"
                )

                embed = discord.Embed(
                    title="⚠️ Broadcast Section Already Exists",
                    description=(
                        f"**A broadcast section '{section.section_name}' already exists** (status: {status_text}).\n\n"
                        "**Starting again will:**\n"
                        "• Restart the communication between speaker and channels\n"
                        "• Interrupt audio for 5-10 seconds\n"
                        "• Reconnect all bots to their channels\n\n"
                        "**Run this command only if:**\n"
                        "• The broadcast started but no one can hear the listeners\n"
                        "• You need to force a restart of the communication\n\n"
                        "**Are you sure you want to restart the broadcast?**"
                    ),
                    color=discord.Color.orange(),
                )

                async def confirmed_callback(interaction):
                    # Create a context for the callback
                    bot = interaction.client
                    ctx = await bot.get_context(interaction.message)
                    if ctx:
                        await self.start_broadcast_callback(ctx)

                view = StartBroadcastConfirmationView(confirmed_callback)
                await interaction.response.send_message(
                    embed=embed, view=view, ephemeral=True
                )
            else:
                # No active broadcast, proceed normally
                await interaction.response.defer()
                # Create a context for the callback
                ctx = await bot.get_context(interaction.message)
                if ctx:
                    await self.start_broadcast_callback(ctx)

        except Exception as e:
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        f"❌ Error: {str(e)}", ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        f"❌ Error: {str(e)}", ephemeral=True
                    )
            except Exception:
                pass

    @discord.ui.button(
        label="Stop Broadcast",
        style=discord.ButtonStyle.danger,
        emoji="⏹️",
        row=0,
        custom_id="stop_broadcast",
    )
    async def stop_broadcast_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Handle stop broadcast button click."""
        try:
            # Get guild directly from interaction
            guild = interaction.guild
            if not guild:
                await interaction.response.send_message(
                    "❌ This command can only be used in a server", ephemeral=True
                )
                return

            # Check if broadcast section exists (regardless of active status)
            audio_router = self.audio_router
            if audio_router and audio_router.section_manager.active_sections.get(
                guild.id
            ):
                # Show confirmation dialog for stop
                section = audio_router.section_manager.active_sections.get(guild.id)
                status_text = (
                    "active" if section.is_active else "created but not yet active"
                )

                embed = discord.Embed(
                    title="⚠️ Stop Broadcast Confirmation",
                    description=(
                        f"**The current section '{section.section_name}' will be deleted** (status: {status_text}).\n\n"
                        "**This will:**\n"
                        "• Delete all channels and the category\n"
                        "• Kick everyone from their channels\n"
                        "• Stop all bots and clean up resources\n\n"
                        "**Please do this only if:**\n"
                        "• The broadcast is completely finished\n"
                        "• You want to end the meeting/session\n"
                        "• You need to clean up the channels\n\n"
                        "**Are you sure you want to stop the broadcast?**"
                    ),
                    color=discord.Color.red(),
                )

                async def confirmed_callback(interaction):
                    # Create a context for the callback
                    bot = interaction.client
                    ctx = await bot.get_context(interaction.message)
                    if ctx:
                        await self.stop_broadcast_callback(ctx)

                view = StopBroadcastConfirmationView(confirmed_callback)
                await interaction.response.send_message(
                    embed=embed, view=view, ephemeral=True
                )
            else:
                # No broadcast section exists
                await interaction.response.send_message(
                    "⚠️ No broadcast section found in this server!\n\n"
                    "**To stop a broadcast, you first need to create and start one.**\n"
                    "Use the **Start Broadcast** button to create a new broadcast section.",
                    ephemeral=True,
                )

        except Exception as e:
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        f"❌ Error: {str(e)}", ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        f"❌ Error: {str(e)}", ephemeral=True
                    )
            except Exception:
                pass

    @discord.ui.button(
        label="Setup Settings",
        style=discord.ButtonStyle.secondary,
        emoji="⚙️",
        row=0,
        custom_id="setup_settings",
    )
    async def setup_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Handle setup button click - open comprehensive setup modal."""
        modal = SetupModal(self.settings, self.max_listeners, self._update_all_settings)
        await interaction.response.send_modal(modal)

    async def _update_all_settings(
        self, section_name: str, listener_count: int, role_name: Optional[str]
    ) -> None:
        """Update all settings at once and refresh panel."""
        # This will be implemented by the command handler
        pass


def create_control_panel_embed(
    settings: ControlPanelSettings, is_active: bool = False, max_listeners: int = 1
) -> discord.Embed:
    """Create the control panel embed with modern Discord UI design."""
    # Status styling with better visual hierarchy
    status_emoji = "🔴" if not is_active else "🟢"
    status_text = "OFFLINE" if not is_active else "LIVE"
    status_color = (
        discord.Color.from_rgb(220, 38, 38)
        if not is_active
        else discord.Color.from_rgb(34, 197, 94)
    )

    embed = discord.Embed(
        title="🎛️ Broadcast Control Panel",
        description=f"**Status:** {status_emoji} {status_text}",
        color=status_color,
        timestamp=discord.utils.utcnow(),
    )

    # Configuration section with better visual separation
    embed.add_field(name="⚙️ Configuration", value="", inline=False)

    # Settings with improved formatting and spacing
    embed.add_field(
        name="📝 Section Name", value=f"```{settings.section_name}```", inline=True
    )

    embed.add_field(
        name="🔊 Listener Channels",
        value=f"```{settings.listener_channels}/{max_listeners}```",
        inline=True,
    )

    # Permission Role with better display
    role_display = settings.permission_role or "Everyone"
    role_emoji = "🔒" if settings.permission_role else "🌐"
    embed.add_field(
        name=f"{role_emoji} Access Level", value=f"```{role_display}```", inline=True
    )

    # Control Panel section
    embed.add_field(name="🎮 Control Panel", value="", inline=False)

    # Action descriptions with better formatting
    action_text = (
        "**▶️ Start Broadcast** - Begin audio streaming with current settings\n"
        "**⏹️ Stop Broadcast** - End current broadcast and cleanup\n"
        "**⚙️ Setup Settings** - Configure section name, listeners, and permissions"
    )

    embed.add_field(name="", value=action_text, inline=False)

    # Footer with better information hierarchy
    embed.set_footer(text="💾 Auto-saved • 🔄 Persistent across restarts")

    return embed
