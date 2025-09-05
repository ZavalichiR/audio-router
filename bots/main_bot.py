"""
Main Discord Audio Router Bot.

This is the main bot file that implements the audio routing system with
proper multi-bot architecture for handling multiple listener channels.
"""

import asyncio
import re
from typing import Optional

import discord
from config.simple_config import config_manager
from core.access_control import is_broadcast_admin
from core.audio_router import AudioRouter
from discord.ext import commands
from logging_config import setup_logging

# Configure logging
logger = setup_logging(
    component_name="main_bot", log_level="INFO", log_file="logs/main_bot.log"
)

# Load configuration
try:
    config = config_manager.get_config()
except Exception as e:
    logger.error(f"Failed to load configuration: {e}")
    exit(1)

# Discord bot setup
intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(
    command_prefix=config.command_prefix, intents=intents, help_command=None
)

# Global audio router instance
audio_router: Optional[AudioRouter] = None


def is_admin():
    """Check if user has administrator permissions."""

    def predicate(ctx: commands.Context) -> bool:
        return ctx.author.guild_permissions.administrator

    return commands.check(predicate)


@bot.event
async def on_ready() -> None:
    """Bot ready event."""
    global audio_router

    logger.info(f"Audio Router Bot online: {bot.user}")

    # Initialize audio router
    try:
        # Pass the existing config directly to the audio router
        audio_router = AudioRouter(config)
        await audio_router.initialize(bot)

        logger.info("Audio router initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize audio router: {e}")

    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} slash commands")
    except Exception as e:
        logger.error(f"Command sync failed: {e}")


@bot.event
async def on_message(message: discord.Message) -> None:
    """Message event handler."""
    if message.author.bot:
        return

    # Process commands
    await bot.process_commands(message)


@bot.event
async def on_command_error(ctx: commands.Context, error: Exception) -> None:
    """Command error handler."""
    try:
        if isinstance(error, commands.CheckFailure):
            embed = discord.Embed(
                description="❌ You need administrator permissions to use this command!",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description=f"❌ Error: {str(error)}", color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            logger.error(f"Command error in {ctx.command}: {error}")
    except discord.NotFound:
        # Channel was deleted, just log the error
        logger.error(f"Command error in {ctx.command}: {error} (channel was deleted)")
    except Exception as send_error:
        # Some other error sending the message
        logger.error(f"Command error in {ctx.command}: {error}")
        logger.error(f"Failed to send error message: {send_error}")


@bot.command(name="setup_broadcast")
@is_broadcast_admin()
async def setup_broadcast_command(ctx: commands.Context, *, args: str) -> None:
    """
    🏗️ Setup a broadcast section with speaker and listener channels.

    This command creates a complete broadcast section including:
    - A category with the specified name
    - One speaker channel for the presenter
    - N listener channels for the audience
    - A control channel for admin commands

    Usage: !setup_broadcast 'Section Name' N
    Example: !setup_broadcast 'War Room' 5

    Args:
        ctx: Discord command context
        args: Command arguments in format "'Section Name' N"

    Note:
        - Section name must be enclosed in single quotes
        - N must be between 1 and 10
        - Requires Administrator permissions
    """
    try:
        if not audio_router:
            embed = discord.Embed(
                title="❌ System Error",
                description="Audio router not initialized. Please restart the bot.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return

        # Parse arguments
        # Expected format: 'Section Name' N
        match = re.match(r"'([^']+)'\s+(\d+)", args.strip())
        if not match:
            embed = discord.Embed(
                title="❌ Invalid Command Format",
                description="Usage: `!setup_broadcast 'Section Name' N`\n"
                "Example: `!setup_broadcast 'War Room' 5`",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return

        section_name = match.group(1)
        listener_count = int(match.group(2))

        # Validate listener count
        if listener_count < 1 or listener_count > 10:
            embed = discord.Embed(
                title="❌ Invalid Listener Count",
                description="Listener count must be between 1 and 10",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return

        # Create broadcast section
        result = await audio_router.create_broadcast_section(
            ctx.guild, section_name, listener_count
        )

        if result["success"]:
            # Use simple message for the original channel
            simple_message = result.get("simple_message", result["message"])
            embed = discord.Embed(
                title="🏗️ Broadcast Section Setup Complete!",
                description=simple_message,
                color=discord.Color.green(),
            )
        else:
            embed = discord.Embed(
                title="❌ Failed to Create Section",
                description=result["message"],
                color=discord.Color.red(),
            )

        await ctx.send(embed=embed)

    except Exception as e:
        logger.error(f"Error in start_broadcast command: {e}")
        embed = discord.Embed(
            title="❌ Command Error",
            description=f"An error occurred: {str(e)}",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)


@bot.command(name="start_broadcast")
@is_broadcast_admin()
async def start_broadcast_command(ctx):
    """🎵 Start audio broadcasting for the current section."""
    try:
        if not audio_router:
            embed = discord.Embed(
                title="❌ System Error",
                description="Audio router not initialized. Please restart the bot.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return

        result = await audio_router.start_broadcast(ctx.guild)

        if result["success"]:
            embed = discord.Embed(
                title="🎵 Broadcast Started!",
                description=result["message"],
                color=discord.Color.green(),
            )
        else:
            embed = discord.Embed(
                title="❌ Failed to Start Broadcast",
                description=result["message"],
                color=discord.Color.red(),
            )

        await ctx.send(embed=embed)

    except Exception as e:
        logger.error(f"Error in start_broadcast command: {e}")
        embed = discord.Embed(
            title="❌ Command Error",
            description=f"An error occurred: {str(e)}",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)


@bot.command(name="stop_broadcast")
@is_broadcast_admin()
async def stop_broadcast_command(ctx):
    """⏹️ Stop audio broadcasting for the current section."""
    try:
        if not audio_router:
            embed = discord.Embed(
                title="❌ System Error",
                description="Audio router not initialized. Please restart the bot.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return

        result = await audio_router.stop_broadcast(ctx.guild)

        if result["success"]:
            embed = discord.Embed(
                title="⏹️ Broadcast Stopped!",
                description=result["message"],
                color=discord.Color.green(),
            )
        else:
            embed = discord.Embed(
                title="❌ Failed to Stop Broadcast",
                description=result["message"],
                color=discord.Color.red(),
            )

        await ctx.send(embed=embed)

    except Exception as e:
        logger.error(f"Error in stop_broadcast command: {e}")
        embed = discord.Embed(
            title="❌ Command Error",
            description=f"An error occurred: {str(e)}",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)


@bot.command(name="broadcast_status")
@is_broadcast_admin()
async def broadcast_status_command(ctx):
    """📊 Get the status of the current broadcast section."""
    try:
        if not audio_router:
            embed = discord.Embed(
                title="❌ System Error",
                description="Audio router not initialized. Please restart the bot.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return

        status = await audio_router.get_section_status(ctx.guild)

        if not status["active"]:
            embed = discord.Embed(
                title="📊 No Active Section",
                description=status["message"],
                color=discord.Color.orange(),
            )
        else:
            embed = discord.Embed(
                title=f"📊 {status['section_name']} Status", color=discord.Color.blue()
            )
            embed.add_field(
                name="🎤 Speaker Channel",
                value=f"<#{status['speaker_channel_id']}>",
                inline=True,
            )
            embed.add_field(
                name="📢 Listener Channels",
                value=f"{status['listener_count']} channels",
                inline=True,
            )
            embed.add_field(
                name="🔴 Broadcasting",
                value="🟢 Active" if status["is_broadcasting"] else "🔴 Inactive",
                inline=True,
            )

        await ctx.send(embed=embed)

    except Exception as e:
        logger.error(f"Error in status command: {e}")
        embed = discord.Embed(
            title="❌ Command Error",
            description=f"An error occurred: {str(e)}",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)


@bot.command(name="cleanup_setup")
@is_broadcast_admin()
async def cleanup_setup_command(ctx):
    """🗑️ Clean up the entire broadcast section."""
    try:
        if not audio_router:
            embed = discord.Embed(
                title="❌ System Error",
                description="Audio router not initialized. Please restart the bot.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return

        # Add confirmation
        embed = discord.Embed(
            title="🗑️ Confirm Setup Cleanup",
            description="This will delete the entire broadcast section and all channels. Are you sure?",
            color=discord.Color.orange(),
        )
        embed.add_field(
            name="This action will:",
            value="• Stop all audio broadcasting\n"
            "• Delete all broadcast channels\n"
            "• Remove the broadcast category\n"
            "• Clean up all resources",
            inline=False,
        )

        await ctx.send(embed=embed)

        # For now, proceed with cleanup (in production, you'd want a proper confirmation system)
        result = await audio_router.cleanup_section(ctx.guild)

        # Send result message to the original channel (not the control channel which may be deleted)
        if result["success"]:
            embed = discord.Embed(
                title="🗑️ Setup Cleaned Up!",
                description=result["message"],
                color=discord.Color.green(),
            )
        else:
            embed = discord.Embed(
                title="❌ Failed to Cleanup Setup",
                description=result["message"],
                color=discord.Color.red(),
            )

        # Try to send to original channel, but handle the case where it might not exist
        try:
            await ctx.send(embed=embed)
        except discord.NotFound:
            # Channel was deleted, log success but don't try to send message
            logger.info(
                "Cleanup completed successfully, but control channel was deleted"
            )
        except Exception as send_error:
            logger.warning(f"Could not send cleanup result message: {send_error}")

    except Exception as e:
        logger.error(f"Error in cleanup_setup command: {e}")
        embed = discord.Embed(
            title="❌ Command Error",
            description=f"An error occurred: {str(e)}",
            color=discord.Color.red(),
        )
        # Try to send error message, but handle case where channel might not exist
        try:
            await ctx.send(embed=embed)
        except discord.NotFound:
            logger.warning(
                "Could not send error message - channel may have been deleted"
            )
        except Exception as send_error:
            logger.warning(f"Could not send error message: {send_error}")


@bot.command(name="create_roles")
@is_admin()
async def create_roles_command(ctx):
    """Create the required roles for the audio router system."""
    try:
        if not audio_router or not hasattr(audio_router, "access_control"):
            embed = discord.Embed(
                title="❌ System Error",
                description="Access control system not available.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return

        # Ensure roles exist
        roles = await audio_router.access_control.ensure_roles_exist(ctx.guild)
        speaker_role = roles.get('speaker_role')
        broadcast_admin_role = roles.get('broadcast_admin_role')

        embed = discord.Embed(
            title="✅ Roles Created/Verified",
            description="Required roles have been created or verified:",
            color=discord.Color.green(),
        )

        if speaker_role:
            embed.add_field(
                name="🎤 Speaker Role",
                value=f"✅ {speaker_role.mention} - Required to join speaker channels",
                inline=False,
            )
        else:
            embed.add_field(
                name="🎤 Speaker Role",
                value="❌ Failed to create speaker role",
                inline=False,
            )

        if broadcast_admin_role:
            embed.add_field(
                name="🎛️ Broadcast Admin Role",
                value=f"✅ {broadcast_admin_role.mention} - Required to use bot commands",
                inline=False,
            )
        else:
            embed.add_field(
                name="🎛️ Broadcast Admin Role",
                value="❌ Failed to create broadcast admin role",
                inline=False,
            )

        embed.add_field(
            name="📝 Next Steps",
            value="• Assign the **Speaker** role to users who should be able to speak\n"
                  "• Assign the **Broadcast Admin** role to users who should control broadcasts\n"
                  "• Create a broadcast section with `!setup_broadcast 'Name' N`",
            inline=False,
        )

        await ctx.send(embed=embed)

    except Exception as e:
        logger.error(f"Error in create_roles command: {e}")
        embed = discord.Embed(
            title="❌ Command Error",
            description=f"An error occurred: {str(e)}",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)


@bot.command(name="check_setup")
@is_broadcast_admin()
async def check_setup_command(ctx, *, section_name: str):
    """🔍 Check if a broadcast section already exists."""
    try:
        if not audio_router:
            embed = discord.Embed(
                title="❌ System Error",
                description="Audio router not initialized. Please restart the bot.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return

        # Check if section exists in active sections
        if ctx.guild.id in audio_router.section_manager.active_sections:
            section = audio_router.section_manager.active_sections[ctx.guild.id]
            embed = discord.Embed(
                title="✅ Active Section Found",
                description=f"Section '{section.section_name}' is currently active.",
                color=discord.Color.green(),
            )
            embed.add_field(
                name="Status",
                value="🟢 Active" if section.is_active else "🔴 Inactive",
                inline=True,
            )
            embed.add_field(
                name="Listener Channels",
                value=f"{len(section.listener_channel_ids)}",
                inline=True,
            )
        else:
            # Check if category exists
            existing_category = discord.utils.get(
                ctx.guild.categories, name=section_name
            )
            if existing_category:
                embed = discord.Embed(
                    title="⚠️ Category Exists",
                    description=f"A category named '{section_name}' already exists but is not managed by the bot.",
                    color=discord.Color.orange(),
                )
                embed.add_field(
                    name="Recommendation",
                    value="Either delete the existing category or use a different name.",
                    inline=False,
                )
            else:
                embed = discord.Embed(
                    title="✅ Section Available",
                    description=f"No section named '{section_name}' exists. You can create it!",
                    color=discord.Color.green(),
                )

        await ctx.send(embed=embed)

    except Exception as e:
        logger.error(f"Error in check_setup command: {e}")
        embed = discord.Embed(
            title="❌ Command Error",
            description=f"An error occurred: {str(e)}",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)


@bot.command(name="fix_permissions")
@is_admin()
async def fix_permissions_command(ctx):
    """Get step-by-step instructions to fix bot permissions."""
    try:
        bot_member = ctx.guild.me

        embed = discord.Embed(
            title="🔧 How to Fix Bot Permissions",
            description="Follow these steps to give your bot the permissions it needs:",
            color=discord.Color.orange(),
        )

        # Check current permissions
        has_manage_channels = bot_member.guild_permissions.manage_channels
        has_manage_roles = bot_member.guild_permissions.manage_roles
        has_administrator = bot_member.guild_permissions.administrator

        steps = []

        if not has_administrator and (not has_manage_channels or not has_manage_roles):
            steps.append("**Option 1: Grant Administrator Permission (Recommended)**")
            steps.append("1. Go to Server Settings ⚙️")
            steps.append("2. Click on 'Roles' in the left sidebar")
            steps.append("3. Find your bot's role (usually named after your bot)")
            steps.append("4. Click on the bot's role")
            steps.append("5. Scroll down and enable 'Administrator' permission")
            steps.append("6. Click 'Save Changes'")
            steps.append("")
            steps.append("**Option 2: Grant Specific Permissions**")
            steps.append("1. Go to Server Settings ⚙️")
            steps.append("2. Click on 'Roles' in the left sidebar")
            steps.append("3. Find your bot's role")
            steps.append("4. Enable these permissions:")
            if not has_manage_channels:
                steps.append("   • ✅ Manage Channels")
            if not has_manage_roles:
                steps.append("   • ✅ Manage Roles")
            steps.append("   • ✅ Send Messages")
            steps.append("   • ✅ Read Message History")
            steps.append("   • ✅ Connect (for voice)")
            steps.append("   • ✅ Speak (for voice)")
            steps.append("5. Click 'Save Changes'")
        else:
            steps.append("✅ Your bot already has sufficient permissions!")
            steps.append("If you're still having issues, try:")
            steps.append("1. Moving the bot's role higher in the role hierarchy")
            steps.append("2. Re-inviting the bot with a fresh invite link")

        steps.append("")
        steps.append("**After fixing permissions:**")
        steps.append("• Run `!check_permissions` to verify")
        steps.append("• Try `!start_broadcast 'Test Room' 3` again")

        embed.add_field(name="📋 Instructions", value="\n".join(steps), inline=False)

        # Add invite link generation info
        embed.add_field(
            name="🔗 Need a New Invite Link?",
            value="1. Go to [Discord Developer Portal](https://discord.com/developers/applications)\n"
            "2. Select your application\n"
            "3. Go to OAuth2 > URL Generator\n"
            "4. Select 'bot' scope\n"
            "5. Select 'Administrator' permission\n"
            "6. Copy the generated URL and use it to re-invite your bot",
            inline=False,
        )

        await ctx.send(embed=embed)

    except Exception as e:
        logger.error(f"Error in fix_permissions command: {e}")
        embed = discord.Embed(
            title="❌ Command Error",
            description=f"An error occurred: {str(e)}",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)


@bot.command(name="check_permissions")
@is_admin()
async def check_permissions_command(ctx):
    """Check bot permissions and role hierarchy."""
    try:
        bot_member = ctx.guild.me

        embed = discord.Embed(
            title="🔍 Bot Permission Check", color=discord.Color.blue()
        )

        # Check essential permissions
        permissions = [
            ("Manage Channels", bot_member.guild_permissions.manage_channels),
            ("Manage Roles", bot_member.guild_permissions.manage_roles),
            ("Connect", bot_member.guild_permissions.connect),
            ("Speak", bot_member.guild_permissions.speak),
            ("Send Messages", bot_member.guild_permissions.send_messages),
            ("Read Message History", bot_member.guild_permissions.read_message_history),
            ("Embed Links", bot_member.guild_permissions.embed_links),
            ("Administrator", bot_member.guild_permissions.administrator),
        ]

        permission_status = []
        for perm_name, has_perm in permissions:
            status = "✅" if has_perm else "❌"
            permission_status.append(f"{status} {perm_name}")

        embed.add_field(
            name="📋 Bot Permissions", value="\n".join(permission_status), inline=False
        )

        # Check role hierarchy
        embed.add_field(
            name="👑 Bot Role Hierarchy",
            value=f"Bot's highest role: {bot_member.top_role.name} (Position: {bot_member.top_role.position})",
            inline=False,
        )

        # Check if bot can manage other roles
        manageable_roles = []
        for role in ctx.guild.roles:
            if role != ctx.guild.default_role and bot_member.top_role > role:
                manageable_roles.append(f"✅ {role.name}")
            elif role != ctx.guild.default_role:
                manageable_roles.append(f"❌ {role.name} (too high)")

        if manageable_roles:
            embed.add_field(
                name="🎭 Role Management",
                value="\n".join(manageable_roles[:10])
                + ("\n..." if len(manageable_roles) > 10 else ""),
                inline=False,
            )

        # Recommendations
        recommendations = []
        if not bot_member.guild_permissions.manage_channels:
            recommendations.append("• Grant 'Manage Channels' permission")
        if not bot_member.guild_permissions.manage_roles:
            recommendations.append("• Grant 'Manage Roles' permission")
        if bot_member.top_role.position < 5:
            recommendations.append("• Move bot role higher in hierarchy")

        if recommendations:
            embed.add_field(
                name="💡 Recommendations",
                value="\n".join(recommendations),
                inline=False,
            )
        else:
            embed.add_field(
                name="✅ Status", value="Bot has sufficient permissions!", inline=False
            )

        await ctx.send(embed=embed)

    except Exception as e:
        logger.error(f"Error in check_permissions command: {e}")
        embed = discord.Embed(
            title="❌ Command Error",
            description=f"An error occurred: {str(e)}",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)


@bot.command(name="role_info")
@is_broadcast_admin()
async def role_info_command(ctx):
    """Show information about the audio router roles."""
    try:
        if not audio_router or not hasattr(audio_router, "access_control"):
            embed = discord.Embed(
                title="❌ System Error",
                description="Access control system not available.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return

        # Get role information
        speaker_role = discord.utils.get(ctx.guild.roles, name=audio_router.access_control.speaker_role_name)
        broadcast_admin_role = discord.utils.get(ctx.guild.roles, name=audio_router.access_control.broadcast_admin_role_name)

        embed = discord.Embed(
            title="👥 Audio Router Role Information",
            description="Information about the roles used by the audio router system:",
            color=discord.Color.blue(),
        )

        # Speaker role info
        if speaker_role:
            speaker_members = [member for member in ctx.guild.members if speaker_role in member.roles]
            embed.add_field(
                name="🎤 Speaker Role",
                value=f"**Role:** {speaker_role.mention}\n"
                      f"**Purpose:** Required to join speaker channels\n"
                      f"**Members:** {len(speaker_members)} users",
                inline=False,
            )
        else:
            embed.add_field(
                name="🎤 Speaker Role",
                value=f"**Role:** {audio_router.access_control.speaker_role_name} (not found)\n"
                      f"**Purpose:** Required to join speaker channels\n"
                      f"**Action:** Use `!create_roles` to create this role",
                inline=False,
            )

        # Broadcast admin role info
        if broadcast_admin_role:
            admin_members = [member for member in ctx.guild.members if broadcast_admin_role in member.roles]
            embed.add_field(
                name="🎛️ Broadcast Admin Role",
                value=f"**Role:** {broadcast_admin_role.mention}\n"
                      f"**Purpose:** Required to use bot commands\n"
                      f"**Members:** {len(admin_members)} users",
                inline=False,
            )
        else:
            embed.add_field(
                name="🎛️ Broadcast Admin Role",
                value=f"**Role:** {audio_router.access_control.broadcast_admin_role_name} (not found)\n"
                      f"**Purpose:** Required to use bot commands\n"
                      f"**Action:** Use `!create_roles` to create this role",
                inline=False,
            )

        embed.add_field(
            name="📝 How to Use",
            value="• **Listeners:** Anyone can join listener channels and speak (no role required)\n"
                  "• **Speakers:** Must have the Speaker role to join speaker channels\n"
                  "• **Admins:** Must have the Broadcast Admin role to use bot commands\n"
                  "• **Server Admins:** Can always use bot commands and join any channel",
            inline=False,
        )

        await ctx.send(embed=embed)

    except Exception as e:
        logger.error(f"Error in role_info command: {e}")
        embed = discord.Embed(
            title="❌ Command Error",
            description=f"An error occurred: {str(e)}",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)


@bot.command(name="system_status")
@is_broadcast_admin()
async def system_status_command(ctx):
    """🔍 Get detailed system status including all bot processes."""
    try:
        if not audio_router:
            embed = discord.Embed(
                title="❌ System Error",
                description="Audio router not initialized. Please restart the bot.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return

        # Get system status
        status = await audio_router.get_system_status()

        embed = discord.Embed(title="🔍 System Status", color=discord.Color.blue())

        # Active sections
        embed.add_field(
            name="📊 Active Sections",
            value=f"{status['active_sections']} sections",
            inline=True,
        )

        # Process status
        process_status = status["process_status"]
        embed.add_field(
            name="🤖 Bot Processes",
            value=f"{process_status['total_processes']} running",
            inline=True,
        )

        embed.add_field(
            name="🎫 Token Status",
            value=f"{status['available_tokens']} available, {status['used_tokens']} used",
            inline=True,
        )

        # Detailed process information
        if process_status["processes"]:
            process_info = []
            for bot_id, bot_status in process_status["processes"].items():
                status_emoji = "🟢" if bot_status["is_alive"] else "🔴"
                process_info.append(
                    f"{status_emoji} **{bot_id}**\n"
                    f"   Type: {bot_status['bot_type']}\n"
                    f"   Channel: <#{bot_status['channel_id']}>\n"
                    f"   PID: {bot_status['pid']}\n"
                    f"   Uptime: {bot_status['uptime']:.1f}s"
                )

            embed.add_field(
                name="📋 Process Details", value="\n\n".join(process_info), inline=False
            )

        await ctx.send(embed=embed)

    except Exception as e:
        logger.error(f"Error in system_status command: {e}")
        embed = discord.Embed(
            title="❌ Command Error",
            description=f"An error occurred: {str(e)}",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)


@bot.command(name="help_audio_router")
@is_admin()
async def help_command(ctx):
    """Show admin-only help and setup tutorial for the Audio Router Bot."""
    embed = discord.Embed(
        title="🎵 Audio Router Bot - Admin Setup Guide",
        description="**Welcome to the Audio Router Bot!** This guide will help you set up the system step by step.",
        color=discord.Color.blue(),
    )

    # Check if roles exist
    speaker_role = discord.utils.get(ctx.guild.roles, name="Speaker")
    broadcast_admin_role = discord.utils.get(ctx.guild.roles, name="Broadcast Admin")
    
    # Step 1: Create roles
    embed.add_field(
        name="📋 Step 1: Create Required Roles",
        value="**First, you need to create the required roles:**\n"
        f"• **Speaker Role:** {'✅ Exists' if speaker_role else '❌ Missing'}\n"
        f"• **Broadcast Admin Role:** {'✅ Exists' if broadcast_admin_role else '❌ Missing'}\n\n"
        "**Action Required:** Run `!create_roles` to create missing roles",
        inline=False,
    )

    # Step 2: Assign roles
    embed.add_field(
        name="👥 Step 2: Assign Roles to Users",
        value="**After creating roles, assign them to users:**\n"
        "• Give **Speaker** role to users who should be able to speak in broadcasts\n"
        "• Give **Broadcast Admin** role to users who should control broadcasts\n"
        "• Server administrators can always use bot commands",
        inline=False,
    )

    # Step 3: Create broadcast section
    embed.add_field(
        name="🏗️ Step 3: Create Your First Broadcast Section",
        value="**Create a broadcast section with:**\n"
        "• `!setup_broadcast 'Section Name' N`\n"
        "• Example: `!setup_broadcast 'War Room' 5`\n"
        "• This creates 1 Speaker channel + 5 Listener channels",
        inline=False,
    )

    # Step 4: Start broadcasting
    embed.add_field(
        name="🎵 Step 4: Start Broadcasting",
        value="**Once your section is created:**\n"
        "• Go to the control channel that was created\n"
        "• Run `!start_broadcast` to begin audio forwarding\n"
        "• Users with Speaker role can join the Speaker channel\n"
        "• Everyone else can join Listener channels",
        inline=False,
    )

    # Quick commands reference
    embed.add_field(
        name="⚡ Quick Commands Reference",
        value="• `!create_roles` - Create required roles\n"
        "• `!setup_broadcast 'Name' N` - Create broadcast section\n"
        "• `!start_broadcast` - Start audio forwarding\n"
        "• `!stop_broadcast` - Stop audio forwarding\n"
        "• `!broadcast_status` - Check status\n"
        "• `!role_info` - Show role information",
        inline=False,
    )

    # System explanation
    embed.add_field(
        name="🔧 How the System Works",
        value="• **Speaker Channel:** Only users with Speaker role can join\n"
        "• **Listener Channels:** Everyone can join and speak freely\n"
        "• **Control Channel:** Only Broadcast Admin role can access\n"
        "• **Audio Flow:** Speaker channel audio is forwarded to all listener channels",
        inline=False,
    )

    # Next steps based on current state
    if not speaker_role or not broadcast_admin_role:
        embed.add_field(
            name="🚀 Next Step",
            value="**Run `!create_roles` to get started!**",
            inline=False,
        )
    else:
        embed.add_field(
            name="🚀 Next Step",
            value="**You're ready! Run `!setup_broadcast 'Test Room' 3` to create your first broadcast section.**",
            inline=False,
        )

    embed.set_footer(text="This help command is only visible to server administrators")
    await ctx.send(embed=embed)


# Initialize and run the bot
async def main():
    """Main function to initialize and run the bot."""
    try:
        logger.info("Starting Audio Router Bot...")
        await bot.start(config.main_bot_token)
    except Exception as e:
        logger.critical(f"Failed to start Audio Router Bot: {e}")
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot shutdown requested")
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        raise
