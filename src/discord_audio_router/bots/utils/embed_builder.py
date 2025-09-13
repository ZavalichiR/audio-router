"""
Utility class for building Discord embeds consistently.

This module provides a centralized way to create Discord embeds with
consistent styling and formatting across the bot.
"""

import discord


class EmbedBuilder:
    """Utility class for building Discord embeds with consistent styling."""

    @staticmethod
    def success(title: str, description: str, **kwargs) -> discord.Embed:
        """Create a success embed (green)."""
        return discord.Embed(
            title=title, description=description, color=discord.Color.green(), **kwargs
        )

    @staticmethod
    def error(title: str, description: str, **kwargs) -> discord.Embed:
        """Create an error embed (red)."""
        return discord.Embed(
            title=title, description=description, color=discord.Color.red(), **kwargs
        )

    @staticmethod
    def warning(title: str, description: str, **kwargs) -> discord.Embed:
        """Create a warning embed (orange)."""
        return discord.Embed(
            title=title, description=description, color=discord.Color.orange(), **kwargs
        )

    @staticmethod
    def info(title: str, description: str, **kwargs) -> discord.Embed:
        """Create an info embed (blue)."""
        return discord.Embed(
            title=title, description=description, color=discord.Color.blue(), **kwargs
        )

    @staticmethod
    def subscription_error(validation_message: str) -> discord.Embed:
        """Create a subscription error embed."""
        return discord.Embed(
            title="💎 Upgrade Your Subscription",
            description=f"{validation_message}\n\n**Need more listeners?** Contact **zavalichir** or visit our website to upgrade your subscription tier!",
            color=discord.Color.orange(),
        )

    @staticmethod
    def system_starting() -> discord.Embed:
        """Create a system starting embed."""
        return discord.Embed(
            title="⚠️ System Starting Up",
            description="The audio router is still initializing. Please wait a moment and try again.\n\nIf this persists, contact the bot administrator.",
            color=discord.Color.orange(),
        )

    @staticmethod
    def no_permission() -> discord.Embed:
        """Create a no permission embed."""
        return discord.Embed(
            description="❌ You don't have permission to use this command! You need either administrator permissions or the Broadcast Admin role.",
            color=discord.Color.red(),
        )

    @staticmethod
    def command_error(error_message: str) -> discord.Embed:
        """Create a command error embed."""
        return discord.Embed(
            description=f"❌ Error: {error_message}",
            color=discord.Color.red(),
        )

    @staticmethod
    def help_command() -> discord.Embed:
        """Create the main help command embed."""
        embed = discord.Embed(
            title="🎵 Audio Router Bot - Commands",
            description="Transform your Discord server into a professional broadcasting platform!",
            color=discord.Color.blue(),
        )

        embed.add_field(
            name="🚀 Quick Start Guide",
            value="1. **Check Setup:** `!check_setup` - See what's needed\n"
            "2. **Create Roles:** `!setup_roles` - Set up required roles\n"
            "3. **Start Broadcast:** `!start_broadcast 'Room Name'` - Create your first broadcast\n"
            "4. **Optional:** Add `--role 'RoleName'` to restrict category visibility\n"
            "5. **Stop When Done:** `!stop_broadcast` - Clean up everything",
            inline=False,
        )

        embed.add_field(
            name="🎤 Broadcast Commands",
            value="• `!start_broadcast 'Name' [N]` - Start a new broadcast section (visible to everyone)\n"
            "• `!start_broadcast 'Name' [N] --role 'RoleName'` - Start broadcast visible only to specified role\n"
            "• `!stop_broadcast` - Stop and clean up current broadcast\n"
            "• `!broadcast_status` - Check current broadcast status",
            inline=False,
        )

        embed.add_field(
            name="⚙️ Setup & Management",
            value="• `!check_setup` - Verify your server is ready\n"
            "• `!setup_roles` - Create required roles\n"
            "• `!check_permissions` - Fix bot permission issues\n"
            "• `!bot_status` - Check installed receiver bots",
            inline=False,
        )

        embed.add_field(
            name="ℹ️ Information",
            value="• `!subscription_status` - Check your subscription tier\n"
            "• `!role_info` - Learn about roles and permissions\n"
            "• `!how_it_works` - Understand the audio routing system",
            inline=False,
        )

        embed.set_footer(text="Need help? Run !how_it_works for a detailed explanation")
        return embed

    @staticmethod
    def how_it_works() -> discord.Embed:
        """Create the how it works explanation embed."""
        embed = discord.Embed(
            title="🔧 How the Audio Router System Works",
            description="Learn how the audio routing system functions:",
            color=discord.Color.green(),
        )

        embed.add_field(
            name="🎤 Speaker Channels",
            value="• Only users with the **Speaker** role can join\n"
            "• Audio from speakers is captured and forwarded\n"
            "• Speakers can hear each other normally",
            inline=False,
        )

        embed.add_field(
            name="📢 Listener Channels",
            value="• Anyone can join listener channels\n"
            "• Listeners receive audio from speaker channels\n"
            "• Listeners can speak to each other in their channel\n"
            "• Multiple listener channels can receive the same speaker audio",
            inline=False,
        )

        embed.add_field(
            name="🎛️ Control Channels",
            value="• Only users with **Broadcast Admin** role can access\n"
            "• Used to start/stop broadcasts and manage the system\n"
            "• Contains setup instructions and status information",
            inline=False,
        )

        embed.add_field(
            name="🔄 Audio Flow",
            value="1. **Speaker** joins speaker channel and talks\n"
            "2. Audio is captured by the AudioForwarder bot\n"
            "3. Audio is forwarded to all listener channels\n"
            "4. **Listeners** in their channels hear the speaker\n"
            "5. Listeners can respond to each other in their channel",
            inline=False,
        )

        embed.add_field(
            name="👥 Role System",
            value="• **Speaker Role:** Required to join speaker channels\n"
            "• **Broadcast Admin Role:** Required to use bot commands\n"
            "• **Server Administrators:** Can always use all commands\n"
            "• **Everyone Else:** Can join listener channels freely\n"
            "• **Category Visibility:** Use `--role 'RoleName'` to restrict who can see broadcast categories",
            inline=False,
        )

        embed.add_field(
            name="🏗️ Broadcast Sections",
            value="• Each section has 1 speaker channel + multiple listener channels\n"
            "• Sections are organized in Discord categories\n"
            "• You can have multiple sections for different events\n"
            "• Each section operates independently",
            inline=False,
        )

        embed.add_field(
            name="🔒 Category Visibility Control",
            value="• **Default:** Categories are visible to everyone\n"
            "• **Restricted:** Use `--role 'RoleName'` to limit visibility\n"
            "• **Examples:**\n"
            "  - `!start_broadcast 'Public Event' 5` (everyone can see)\n"
            "  - `!start_broadcast 'VIP Session' 3 --role 'Premium'` (only Premium role can see)\n"
            "• **Perfect for:** VIP content, member-only events, private sessions",
            inline=False,
        )

        embed.add_field(
            name="💎 Subscription System",
            value="• **Free Tier:** 1 listener channel - Basic functionality\n"
            "• **Basic Tier:** 2 listener channels - Trial tier\n"
            "• **Standard Tier:** 6 listener channels - Small communities\n"
            "• **Advanced Tier:** 12 listener channels - Medium communities (request via email)\n"
            "• **Premium Tier:** 24 listener channels - Large communities (request via email)\n"
            "• **Custom Tier:** Unlimited listeners - Custom features (request via DM or email)\n"
            "• Use `!subscription_status` to check your current tier",
            inline=False,
        )

        embed.set_footer(text="Run !check_setup to see if your server is ready")
        return embed
