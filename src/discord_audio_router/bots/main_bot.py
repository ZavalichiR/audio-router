"""
AudioBroadcast Discord Bot - Main Control Bot for Audio Router System.

This is the main control bot that implements the audio routing system with
proper multi-bot architecture for handling multiple listener channels.
"""

import asyncio
import re
import sys
from pathlib import Path
from typing import Optional

# Add src directory to Python path for direct execution
if __name__ == "__main__":
    src_path = Path(__file__).parent.parent.parent.parent / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

import discord
from discord.ext import commands

from discord_audio_router.config.settings import config_manager

from discord_audio_router.core import AudioRouter, is_broadcast_admin
from discord_audio_router.infrastructure import setup_logging

# Configure logging
logger = setup_logging(
    component_name="main_bot",
    log_file="logs/main_bot.log",
)

# Load configuration
try:
    config = config_manager.get_config()
except Exception as e:
    logger.error(f"Failed to load configuration: {e}", exc_info=True)
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


def get_broadcast_admin_decorator():
    """Get the broadcast admin decorator with the correct role name."""
    if audio_router and hasattr(audio_router, "access_control"):
        role_name = audio_router.access_control.broadcast_admin_role_name
    else:
        role_name = "Broadcast Admin"  # Default fallback
    
    return is_broadcast_admin(role_name)


@bot.event
async def on_ready() -> None:
    """Bot ready event."""
    global audio_router

    logger.info(f"AudioBroadcast Bot online: {bot.user}")

    # Initialize audio router
    try:
        # Pass the existing config directly to the audio router
        audio_router = AudioRouter(config)
        await audio_router.initialize(bot)

        logger.info("Audio router initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize audio router: {e}", exc_info=True)

    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} slash commands")
    except Exception as e:
        logger.error(f"Command sync failed: {e}", exc_info=True)


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
                description="❌ You don't have permission to use this command! You need either administrator permissions or the Broadcast Admin role.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description=f"❌ Error: {str(error)}",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            logger.error(f"Command error in {ctx.command}: {error}")
    except discord.NotFound:
        # Channel was deleted, just log the error
        logger.error(
            f"Command error in {ctx.command}: {error} (channel was deleted)"
        )
    except Exception as send_error:
        # Some other error sending the message
        logger.error(f"Command error in {ctx.command}: {error}")
        logger.error(f"Failed to send error message: {send_error}")


@bot.command(name="setup_broadcast")
@get_broadcast_admin_decorator()
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
        logger.error(f"Error in start_broadcast command: {e}", exc_info=True)
        embed = discord.Embed(
            title="❌ Command Error",
            description=f"An error occurred: {str(e)}",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)


@bot.command(name="start_broadcast")
@get_broadcast_admin_decorator()
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
        logger.error(f"Error in start_broadcast command: {e}", exc_info=True)
        embed = discord.Embed(
            title="❌ Command Error",
            description=f"An error occurred: {str(e)}",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)


@bot.command(name="stop_broadcast")
@get_broadcast_admin_decorator()
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
        logger.error(f"Error in stop_broadcast command: {e}", exc_info=True)
        embed = discord.Embed(
            title="❌ Command Error",
            description=f"An error occurred: {str(e)}",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)


@bot.command(name="broadcast_status")
@get_broadcast_admin_decorator()
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
                title=f"📊 {status['section_name']} Status",
                color=discord.Color.blue(),
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
                value=(
                    "🟢 Active" if status["is_broadcasting"] else "🔴 Inactive"
                ),
                inline=True,
            )

        await ctx.send(embed=embed)

    except Exception as e:
        logger.error(f"Error in status command: {e}", exc_info=True)
        embed = discord.Embed(
            title="❌ Command Error",
            description=f"An error occurred: {str(e)}",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)


@bot.command(name="cleanup_setup")
@get_broadcast_admin_decorator()
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
            logger.warning(
                f"Could not send cleanup result message: {send_error}"
            )

    except Exception as e:
        logger.error(f"Error in cleanup_setup command: {e}", exc_info=True)
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


@bot.command(name="setup_roles")
@is_admin()
async def setup_roles_command(ctx):
    """Create and configure the required roles for the audio router system."""
    try:
        if not audio_router or not hasattr(audio_router, "access_control"):
            embed = discord.Embed(
                title="❌ System Error",
                description="Access control system not available.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(
            title="🔧 Setting Up Roles",
            description="Creating and configuring required roles...",
            color=discord.Color.blue(),
        )
        await ctx.send(embed=embed)

        # Ensure roles exist
        roles = await audio_router.access_control.ensure_roles_exist(ctx.guild)
        speaker_role = roles.get("speaker_role")
        broadcast_admin_role = roles.get("broadcast_admin_role")

        # Check if we need to move roles in hierarchy
        bot_member = ctx.guild.me
        bot_role = bot_member.top_role
        
        # Determine optimal role positions
        roles_to_move = []
        
        if speaker_role and speaker_role.position >= bot_role.position:
            roles_to_move.append(("Speaker", speaker_role))
        
        if broadcast_admin_role and broadcast_admin_role.position >= bot_role.position:
            roles_to_move.append(("Broadcast Admin", broadcast_admin_role))

        # Move roles if needed
        if roles_to_move:
            try:
                # Find a good position for the roles (below bot role)
                target_position = max(0, bot_role.position - 1)
                
                for role_name, role in roles_to_move:
                    if role.position >= bot_role.position:
                        await role.edit(position=target_position)
                        logger.info(f"Moved {role_name} role to position {target_position}")
                        target_position -= 1
                        
            except discord.Forbidden:
                logger.warning("Could not move roles - insufficient permissions")
            except Exception as e:
                logger.error(f"Error moving roles: {e}", exc_info=True)

        # Create result embed
        result_embed = discord.Embed(
            title="✅ Role Setup Complete",
            description="Required roles have been created and configured:",
            color=discord.Color.green(),
        )

        if speaker_role:
            member_count = len([m for m in ctx.guild.members if speaker_role in m.roles])
            result_embed.add_field(
                name="🎤 Speaker Role",
                value=f"✅ {speaker_role.mention}\n"
                      f"**Purpose:** Required to join speaker channels\n"
                      f"**Members:** {member_count} users\n"
                      f"**Position:** {speaker_role.position}",
                inline=False,
            )
        else:
            result_embed.add_field(
                name="🎤 Speaker Role",
                value="❌ Failed to create speaker role",
                inline=False,
            )

        if broadcast_admin_role:
            member_count = len([m for m in ctx.guild.members if broadcast_admin_role in m.roles])
            result_embed.add_field(
                name="🎛️ Broadcast Admin Role",
                value=f"✅ {broadcast_admin_role.mention}\n"
                      f"**Purpose:** Required to use bot commands\n"
                      f"**Members:** {member_count} users\n"
                      f"**Position:** {broadcast_admin_role.position}",
                inline=False,
            )
        else:
            result_embed.add_field(
                name="🎛️ Broadcast Admin Role",
                value="❌ Failed to create broadcast admin role",
                inline=False,
            )

        # Role hierarchy info
        if roles_to_move:
            result_embed.add_field(
                name="📊 Role Hierarchy",
                value="✅ Roles have been positioned correctly in the hierarchy\n"
                      "✅ Bot can now manage these roles properly",
                inline=False,
            )
        else:
            result_embed.add_field(
                name="📊 Role Hierarchy",
                value="✅ Roles are already positioned correctly",
                inline=False,
            )

        # Next steps
        if speaker_role and broadcast_admin_role:
            result_embed.add_field(
                name="📝 Next Steps",
                value="1. **Assign Roles:** Give users the appropriate roles\n"
                      "2. **Test Setup:** Run `!check_setup` to verify everything\n"
                      "3. **Create Section:** Run `!setup_broadcast 'Test Room' 3`\n"
                      "4. **Learn More:** Run `!how_it_works` for usage guide",
                inline=False,
            )
        else:
            result_embed.add_field(
                name="⚠️ Issues Found",
                value="Some roles could not be created. Check bot permissions with `!check_permissions`",
                inline=False,
            )
            result_embed.color = discord.Color.orange()

        await ctx.send(embed=result_embed)

    except Exception as e:
        logger.error(f"Error in setup_roles command: {e}", exc_info=True)
        embed = discord.Embed(
            title="❌ Command Error",
            description=f"An error occurred: {str(e)}",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)


@bot.command(name="check_setup")
async def check_setup_command(ctx):
    """🔍 Check if your server is properly configured for the Audio Router Bot."""
    try:
        if not audio_router:
            embed = discord.Embed(
                title="❌ System Error",
                description="Audio router not initialized. Please restart the bot.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(
            title="🔍 Server Setup Check",
            description="Checking your server configuration...",
            color=discord.Color.blue(),
        )

        # Check bot permissions
        bot_member = ctx.guild.me
        has_manage_channels = bot_member.guild_permissions.manage_channels
        has_manage_roles = bot_member.guild_permissions.manage_roles
        has_administrator = bot_member.guild_permissions.administrator
        has_connect = bot_member.guild_permissions.connect
        has_speak = bot_member.guild_permissions.speak

        # Check roles
        speaker_role = discord.utils.get(ctx.guild.roles, name="Speaker")
        broadcast_admin_role = discord.utils.get(ctx.guild.roles, name="Broadcast Admin")

        # Check active sections
        has_active_section = ctx.guild.id in audio_router.section_manager.active_sections

        # Permission status
        permission_status = []
        if has_administrator:
            permission_status.append("✅ Administrator (Full Access)")
        else:
            if has_manage_channels:
                permission_status.append("✅ Manage Channels")
            else:
                permission_status.append("❌ Manage Channels")
            
            if has_manage_roles:
                permission_status.append("✅ Manage Roles")
            else:
                permission_status.append("❌ Manage Roles")
            
            if has_connect:
                permission_status.append("✅ Connect (Voice)")
            else:
                permission_status.append("❌ Connect (Voice)")
            
            if has_speak:
                permission_status.append("✅ Speak (Voice)")
            else:
                permission_status.append("❌ Speak (Voice)")

        embed.add_field(
            name="🤖 Bot Permissions",
            value="\n".join(permission_status),
            inline=False,
        )

        # Role status
        role_status = []
        if speaker_role:
            role_status.append(f"✅ Speaker Role ({len([m for m in ctx.guild.members if speaker_role in m.roles])} members)")
        else:
            role_status.append("❌ Speaker Role (Missing)")
        
        if broadcast_admin_role:
            role_status.append(f"✅ Broadcast Admin Role ({len([m for m in ctx.guild.members if broadcast_admin_role in m.roles])} members)")
        else:
            role_status.append("❌ Broadcast Admin Role (Missing)")

        embed.add_field(
            name="👥 Required Roles",
            value="\n".join(role_status),
            inline=False,
        )

        # Active sections
        if has_active_section:
            section = audio_router.section_manager.active_sections[ctx.guild.id]
            embed.add_field(
                name="📊 Active Broadcast Section",
                value=f"✅ **{section.section_name}**\n"
                      f"Status: {'🟢 Broadcasting' if section.is_active else '🔴 Stopped'}\n"
                      f"Listener Channels: {len(section.listener_channel_ids)}",
                inline=False,
            )
        else:
            embed.add_field(
                name="📊 Active Broadcast Section",
                value="❌ No active broadcast section found",
                inline=False,
            )

        # Overall status and recommendations
        issues = []
        if not has_administrator and (not has_manage_channels or not has_manage_roles):
            issues.append("• Bot lacks required permissions")
        
        if not speaker_role or not broadcast_admin_role:
            issues.append("• Required roles are missing")
        
        if not has_connect or not has_speak:
            issues.append("• Bot cannot access voice channels")

        if issues:
            embed.add_field(
                name="⚠️ Issues Found",
                value="\n".join(issues),
                inline=False,
            )
            
            embed.add_field(
                name="🔧 How to Fix",
                value="• Run `!check_permissions` for detailed permission analysis\n"
                      "• Run `!setup_roles` to create missing roles\n"
                      "• Contact your server administrator if permissions are missing",
                inline=False,
            )
            
            embed.color = discord.Color.orange()
        else:
            embed.add_field(
                name="✅ Setup Status",
                value="Your server is properly configured! You can:\n"
                      "• Run `!setup_broadcast 'Name' N` to create a broadcast section\n"
                      "• Run `!how_it_works` to learn how to use the system",
                inline=False,
            )
            embed.color = discord.Color.green()

        await ctx.send(embed=embed)

    except Exception as e:
        logger.error(f"Error in check_setup command: {e}", exc_info=True)
        embed = discord.Embed(
            title="❌ Command Error",
            description=f"An error occurred: {str(e)}",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)




@bot.command(name="check_permissions")
@is_admin()
async def check_permissions_command(ctx):
    """Check bot permissions and provide step-by-step fixes."""
    try:
        bot_member = ctx.guild.me

        embed = discord.Embed(
            title="🔍 Bot Permission Analysis", 
            description="Analyzing bot permissions and role hierarchy...",
            color=discord.Color.blue()
        )

        # Check essential permissions
        permissions = [
            ("Manage Channels", bot_member.guild_permissions.manage_channels, "Required to create and manage voice channels"),
            ("Manage Roles", bot_member.guild_permissions.manage_roles, "Required to create and manage roles"),
            ("Connect", bot_member.guild_permissions.connect, "Required to join voice channels"),
            ("Speak", bot_member.guild_permissions.speak, "Required to play audio in voice channels"),
            ("Send Messages", bot_member.guild_permissions.send_messages, "Required to send command responses"),
            ("Read Message History", bot_member.guild_permissions.read_message_history, "Required to read command messages"),
            ("Embed Links", bot_member.guild_permissions.embed_links, "Required to send rich embeds"),
            ("Administrator", bot_member.guild_permissions.administrator, "Full access to all features"),
        ]

        permission_status = []
        missing_permissions = []
        
        for perm_name, has_perm, description in permissions:
            status = "✅" if has_perm else "❌"
            permission_status.append(f"{status} **{perm_name}**")
            if not has_perm and perm_name != "Administrator":  # Don't require admin if other perms are present
                missing_permissions.append((perm_name, description))

        embed.add_field(
            name="📋 Current Permissions",
            value="\n".join(permission_status),
            inline=False,
        )

        # Check role hierarchy
        embed.add_field(
            name="👑 Bot Role Position",
            value=f"**Bot Role:** {bot_member.top_role.name}\n"
                  f"**Position:** {bot_member.top_role.position} (higher = more permissions)\n"
                  f"**Total Roles:** {len(ctx.guild.roles)}",
            inline=False,
        )

        # Check if bot can manage required roles
        speaker_role = discord.utils.get(ctx.guild.roles, name="Speaker")
        broadcast_admin_role = discord.utils.get(ctx.guild.roles, name="Broadcast Admin")
        
        role_management_status = []
        if speaker_role:
            can_manage_speaker = bot_member.top_role > speaker_role
            status = "✅" if can_manage_speaker else "❌"
            role_management_status.append(f"{status} **Speaker Role** (Position: {speaker_role.position})")
        else:
            role_management_status.append("⚠️ **Speaker Role** (Not created yet)")
            
        if broadcast_admin_role:
            can_manage_admin = bot_member.top_role > broadcast_admin_role
            status = "✅" if can_manage_admin else "❌"
            role_management_status.append(f"{status} **Broadcast Admin Role** (Position: {broadcast_admin_role.position})")
        else:
            role_management_status.append("⚠️ **Broadcast Admin Role** (Not created yet)")

        embed.add_field(
            name="🎭 Role Management",
            value="\n".join(role_management_status),
            inline=False,
        )

        # Provide fixes based on what's missing
        if missing_permissions or not bot_member.guild_permissions.administrator:
            embed.add_field(
                name="🔧 How to Fix Missing Permissions",
                value="**The bot needs additional permissions to function properly.**\n\n"
                      "**Contact your server administrator to:**\n"
                      "1. Go to **Server Settings** → **Roles**\n"
                      "2. Find the bot's role (usually named after the bot)\n"
                      "3. Enable the missing permissions:\n" +
                      "\n".join([f"   • **{perm}** - {desc}" for perm, desc in missing_permissions]) +
                      "\n4. **Move the bot's role higher** in the role list (above other roles)\n"
                      "5. **Save changes** and try again",
                inline=False,
            )
            embed.color = discord.Color.orange()
        else:
            embed.add_field(
                name="✅ Permission Status",
                value="**All required permissions are present!**\n"
                      "The bot should work correctly. If you're still having issues:\n"
                      "• Run `!setup_roles` to create required roles\n"
                      "• Run `!check_setup` to verify everything is working",
                inline=False,
            )
            embed.color = discord.Color.green()

        # Additional troubleshooting
        if bot_member.top_role.position < 3:
            embed.add_field(
                name="⚠️ Role Hierarchy Issue",
                value="**The bot's role is positioned too low in the hierarchy.**\n"
                      "This can cause permission issues even if permissions are granted.\n\n"
                      "**Fix:** Move the bot's role higher in the role list (closer to the top)",
                inline=False,
            )

        await ctx.send(embed=embed)

    except Exception as e:
        logger.error(f"Error in check_permissions command: {e}", exc_info=True)
        embed = discord.Embed(
            title="❌ Command Error",
            description=f"An error occurred: {str(e)}",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)


@bot.command(name="role_info")
async def role_info_command(ctx):
    """Show information about the audio router roles and how to use them."""
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
        speaker_role = discord.utils.get(
            ctx.guild.roles, name=audio_router.access_control.speaker_role_name
        )
        broadcast_admin_role = discord.utils.get(
            ctx.guild.roles,
            name=audio_router.access_control.broadcast_admin_role_name,
        )

        embed = discord.Embed(
            title="👥 Audio Router Role Information",
            description="Learn about the roles used by the audio router system:",
            color=discord.Color.blue(),
        )

        # Speaker role info
        if speaker_role:
            speaker_members = [
                member
                for member in ctx.guild.members
                if speaker_role in member.roles
            ]
            embed.add_field(
                name="🎤 Speaker Role",
                value=f"**Role:** {speaker_role.mention}\n"
                f"**Purpose:** Required to join speaker channels\n"
                f"**Members:** {len(speaker_members)} users\n"
                f"**Position:** {speaker_role.position}",
                inline=False,
            )
        else:
            embed.add_field(
                name="🎤 Speaker Role",
                value=f"**Status:** ❌ Not created\n"
                f"**Purpose:** Required to join speaker channels\n"
                f"**Action:** Run `!setup_roles` to create this role",
                inline=False,
            )

        # Broadcast admin role info
        if broadcast_admin_role:
            admin_members = [
                member
                for member in ctx.guild.members
                if broadcast_admin_role in member.roles
            ]
            embed.add_field(
                name="🎛️ Broadcast Admin Role",
                value=f"**Role:** {broadcast_admin_role.mention}\n"
                f"**Purpose:** Required to use bot commands\n"
                f"**Members:** {len(admin_members)} users\n"
                f"**Position:** {broadcast_admin_role.position}",
                inline=False,
            )
        else:
            embed.add_field(
                name="🎛️ Broadcast Admin Role",
                value=f"**Status:** ❌ Not created\n"
                f"**Purpose:** Required to use bot commands\n"
                f"**Action:** Run `!setup_roles` to create this role",
                inline=False,
            )

        # How the system works
        embed.add_field(
            name="🔧 How the Role System Works",
            value="• **🎤 Speaker Role:** Users with this role can join speaker channels to broadcast audio\n"
            "• **🎛️ Broadcast Admin Role:** Users with this role can use bot commands to control broadcasts\n"
            "• **👑 Server Administrators:** Can always use all commands and join any channel\n"
            "• **👥 Everyone Else:** Can join listener channels freely (no role required)",
            inline=False,
        )

        # Usage examples
        embed.add_field(
            name="📝 Usage Examples",
            value="• **For a presentation:** Give Speaker role to the presenter, everyone else joins listener channels\n"
            "• **For a meeting:** Give Broadcast Admin role to meeting organizers, Speaker role to speakers\n"
            "• **For an event:** Create multiple broadcast sections, assign roles as needed",
            inline=False,
        )

        # Next steps
        if not speaker_role or not broadcast_admin_role:
            embed.add_field(
                name="🚀 Next Steps",
                value="1. Run `!setup_roles` to create the required roles\n"
                "2. Assign roles to users as needed\n"
                "3. Run `!setup_broadcast 'Name' N` to create your first broadcast section",
                inline=False,
            )
            embed.color = discord.Color.orange()
        else:
            embed.add_field(
                name="✅ Ready to Use",
                value="All required roles are set up! You can now:\n"
                "• Assign roles to users\n"
                "• Create broadcast sections with `!setup_broadcast 'Name' N`\n"
                "• Start broadcasting with `!start_broadcast`",
                inline=False,
            )
            embed.color = discord.Color.green()

        await ctx.send(embed=embed)

    except Exception as e:
        logger.error(f"Error in role_info command: {e}", exc_info=True)
        embed = discord.Embed(
            title="❌ Command Error",
            description=f"An error occurred: {str(e)}",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)


@bot.command(name="debug_control_channel")
@get_broadcast_admin_decorator()
async def debug_control_channel_command(ctx):
    """🔧 Debug control channel permissions and access."""
    try:
        if not audio_router:
            embed = discord.Embed(
                title="❌ System Error",
                description="Audio router not initialized. Please restart the bot.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return

        # Check if there's an active section
        if ctx.guild.id not in audio_router.section_manager.active_sections:
            embed = discord.Embed(
                title="❌ No Active Section",
                description="No active broadcast section found in this server.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return

        section = audio_router.section_manager.active_sections[ctx.guild.id]
        control_channel = ctx.guild.get_channel(section.control_channel_id)
        
        if not control_channel:
            embed = discord.Embed(
                title="❌ Control Channel Not Found",
                description=f"Control channel with ID {section.control_channel_id} not found.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return

        # Check bot permissions in control channel
        bot_member = ctx.guild.me
        bot_permissions = control_channel.permissions_for(bot_member)
        
        embed = discord.Embed(
            title="🔧 Control Channel Debug Info",
            description=f"Debug information for control channel: {control_channel.mention}",
            color=discord.Color.blue(),
        )
        
        # Bot permissions
        permission_status = []
        permissions_to_check = [
            ("read_messages", "Read Messages"),
            ("send_messages", "Send Messages"),
            ("embed_links", "Embed Links"),
            ("manage_messages", "Manage Messages"),
            ("read_message_history", "Read Message History"),
        ]
        
        for perm_attr, perm_name in permissions_to_check:
            has_perm = getattr(bot_permissions, perm_attr, False)
            status = "✅" if has_perm else "❌"
            permission_status.append(f"{status} {perm_name}")
        
        embed.add_field(
            name="🤖 Bot Permissions in Control Channel",
            value="\n".join(permission_status),
            inline=False,
        )
        
        # Channel permissions
        embed.add_field(
            name="📋 Channel Permission Overwrites",
            value=f"**@everyone:** {len(control_channel.overwrites_for(ctx.guild.default_role))} overwrites\n"
                  f"**Bot Role:** {len(control_channel.overwrites_for(bot_member))} overwrites\n"
                  f"**Total Overwrites:** {len(control_channel.overwrites)}",
            inline=True,
        )
        
        # Test message sending
        try:
            test_embed = discord.Embed(
                title="✅ Test Message",
                description="This is a test message to verify the bot can send messages to this channel.",
                color=discord.Color.green(),
            )
            await control_channel.send(embed=test_embed)
            embed.add_field(
                name="📤 Message Test",
                value="✅ Successfully sent test message to control channel",
                inline=True,
            )
        except discord.Forbidden:
            embed.add_field(
                name="📤 Message Test",
                value="❌ Failed to send test message - permission denied",
                inline=True,
            )
        except Exception as e:
            embed.add_field(
                name="📤 Message Test",
                value=f"❌ Failed to send test message - {str(e)}",
                inline=True,
            )
        
        # Guild permissions
        guild_permissions = bot_member.guild_permissions
        embed.add_field(
            name="🏰 Guild Permissions",
            value=f"**Manage Channels:** {'✅' if guild_permissions.manage_channels else '❌'}\n"
                  f"**Manage Roles:** {'✅' if guild_permissions.manage_roles else '❌'}\n"
                  f"**Administrator:** {'✅' if guild_permissions.administrator else '❌'}",
            inline=True,
        )
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        logger.error(f"Error in debug_control_channel command: {e}", exc_info=True)
        embed = discord.Embed(
            title="❌ Command Error",
            description=f"An error occurred: {str(e)}",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)


@bot.command(name="system_status")
@get_broadcast_admin_decorator()
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

        embed = discord.Embed(
            title="🔍 System Status", color=discord.Color.blue()
        )

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
                name="📋 Process Details",
                value="\n\n".join(process_info),
                inline=False,
            )

        await ctx.send(embed=embed)

    except Exception as e:
        logger.error(f"Error in system_status command: {e}", exc_info=True)
        embed = discord.Embed(
            title="❌ Command Error",
            description=f"An error occurred: {str(e)}",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)


@bot.command(name="help")
async def help_command(ctx):
    """Show all available commands and their descriptions."""
    embed = discord.Embed(
        title="🎵 Audio Router Bot - Commands",
        description="Here are all the available commands for the Audio Router Bot:",
        color=discord.Color.blue(),
    )

    # Basic commands (available to everyone)
    embed.add_field(
        name="📋 Basic Commands",
        value="• `!help` - Show this command list\n"
        "• `!how_it_works` - Learn how the audio routing system works\n"
        "• `!check_setup` - Check if your server is properly configured",
        inline=False,
    )

    # Admin commands
    embed.add_field(
        name="👑 Admin Commands",
        value="• `!setup_roles` - Create and configure required roles\n"
        "• `!check_permissions` - Verify bot permissions and get fixes\n"
        "• `!setup_broadcast 'Name' N` - Create a broadcast section\n"
        "• `!start_broadcast` - Start audio forwarding\n"
        "• `!stop_broadcast` - Stop audio forwarding\n"
        "• `!broadcast_status` - Check broadcast status\n"
        "• `!cleanup_setup` - Remove entire broadcast section\n"
        "• `!system_status` - Get detailed system information",
        inline=False,
    )

    # Role management commands
    embed.add_field(
        name="👥 Role Management",
        value="• `!role_info` - Show information about audio router roles\n"
        "• `!setup_roles` - Create and position roles correctly",
        inline=False,
    )

    # Debug commands
    embed.add_field(
        name="🔧 Debug Commands",
        value="• `!debug_control_channel` - Debug control channel issues\n"
        "• `!check_permissions` - Detailed permission analysis",
        inline=False,
    )

    # Quick start guide
    embed.add_field(
        name="🚀 Quick Start",
        value="1. Run `!check_setup` to see what's needed\n"
        "2. Run `!setup_roles` to create required roles\n"
        "3. Run `!setup_broadcast 'Test Room' 3` to create your first section\n"
        "4. Go to the control channel and run `!start_broadcast`",
        inline=False,
    )

    embed.set_footer(text="Use !how_it_works to learn more about the system")
    await ctx.send(embed=embed)


@bot.command(name="how_it_works")
async def how_it_works_command(ctx):
    """Explain how the audio routing system works."""
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
        "• **Everyone Else:** Can join listener channels freely",
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

    embed.set_footer(text="Run !check_setup to see if your server is ready")
    await ctx.send(embed=embed)


# Initialize and run the bot
async def main():
    """Main function to initialize and run the bot."""
    try:
        logger.info("Starting AudioBroadcast Bot...")
        await bot.start(config.audio_broadcast_token)
    except Exception as e:
        logger.critical(f"Failed to start AudioBroadcast Bot: {e}")
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot shutdown requested")
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        raise
