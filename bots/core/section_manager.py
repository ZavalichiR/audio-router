"""
Section Manager for handling broadcast sections.

This module manages broadcast sections, including channel creation,
bot deployment, and audio routing coordination.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
import discord
from discord.ext import commands

from .process_manager import ProcessManager
from .access_control import AccessControl

logger = logging.getLogger(__name__)


class BroadcastSection:
    """
    Represents a broadcast section with speaker and listener channels.
    
    A broadcast section is a complete audio routing setup that includes:
    - One speaker channel where the presenter speaks
    - Multiple listener channels where audience members listen
    - Associated bot instances for audio routing
    """
    
    def __init__(self, guild_id: int, section_name: str, speaker_channel_id: int, 
                 listener_channel_ids: List[int]):
        """
        Initialize a broadcast section.
        
        Args:
            guild_id: Discord guild ID
            section_name: Name of the section (e.g., 'War Room')
            speaker_channel_id: Channel ID for the speaker channel
            listener_channel_ids: List of channel IDs for listener channels
        """
        self.guild_id = guild_id
        self.section_name = section_name
        self.speaker_channel_id = speaker_channel_id
        self.listener_channel_ids = listener_channel_ids
        self.is_active = False
        self.category_id: Optional[int] = None
        self.control_channel_id: Optional[int] = None
        
        # Bot instances for this section
        self.speaker_bot_id: Optional[str] = None
        self.listener_bot_ids: List[str] = []
    
    def get_status(self) -> Dict[str, Any]:
        """Get the current status of this section."""
        return {
            'section_name': self.section_name,
            'speaker_channel_id': self.speaker_channel_id,
            'listener_channel_ids': self.listener_channel_ids,
            'is_active': self.is_active,
            'category_id': self.category_id,
            'control_channel_id': self.control_channel_id,
            'speaker_bot_id': self.speaker_bot_id,
            'listener_bot_ids': self.listener_bot_ids
        }


class SectionManager:
    """
    Manages broadcast sections and their associated resources.
    
    This class handles the creation, management, and cleanup of broadcast
    sections, including channel creation and bot deployment.
    """
    
    def __init__(self, process_manager: ProcessManager, access_control: AccessControl = None):
        """
        Initialize the section manager.
        
        Args:
            process_manager: Process manager instance
            access_control: Access control instance (optional)
        """
        self.process_manager = process_manager
        self.access_control = access_control
        self.active_sections: Dict[int, BroadcastSection] = {}  # guild_id -> section
    
    async def _adopt_existing_category(self, guild: discord.Guild, existing_category: discord.CategoryChannel, 
                                     section_name: str, listener_count: int) -> Dict[str, Any]:
        """
        Try to adopt an existing category and convert it to a broadcast section.
        
        Args:
            guild: Discord guild
            existing_category: Existing category to adopt
            section_name: Name of the section
            listener_count: Number of listener channels needed
            
        Returns:
            Dict with adoption results
        """
        try:
            # Check if the category has the right structure
            voice_channels = [ch for ch in existing_category.channels if isinstance(ch, discord.VoiceChannel)]
            text_channels = [ch for ch in existing_category.channels if isinstance(ch, discord.TextChannel)]
            
            # Look for speaker and listener channels
            speaker_channel = None
            listener_channels = []
            control_channel = None
            
            for channel in voice_channels:
                if "🎤" in channel.name or "speaker" in channel.name.lower():
                    speaker_channel = channel
                elif "📢" in channel.name or "listener" in channel.name.lower():
                    listener_channels.append(channel)
            
            for channel in text_channels:
                if "control" in channel.name.lower() or "broadcast" in channel.name.lower():
                    control_channel = channel
            
            # If we have a good structure, adopt it
            if speaker_channel and len(listener_channels) >= listener_count:
                # Create broadcast section from existing channels
                section = BroadcastSection(
                    guild_id=guild.id,
                    section_name=section_name,
                    speaker_channel_id=speaker_channel.id,
                    listener_channel_ids=[ch.id for ch in listener_channels[:listener_count]]
                )
                section.category_id = existing_category.id
                if control_channel:
                    section.control_channel_id = control_channel.id
                
                self.active_sections[guild.id] = section
                
                # Set up private channel permissions if we have a control channel
                if control_channel and self.access_control:
                    authorized_role = None
                    if self.access_control.config.create_authorized_role:
                        authorized_role = await self.access_control.create_authorized_role(
                            guild, 
                            self.access_control.config.authorized_role_name
                        )
                    
                    # Try to set up permissions, but don't fail if it doesn't work
                    permission_success = await self.access_control.setup_private_channel_permissions(
                        control_channel, 
                        authorized_role
                    )
                    if not permission_success:
                        logger.warning(f"Could not set up private permissions for adopted channel: {control_channel.name}")
                
                logger.info(f"Adopted existing category '{section_name}' in {guild.name}")
                
                return {
                    'success': True,
                    'message': f"Adopted existing broadcast section '{section_name}' with {len(listener_channels)} listener channels",
                    'section': section,
                    'was_existing': True,
                    'adopted': True,
                    'simple_message': f"✅ Using existing broadcast section '{section_name}'! Go to the control channel and use `!start_broadcast` to begin."
                }
            
            # If structure is not suitable, create a new category with a different name
            new_section_name = f"{section_name} (New)"
            counter = 1
            while discord.utils.get(guild.categories, name=new_section_name):
                counter += 1
                new_section_name = f"{section_name} (New {counter})"
            
            logger.info(f"Existing category '{section_name}' not suitable, creating '{new_section_name}' instead")
            
            # Create new category with modified name
            category = await guild.create_category(
                name=new_section_name,
                reason=f"Creating broadcast section: {new_section_name} (original name '{section_name}' was taken)"
            )
            
            # Continue with normal creation process using the new name
            return await self._create_new_section(guild, category, new_section_name, listener_count)
            
        except Exception as e:
            logger.error(f"Error adopting existing category: {e}")
            return {
                'success': False,
                'message': f"Failed to adopt existing category: {str(e)}"
            }
    
    async def _create_new_section(self, guild: discord.Guild, category: discord.CategoryChannel, 
                                section_name: str, listener_count: int) -> Dict[str, Any]:
        """
        Create a new broadcast section with the given category.
        
        Args:
            guild: Discord guild
            category: Category to use for the section
            section_name: Name of the section
            listener_count: Number of listener channels to create
            
        Returns:
            Dict with creation results
        """
        try:
            # Create speaker channel
            speaker_channel = await category.create_voice_channel(
                name="Speaker",
                bitrate=96000,  # Discord's maximum bitrate
                user_limit=10,
                reason="Creating speaker channel"
            )
            
            # Create listener channels
            listener_channel_ids = []
            for i in range(1, listener_count + 1):
                listener_channel = await category.create_voice_channel(
                    name=f"{i}-listener",
                    bitrate=96000,  # Discord's maximum bitrate
                    user_limit=0,
                    reason=f"Creating listener channel {i}"
                )
                listener_channel_ids.append(listener_channel.id)
            
            # Create control text channel
            control_channel = await category.create_text_channel(
                name="broadcast-control",
                topic=f"Control channel for {section_name} broadcast section",
                reason="Creating control channel"
            )
            
            # Set up private channel permissions using access control
            permission_setup_success = False
            if self.access_control:
                # Create authorized role if configured
                authorized_role = None
                if self.access_control.config.create_authorized_role:
                    authorized_role = await self.access_control.create_authorized_role(
                        guild, 
                        self.access_control.config.authorized_role_name
                    )
                
                # Set up private permissions
                permission_setup_success = await self.access_control.setup_private_channel_permissions(
                    control_channel, 
                    authorized_role
                )
            
            # Fallback to basic permissions if access control setup failed
            if not permission_setup_success:
                try:
                    # Check if bot has manage channels permission before attempting
                    if guild.me.guild_permissions.manage_channels:
                        # Basic admin-only permissions
                        await control_channel.set_permissions(
                            guild.default_role,
                            read_messages=False,
                            send_messages=False
                        )
                        await control_channel.set_permissions(
                            guild.me,
                            read_messages=True,
                            send_messages=True,
                            manage_messages=True
                        )
                        logger.info(f"Set up basic permissions for control channel: {control_channel.name}")
                    else:
                        logger.warning(f"Bot lacks 'Manage Channels' permission - control channel will remain public")
                except discord.Forbidden:
                    logger.warning(f"Cannot set basic permissions for control channel: {control_channel.name}")
                    # Channel will remain public - not ideal but functional
            
            # Create broadcast section
            section = BroadcastSection(
                guild_id=guild.id,
                section_name=section_name,
                speaker_channel_id=speaker_channel.id,
                listener_channel_ids=listener_channel_ids
            )
            section.category_id = category.id
            section.control_channel_id = control_channel.id
            
            self.active_sections[guild.id] = section
            
            # Send welcome message (if bot has permission)
            try:
                embed = discord.Embed(
                    title=f"🎵 {section_name} Broadcast Section Created!",
                    description="Your broadcast section is ready to use!",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="🎤 Speaker Channel",
                    value=f"<#{speaker_channel.id}>",
                    inline=True
                )
                embed.add_field(
                    name="📢 Listener Channels",
                    value=f"{listener_count} channels created",
                    inline=True
                )
                embed.add_field(
                    name="🎛️ Control Channel",
                    value=f"<#{control_channel.id}>",
                    inline=True
                )
                embed.add_field(
                    name="🎛️ Available Commands",
                    value="• `!start_broadcast` - Start audio forwarding\n"
                          "• `!stop_broadcast` - Stop audio forwarding\n"
                          "• `!broadcast_status` - Check broadcast status\n"
                          "• `!cleanup_setup` - Remove entire section",
                    inline=False
                )
                
                await control_channel.send(embed=embed)
                logger.info(f"Sent welcome message to control channel: {control_channel.name}")
            except discord.Forbidden:
                logger.warning(f"Cannot send welcome message to control channel: {control_channel.name} - bot lacks send message permission")
            except Exception as e:
                logger.warning(f"Failed to send welcome message: {e}")
            
            logger.info(f"Created broadcast section '{section_name}' in {guild.name} with {listener_count} listeners")
            
            return {
                'success': True,
                'message': f"Broadcast section '{section_name}' created successfully!",
                'section': section,
                'category_id': category.id,
                'control_channel_id': control_channel.id,
                'was_existing': False,
                'simple_message': f"✅ Broadcast section '{section_name}' created! Go to the control channel and use `!start_broadcast` to begin."
            }
            
        except Exception as e:
            logger.error(f"Error creating new section: {e}")
            return {
                'success': False,
                'message': f"Failed to create broadcast section: {str(e)}"
            }
    
    async def create_broadcast_section(self, guild: discord.Guild, section_name: str, 
                                     listener_count: int) -> Dict[str, Any]:
        """
        Create a broadcast section with speaker and listener channels.
        
        Args:
            guild: Discord guild
            section_name: Name of the section (e.g., 'War Room')
            listener_count: Number of listener channels to create
            
        Returns:
            Dict with creation results
        """
        try:
            # Check if section already exists in active sections
            if guild.id in self.active_sections:
                existing_section = self.active_sections[guild.id]
                return {
                    'success': True,
                    'message': f"Using existing broadcast section '{existing_section.section_name}'",
                    'section': existing_section,
                    'was_existing': True,
                    'simple_message': f"✅ Using existing broadcast section '{existing_section.section_name}'! Go to the control channel and use `!start_broadcast` to begin."
                }
            
            # Check if a category with the same name already exists
            existing_category = discord.utils.get(guild.categories, name=section_name)
            if existing_category:
                # Try to adopt the existing category by creating a section from it
                return await self._adopt_existing_category(guild, existing_category, section_name, listener_count)
            
            # Create category for the section
            category = await guild.create_category(
                name=section_name,
                reason=f"Creating broadcast section: {section_name}"
            )
            logger.info(f"Created category '{section_name}' in {guild.name}")
            
            # Use the helper method to create the section
            return await self._create_new_section(guild, category, section_name, listener_count)
            
        except Exception as e:
            logger.error(f"Error creating broadcast section in {guild.name}: {e}")
            return {
                'success': False,
                'message': f"Failed to create broadcast section: {str(e)}"
            }
    
    async def start_broadcast(self, guild: discord.Guild) -> Dict[str, Any]:
        """
        Start audio broadcasting for a section.
        
        Args:
            guild: Discord guild
            
        Returns:
            Dict with start results
        """
        try:
            if guild.id not in self.active_sections:
                return {
                    'success': False,
                    'message': "No active broadcast section found in this server!"
                }
            
            section = self.active_sections[guild.id]
            
            if section.is_active:
                return {
                    'success': False,
                    'message': "Broadcast is already active for this section!"
                }
            
            # Start speaker bot process
            speaker_bot_id = await self.process_manager.start_speaker_bot(section.speaker_channel_id, guild.id)
            if not speaker_bot_id:
                return {
                    'success': False,
                    'message': "Failed to start speaker bot process!"
                }
            
            # Start listener bot processes
            listener_bot_ids = []
            for channel_id in section.listener_channel_ids:
                listener_bot_id = await self.process_manager.start_listener_bot(
                    channel_id, guild.id, section.speaker_channel_id
                )
                if listener_bot_id:
                    listener_bot_ids.append(listener_bot_id)
                else:
                    logger.warning(f"Failed to start listener bot for channel {channel_id}")
            
            if not listener_bot_ids:
                # Stop speaker bot if no listeners started
                await self.process_manager.stop_bot(speaker_bot_id)
                return {
                    'success': False,
                    'message': "Failed to start any listener bot processes!"
                }
            
            # Update section with successful connections
            section.speaker_bot_id = speaker_bot_id
            section.listener_bot_ids = listener_bot_ids
            
            section.is_active = True
            
            logger.info(f"Started broadcast for section '{section.section_name}' in {guild.name}")
            
            return {
                'success': True,
                'message': f"Broadcast started for section '{section.section_name}'!",
                'speaker_channel': section.speaker_channel_id,
                'listener_count': len(listener_bot_ids)
            }
            
        except Exception as e:
            logger.error(f"Error starting broadcast in {guild.name}: {e}")
            return {
                'success': False,
                'message': f"Failed to start broadcast: {str(e)}"
            }
    
    async def stop_broadcast(self, guild: discord.Guild) -> Dict[str, Any]:
        """
        Stop audio broadcasting for a section.
        
        Args:
            guild: Discord guild
            
        Returns:
            Dict with stop results
        """
        try:
            if guild.id not in self.active_sections:
                return {
                    'success': False,
                    'message': "No active broadcast section found in this server!"
                }
            
            section = self.active_sections[guild.id]
            
            if not section.is_active:
                return {
                    'success': False,
                    'message': "Broadcast is not active for this section!"
                }
            
            # Stop all bot processes
            if section.speaker_bot_id:
                await self.process_manager.stop_bot(section.speaker_bot_id)
            
            for listener_bot_id in section.listener_bot_ids:
                await self.process_manager.stop_bot(listener_bot_id)
            
            # Clear section bot references
            section.speaker_bot_id = None
            section.listener_bot_ids.clear()
            
            section.is_active = False
            
            logger.info(f"Stopped broadcast for section '{section.section_name}' in {guild.name}")
            
            return {
                'success': True,
                'message': f"Broadcast stopped for section '{section.section_name}'!"
            }
            
        except Exception as e:
            logger.error(f"Error stopping broadcast in {guild.name}: {e}")
            return {
                'success': False,
                'message': f"Failed to stop broadcast: {str(e)}"
            }
    
    async def cleanup_section(self, guild: discord.Guild) -> Dict[str, Any]:
        """
        Clean up an entire broadcast section.
        
        Args:
            guild: Discord guild
            
        Returns:
            Dict with cleanup results
        """
        try:
            if guild.id not in self.active_sections:
                return {
                    'success': False,
                    'message': "No active broadcast section found in this server!"
                }
            
            section = self.active_sections[guild.id]
            
            # Stop broadcast if active
            if section.is_active:
                await self.stop_broadcast(guild)
            
            # Stop all bot processes for this guild
            await self.process_manager.stop_bots_by_guild(guild.id)
            
            # Find and delete the category
            for category in guild.categories:
                if category.name == section.section_name:
                    for channel in category.channels:
                        await channel.delete(reason="Cleaning up broadcast section")
                    await category.delete(reason="Cleaning up broadcast section")
                    break
            
            # Remove from active sections
            del self.active_sections[guild.id]
            
            logger.info(f"Cleaned up section '{section.section_name}' in {guild.name}")
            
            return {
                'success': True,
                'message': f"Broadcast section '{section.section_name}' cleaned up successfully!"
            }
            
        except Exception as e:
            logger.error(f"Error cleaning up section in {guild.name}: {e}")
            return {
                'success': False,
                'message': f"Failed to cleanup section: {str(e)}"
            }
    
    async def get_section_status(self, guild: discord.Guild) -> Dict[str, Any]:
        """
        Get the status of a broadcast section.
        
        Args:
            guild: Discord guild
            
        Returns:
            Dict with status information
        """
        if guild.id not in self.active_sections:
            return {
                'active': False,
                'message': "No active broadcast section in this server"
            }
        
        section = self.active_sections[guild.id]
        
        return {
            'active': True,
            'section_name': section.section_name,
            'is_broadcasting': section.is_active,
            'speaker_channel_id': section.speaker_channel_id,
            'listener_count': len(section.listener_channel_ids),
            'listener_channel_ids': section.listener_channel_ids
        }
