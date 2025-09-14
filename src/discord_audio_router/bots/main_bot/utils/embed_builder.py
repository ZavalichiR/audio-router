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
            title="📖 Audio Router Bot - Commands",
            description="Transform your Discord server into a professional broadcasting platform!",
            color=discord.Color.blue(),
        )

        embed.add_field(
            name="🚀 Quick Start Guide",
            value="1. **Setup Roles:** `!setup_roles` - Set up required roles\n"
            "2. **Check Subscription:** `!subscription_status` - Ensure you have the needed subscription\n"
            "3. **Check Bots:** `!bot_status` - Ensure you have all bots installed\n"
            "4. **Start Broadcast:** `!start_broadcast 'Room Name' [N]` - Start broadcast with proper parameters\n"
            "5. **Learn More:** Use `!how_it_works` to learn about this bot",
            inline=False,
        )

        embed.add_field(
            name="🎤 Broadcast Commands",
            value="• `!start_broadcast 'Name' [N]` - Start a new broadcast section (visible to everyone)\n"
            "• `!start_broadcast 'Name' [N] --role 'RoleName'` - Start broadcast visible only to specified role\n"
            "• `!stop_broadcast` - Stop and clean up current broadcast\n"
            "• `!control_panel` - Open interactive control panel for easy broadcast management",
            inline=False,
        )

        embed.add_field(
            name="ℹ️ Information",
            value="• `!how_it_works` - Understand the audio routing system",
            inline=False,
        )

        embed.set_footer(text="Need help? Run !how_it_works for a detailed explanation")
        return embed

    @staticmethod
    def how_it_works() -> discord.Embed:
        """Create the how it works explanation embed."""
        embed = discord.Embed(
            title="🔧 How the Audio Router System Works",
            description="Learn how the audio routing system functions and how to use it effectively:",
            color=discord.Color.green(),
        )

        embed.add_field(
            name="🎤 Speaker Channels",
            value="• Only users with the **Speaker** role (configured in your server) can join\n"
            "• Audio from speakers is captured and forwarded to listener channels\n"
            "• Speakers can hear each other normally within the speaker channel",
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
            name="🎛️ Broadcast Control",
            value="• Only users with **Broadcast Admin** role (configured in your server) can use bot commands\n"
            "• Commands like `!start_broadcast` and `!stop_broadcast` require this role\n"
            "• Server administrators can always use all commands regardless of roles",
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
            value="• **Broadcast Admin Role:** Required to use bot commands (start/stop broadcasts)\n"
            "• **Speaker Role:** Required to join speaker channels and broadcast audio\n"
            "• **Listener Role:** Optional role for organizing listeners (can join listener channels)\n"
            "• **Server Administrators:** Can always use all commands and join any channel\n"
            "• **Everyone Else:** Can join listener channels freely (no role required)\n"
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
            "  •    `!start_broadcast 'Public Event' 5` (everyone can see)\n"
            "  •    `!start_broadcast 'VIP Session' 3 --role 'Premium'` (only Premium role can see)\n"
            "• **Perfect for:** VIP content, member-only events, private sessions",
            inline=False,
        )

        embed.add_field(
            name="🚀 Getting Started",
            value="1. **Setup Roles:** Run `!setup_roles` to create required roles\n"
            "2. **Check Subscription:** Run `!subscription_status` to verify your tier\n"
            "3. **Check Bots:** Run `!bot_status` to ensure receiver bots are installed\n"
            "4. **Start Broadcast:** Run `!start_broadcast 'Room Name' [N]` to create your first broadcast\n"
            "5. **Assign Roles:** Give users the appropriate roles to join channels",
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

        embed.set_footer(
            text="Get started: Run !setup_roles → !subscription_status → !bot_status → !start_broadcast"
        )
        return embed
