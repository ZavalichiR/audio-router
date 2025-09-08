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




@bot.command(name="start_broadcast")
@get_broadcast_admin_decorator()
async def start_broadcast_command(ctx, *, args: str) -> None:
    """
    🎵 Start audio broadcasting with automatic setup.
    
    This command creates a complete broadcast section and immediately starts broadcasting:
    - Creates a category with the specified name
    - Creates one speaker channel for the presenter
    - Creates N listener channels for the audience
    - Creates a control channel for admin commands
    - Immediately starts audio forwarding

    Usage: !start_broadcast 'Section Name' N
    Example: !start_broadcast 'War Room' 5

    Args:
        ctx: Discord command context
        args: Command arguments in format "'Section Name' N"

    Note:
        - Section name must be enclosed in single quotes
        - N must be between 1 and 10
        - Requires Administrator permissions or Broadcast Admin role
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
                description="Usage: `!start_broadcast 'Section Name' N`\n"
                "Example: `!start_broadcast 'War Room' 5`",
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

        # Send initial loading message that replaces the command message
        loading_embed = discord.Embed(
            title="🔄 Creating broadcast section...",
            description=f"Creating broadcast section '{section_name}' with {listener_count} listener channels...",
            color=discord.Color.blue(),
        )
        loading_message = await ctx.send(embed=loading_embed)

        # Check if there's already an active section and clean it up first
        if ctx.guild.id in audio_router.section_manager.active_sections:
            # Update loading message for cleanup
            cleanup_embed = discord.Embed(
                title="🔄 Cleaning Up Existing Section",
                description="Found an existing broadcast section. Cleaning it up first...",
                color=discord.Color.orange(),
            )
            await loading_message.edit(embed=cleanup_embed)
            
            # Clean up existing section
            cleanup_result = await audio_router.cleanup_section(ctx.guild)
            if not cleanup_result["success"]:
                error_embed = discord.Embed(
                    title="❌ Failed to Cleanup Existing Section",
                    description=cleanup_result["message"],
                    color=discord.Color.red(),
                )
                await loading_message.edit(embed=error_embed)
                return

        # Update loading message for section creation
        creating_embed = discord.Embed(
            title="🏗️ Setting Up Broadcast Section",
            description=f"Creating broadcast section '{section_name}' with {listener_count} listener channels...",
            color=discord.Color.blue(),
        )
        await loading_message.edit(embed=creating_embed)

        result = await audio_router.create_broadcast_section(
            ctx.guild, section_name, listener_count
        )

        if not result["success"]:
            error_embed = discord.Embed(
                title="❌ Failed to Create Section",
                description=result["message"],
                color=discord.Color.red(),
            )
            await loading_message.edit(embed=error_embed)
            return

        # Update loading message for starting broadcast
        starting_embed = discord.Embed(
            title="🎵 Starting Audio Broadcasting",
            description="Starting audio forwarding from speaker to all listener channels...",
            color=discord.Color.blue(),
        )
        await loading_message.edit(embed=starting_embed)

        start_result = await audio_router.start_broadcast(ctx.guild)

        if start_result["success"]:
            # Get the control channel for the success message
            section = audio_router.section_manager.active_sections[ctx.guild.id]
            control_channel_mention = f"<#{section.control_channel_id}>" if section.control_channel_id else "the control channel"
            
            # Store reference to the loading message for potential cleanup updates
            section.original_message = loading_message
            
            success_embed = discord.Embed(
                title="🎵 Broadcast Started Successfully!",
                description=f"**{section_name}** is now live!\n\n"
                           f"✅ Section created with {listener_count} listener channels\n"
                           f"✅ Audio forwarding is active\n"
                           f"✅ Presenters can join the speaker channel\n"
                           f"✅ Audience can join any listener channel\n\n"
                           f"Go to {control_channel_mention} for more commands!",
                color=discord.Color.green(),
            )
        else:
            # Get the control channel for the partial success message
            section = audio_router.section_manager.active_sections[ctx.guild.id]
            control_channel_mention = f"<#{section.control_channel_id}>" if section.control_channel_id else "the control channel"
            
            # Store reference to the loading message for potential cleanup updates
            section.original_message = loading_message
            
            success_embed = discord.Embed(
                title="⚠️ Section Created but Broadcast Failed",
                description=f"**{section_name}** was created successfully, but starting the broadcast failed:\n\n"
                           f"{start_result['message']}\n\n"
                           f"Go to {control_channel_mention} to try `!start_broadcast` again or use `!stop_broadcast` to clean up.",
                color=discord.Color.orange(),
            )

        await loading_message.edit(embed=success_embed)

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
    """
    ⏹️ Stop audio broadcasting and clean up the entire section.
    
    This command:
    - Stops all audio broadcasting
    - Deletes all broadcast channels
    - Removes the broadcast category
    - Cleans up all resources
    
    Usage: !stop_broadcast
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

        # Check if there's an active section
        if ctx.guild.id not in audio_router.section_manager.active_sections:
            embed = discord.Embed(
                title="❌ No Active Section",
                description="No active broadcast section found in this server.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return

        # Get section info before cleanup
        section = audio_router.section_manager.active_sections[ctx.guild.id]
        section_name = section.section_name

        # Stop broadcasting first
        embed = discord.Embed(
            title="⏹️ Stopping Audio Broadcasting",
            description=f"Stopping audio forwarding for '{section_name}'...",
            color=discord.Color.orange(),
        )
        await ctx.send(embed=embed)

        stop_result = await audio_router.stop_broadcast(ctx.guild)

        if not stop_result["success"]:
            embed = discord.Embed(
                title="⚠️ Failed to Stop Broadcast",
                description=f"Could not stop broadcasting: {stop_result['message']}\n\n"
                           f"Proceeding with cleanup anyway...",
                color=discord.Color.orange(),
            )
            await ctx.send(embed=embed)

        # Now clean up the entire section
        embed = discord.Embed(
            title="🗑️ Cleaning Up Broadcast Section",
            description=f"Removing all channels and resources for '{section_name}'...",
            color=discord.Color.orange(),
        )
        await ctx.send(embed=embed)

        cleanup_result = await audio_router.cleanup_section(ctx.guild)

        if cleanup_result["success"]:
            embed = discord.Embed(
                title="✅ Broadcast Stopped and Cleaned Up!",
                description=f"**{section_name}** has been completely removed:\n\n"
                           f"✅ Audio broadcasting stopped\n"
                           f"✅ All broadcast channels deleted\n"
                           f"✅ Category removed\n"
                           f"✅ All resources cleaned up\n\n"
                           f"Use `!start_broadcast 'Name' N` to create a new section.",
                color=discord.Color.green(),
            )
        else:
            embed = discord.Embed(
                title="⚠️ Partial Cleanup",
                description=f"Broadcasting was stopped, but cleanup encountered issues:\n\n"
                           f"{cleanup_result['message']}\n\n"
                           f"You may need to manually delete some channels.",
                color=discord.Color.orange(),
            )

        # Try to send the result message, but handle the case where the channel might be deleted
        try:
            await ctx.send(embed=embed)
        except discord.NotFound:
            # Channel was deleted during cleanup, log success but don't try to send message
            logger.info(f"Cleanup completed successfully for section '{section_name}', but control channel was deleted")
        except Exception as send_error:
            logger.warning(f"Could not send cleanup result message: {send_error}")

        # Try to update the original start_broadcast loading message if it exists
        try:
            if section.original_message:
                # Create a "broadcast ended" message for the original loading message location
                ended_embed = discord.Embed(
                    title="⏹️ Broadcast Ended",
                    description=f"**{section_name}** broadcast has been stopped and cleaned up.\n\n"
                               f"✅ All channels and resources have been removed\n"
                               f"✅ Ready for a new broadcast section\n\n"
                               f"Use `!start_broadcast 'Name' N` to create a new section.",
                    color=discord.Color.blue(),
                )
                await section.original_message.edit(embed=ended_embed)
                logger.info(f"Updated original start_broadcast loading message for section '{section_name}'")
        except discord.NotFound:
            # Original message was deleted, that's okay
            logger.info(f"Original start_broadcast loading message for section '{section_name}' was deleted")
        except Exception as update_error:
            # Some other error updating the original message, log but don't fail
            logger.warning(f"Could not update original start_broadcast loading message: {update_error}")

    except Exception as e:
        logger.error(f"Error in stop_broadcast command: {e}", exc_info=True)
        embed = discord.Embed(
            title="❌ Command Error",
            description=f"An error occurred: {str(e)}",
            color=discord.Color.red(),
        )
        # Try to send error message, but handle case where channel might not exist
        try:
            await ctx.send(embed=embed)
        except discord.NotFound:
            logger.warning("Could not send error message - channel may have been deleted")
        except Exception as send_error:
            logger.warning(f"Could not send error message: {send_error}")


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
                name="📡 Broadcasting",
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
                      "3. **Create Section:** Run `!start_broadcast 'Test Room' 3`\n"
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
                      "• Run `!start_broadcast 'Name' N` to create and start a broadcast section\n"
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
                "3. Run `!start_broadcast 'Name' N` to create and start your first broadcast section",
                inline=False,
            )
            embed.color = discord.Color.orange()
        else:
            embed.add_field(
                name="✅ Ready to Use",
                value="All required roles are set up! You can now:\n"
                "• Assign roles to users\n"
                "• Create and start broadcast sections with `!start_broadcast 'Name' N`\n"
                "• Stop and clean up with `!stop_broadcast`",
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
        "• `!start_broadcast 'Name' N` - Create and start a broadcast section\n"
        "• `!stop_broadcast` - Stop broadcasting and clean up section\n"
        "• `!broadcast_status` - Check broadcast status",
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
        value="• `!check_permissions` - Detailed permission analysis",
        inline=False,
    )

    # Quick start guide
    embed.add_field(
        name="🚀 Quick Start",
        value="1. Run `!check_setup` to see what's needed\n"
        "2. Run `!setup_roles` to create required roles\n"
        "3. Run `!start_broadcast 'Test Room' 3` to create and start your first section\n"
        "4. Use `!stop_broadcast` to stop and clean up when done",
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
