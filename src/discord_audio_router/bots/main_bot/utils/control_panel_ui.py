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


class ControlPanelView(discord.ui.View):
    """Main control panel view with all interactive elements."""

    def __init__(
        self,
        settings: ControlPanelSettings,
        max_listeners: int,
        update_callback: Callable[[], None],
        start_broadcast_callback: Callable[[], None],
        stop_broadcast_callback: Callable[[], None],
    ):
        super().__init__(timeout=None)  # Persistent view
        self.settings = settings
        self.max_listeners = max_listeners
        self.update_callback = update_callback
        self.start_broadcast_callback = start_broadcast_callback
        self.stop_broadcast_callback = stop_broadcast_callback
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
            await interaction.response.defer()

            # Create a context for the command
            bot = interaction.client
            ctx = await bot.get_context(interaction.message)

            if ctx is None:
                await interaction.followup.send(
                    "❌ Failed to create command context", ephemeral=True
                )
                return

            # Call the start broadcast method
            await self.start_broadcast_callback(ctx)

        except Exception as e:
            try:
                await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
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
            await interaction.response.defer()

            # Create a context for the command
            bot = interaction.client
            ctx = await bot.get_context(interaction.message)

            if ctx is None:
                await interaction.followup.send(
                    "❌ Failed to create command context", ephemeral=True
                )
                return

            # Call the stop broadcast method
            await self.stop_broadcast_callback(ctx)

        except Exception as e:
            try:
                await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
            except Exception:
                pass

    @discord.ui.button(
        label="Setup",
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
        "**⚙️ Setup** - Configure section name, listeners, and permissions"
    )

    embed.add_field(name="", value=action_text, inline=False)

    # Footer with better information hierarchy
    embed.set_footer(text="💾 Auto-saved • 🔄 Persistent across restarts")

    return embed
