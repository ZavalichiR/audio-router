"""
Section Manager for handling broadcast sections.

This module manages broadcast sections, including channel creation,
bot deployment, and audio routing coordination.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import discord

from .access_control import AccessControl
from .process_manager import ProcessManager

logger = logging.getLogger(__name__)


class BroadcastSection:
    """
    Represents a broadcast section with speaker and listener channels.

    A broadcast section is a complete audio routing setup that includes:
    - One speaker channel where the presenter speaks
    - Multiple listener channels where audience members listen
    - Associated bot instances for audio routing
    """

    def __init__(
        self,
        guild_id: int,
        section_name: str,
        speaker_channel_id: int,
        listener_channel_ids: List[int],
    ):
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
        
        # Reference to the original start_broadcast message for cleanup updates
        self.original_message: Optional[Any] = None

    def get_status(self) -> Dict[str, Any]:
        """Get the current status of this section."""
        return {
            "section_name": self.section_name,
            "speaker_channel_id": self.speaker_channel_id,
            "listener_channel_ids": self.listener_channel_ids,
            "is_active": self.is_active,
            "category_id": self.category_id,
            "control_channel_id": self.control_channel_id,
            "speaker_bot_id": self.speaker_bot_id,
            "listener_bot_ids": self.listener_bot_ids,
        }


class SectionManager:
    """
    Manages broadcast sections and their associated resources.

    This class handles the creation, management, and cleanup of broadcast
    sections, including channel creation and bot deployment.
    """

    def __init__(
        self,
        process_manager: ProcessManager,
        access_control: AccessControl = None,
    ):
        """
        Initialize the section manager.

        Args:
            process_manager: Process manager instance
            access_control: Access control instance (optional)
        """
        self.process_manager = process_manager
        self.access_control = access_control
        self.active_sections: Dict[int, BroadcastSection] = (
            {}
        )  # guild_id -> section

    def _validate_section_structure(
        self, category: discord.CategoryChannel, expected_listener_count: int
    ) -> tuple[bool, str]:
        """
        Validate if a category has the correct structure for a broadcast section.
        
        Args:
            category: Category to validate
            expected_listener_count: Expected number of listener channels
            
        Returns:
            Tuple of (is_valid, validation_message)
        """
        voice_channels = [ch for ch in category.channels if isinstance(ch, discord.VoiceChannel)]
        text_channels = [ch for ch in category.channels if isinstance(ch, discord.TextChannel)]
        
        # Check for speaker channel
        speaker_channel = None
        for channel in voice_channels:
            if "🎤" in channel.name or "speaker" in channel.name.lower():
                speaker_channel = channel
                break
        
        # Check for listener channels (Channel-X format)
        listener_channels = []
        for channel in voice_channels:
            if channel.name.startswith("Channel-") and channel.name[8:].isdigit():
                listener_channels.append(channel)
        
        # Check for control channel
        control_channel = None
        for channel in text_channels:
            if "control" in channel.name.lower() or "broadcast" in channel.name.lower():
                control_channel = channel
                break
        
        # Validate structure
        if not speaker_channel:
            return False, "Missing speaker channel"
        
        if len(listener_channels) == 0:
            return False, "No listener channels found (expected Channel-1, Channel-2, etc.)"
        
        if len(listener_channels) != expected_listener_count:
            return False, f"Expected {expected_listener_count} listener channels, but found {len(listener_channels)}"
        
        if not control_channel:
            return False, "Missing control channel"
        
        # Check if listener channels are properly numbered
        expected_numbers = set(range(1, expected_listener_count + 1))
        actual_numbers = set()
        for channel in listener_channels:
            try:
                num = int(channel.name[8:])  # Extract number from "Channel-X"
                actual_numbers.add(num)
            except ValueError:
                return False, f"Invalid listener channel name: {channel.name}"
        
        if expected_numbers != actual_numbers:
            return False, f"Listener channels not properly numbered. Expected Channel-1 through Channel-{expected_listener_count}"
        
        return True, "Structure is valid"

    async def _adopt_existing_category(
        self,
        guild: discord.Guild,
        existing_category: discord.CategoryChannel,
        section_name: str,
        listener_count: int,
    ) -> Dict[str, Any]:
        """
        Adopt an existing category that has been validated to have the correct structure.

        Args:
            guild: Discord guild
            existing_category: Existing category to adopt (already validated)
            section_name: Name of the section
            listener_count: Number of listener channels needed

        Returns:
            Dict with adoption results
        """
        try:
            # Since structure is already validated, we can directly extract channels
            voice_channels = [ch for ch in existing_category.channels if isinstance(ch, discord.VoiceChannel)]
            text_channels = [ch for ch in existing_category.channels if isinstance(ch, discord.TextChannel)]

            # Extract channels (we know they exist from validation)
            speaker_channel = None
            listener_channels = []
            control_channel = None

            for channel in voice_channels:
                if "🎤" in channel.name or "speaker" in channel.name.lower():
                    speaker_channel = channel
                elif channel.name.startswith("Channel-") and channel.name[8:].isdigit():
                    listener_channels.append(channel)

            for channel in text_channels:
                if "control" in channel.name.lower() or "broadcast" in channel.name.lower():
                    control_channel = channel

            # Sort listener channels by numeric order
            def sort_key(channel):
                return int(channel.name[8:])  # Extract number from "Channel-X"
            
            listener_channels.sort(key=sort_key)
            
            # Create broadcast section from existing channels
            section = BroadcastSection(
                guild_id=guild.id,
                section_name=section_name,
                speaker_channel_id=speaker_channel.id,
                listener_channel_ids=[ch.id for ch in listener_channels],
            )
            section.category_id = existing_category.id
            if control_channel:
                section.control_channel_id = control_channel.id

            self.active_sections[guild.id] = section

            # Set up permissions for adopted channels
            if self.access_control:
                # Ensure required roles exist
                roles = await self.access_control.ensure_roles_exist(guild)
                speaker_role = roles.get("speaker_role")
                broadcast_admin_role = roles.get("broadcast_admin_role")

                # Set up voice channel permissions
                if speaker_channel:
                    await self.access_control.setup_voice_channel_permissions(
                        speaker_channel,
                        listener_channels,
                        broadcast_admin_role,
                        speaker_role,
                    )

                # Set up control channel permissions
                if control_channel and guild.me.guild_permissions.manage_channels:
                    try:
                        await control_channel.set_permissions(
                            guild.default_role,
                            read_messages=False,
                            send_messages=False,
                        )
                        await control_channel.set_permissions(
                            guild.me,
                            read_messages=True,
                            send_messages=True,
                            manage_messages=True,
                            embed_links=True,
                        )
                        if broadcast_admin_role:
                            await control_channel.set_permissions(
                                broadcast_admin_role,
                                read_messages=True,
                                send_messages=True,
                                embed_links=True,
                            )
                    except discord.Forbidden:
                        logger.warning(f"Could not set up control channel permissions for adopted channel: {control_channel.name}")

            logger.info(f"Adopted existing section '{section_name}' in {guild.name}")

            return {
                "success": True,
                "message": f"Using existing broadcast section '{section_name}' with {len(listener_channels)} listener channels",
                "section": section,
                "was_existing": True,
                "adopted": True,
                "simple_message": f"✅ Using existing broadcast section '{section_name}'! Go to the control channel and use `!start_broadcast` to begin.",
            }

        except Exception as e:
            logger.error(f"Error adopting existing category: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Failed to adopt existing category: {str(e)}",
            }

    async def _create_new_section(
        self,
        guild: discord.Guild,
        category: discord.CategoryChannel,
        section_name: str,
        listener_count: int,
    ) -> Dict[str, Any]:
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
            # Create control text channel
            control_channel = await category.create_text_channel(
                name="broadcast-control",
                topic=f"Control channel for {section_name} broadcast section",
                reason="Creating control channel",
            )

            # Create speaker channel
            speaker_channel = await category.create_voice_channel(
                name="Speaker",
                bitrate=96000,  # Discord's maximum bitrate
                user_limit=10,
                reason="Creating speaker channel",
            )

            # Create listener channels
            listener_channel_ids = []
            for i in range(1, listener_count + 1):
                listener_channel = await category.create_voice_channel(
                    name=f"Channel-{i}",
                    bitrate=96000,  # Discord's maximum bitrate
                    user_limit=0,
                    reason=f"Creating listener channel {i}",
                )
                listener_channel_ids.append(listener_channel.id)

            # Set up voice channel permissions using access control
            permission_setup_success = False
            if self.access_control:
                logger.info("Setting up access control and roles...")
                # Ensure required roles exist
                roles = await self.access_control.ensure_roles_exist(guild)
                speaker_role = roles.get("speaker_role")
                broadcast_admin_role = roles.get("broadcast_admin_role")
                
                logger.info(f"Roles setup: speaker_role={speaker_role}, broadcast_admin_role={broadcast_admin_role}")

                # Set up voice channel permissions
                permission_setup_success = (
                    await self.access_control.setup_voice_channel_permissions(
                        speaker_channel,
                        [
                            guild.get_channel(cid)
                            for cid in listener_channel_ids
                            if guild.get_channel(cid)
                        ],
                        broadcast_admin_role,
                        speaker_role,
                    )
                )
                logger.info(f"Voice channel permission setup: {'success' if permission_setup_success else 'failed'}")
            else:
                logger.warning("No access control configured - skipping role and permission setup")

            # Set up control channel permissions (restricted to broadcast admins)
            # This should be independent of voice channel permission setup success
            control_channel_permissions_set = False
            if self.access_control:
                logger.info("Setting up control channel permissions...")
                try:
                    # Check if bot has manage channels permission before attempting
                    if guild.me.guild_permissions.manage_channels:
                        # Deny access to @everyone
                        await control_channel.set_permissions(
                            guild.default_role,
                            read_messages=False,
                            send_messages=False,
                        )

                        # Allow bot full access
                        await control_channel.set_permissions(
                            guild.me,
                            read_messages=True,
                            send_messages=True,
                            manage_messages=True,
                            embed_links=True,
                        )

                        # Allow broadcast admin role access
                        if broadcast_admin_role:
                            await control_channel.set_permissions(
                                broadcast_admin_role,
                                read_messages=True,
                                send_messages=True,
                                embed_links=True,
                            )

                        control_channel_permissions_set = True
                        logger.info(
                            f"Set up control channel permissions for: {control_channel.name}"
                        )
                    else:
                        logger.warning(
                            "Bot lacks 'Manage Channels' permission - control channel will remain public"
                        )
                except discord.Forbidden:
                    logger.warning(
                        f"Cannot set control channel permissions: {control_channel.name}"
                    )
                    # Channel will remain public - not ideal but functional
                except Exception as e:
                    logger.error(f"Unexpected error setting control channel permissions: {e}", exc_info=True)
            else:
                logger.warning("No access control configured - control channel will remain public")
            
            logger.info(f"Control channel permission setup: {'success' if control_channel_permissions_set else 'failed or skipped'}")

            # Create broadcast section
            section = BroadcastSection(
                guild_id=guild.id,
                section_name=section_name,
                speaker_channel_id=speaker_channel.id,
                listener_channel_ids=listener_channel_ids,
            )
            section.category_id = category.id
            section.control_channel_id = control_channel.id

            self.active_sections[guild.id] = section

            # Send welcome message (if bot has permission)
            welcome_message_sent = False
            try:
                embed = discord.Embed(
                    title=f"🎵 {section_name} Broadcast Section Created!",
                    description="Your broadcast section is ready to use!",
                    color=discord.Color.green(),
                )
                embed.add_field(
                    name="🎤 Speaker Channel",
                    value=f"<#{speaker_channel.id}>",
                    inline=True,
                )
                embed.add_field(
                    name="📢 Listener Channels",
                    value=f"{listener_count} channels created",
                    inline=True,
                )
                embed.add_field(
                    name="🎛️ Control Channel",
                    value=f"<#{control_channel.id}>",
                    inline=True,
                )
                embed.add_field(
                    name="🎛️ Available Commands",
                    value="• `!stop_broadcast` - Stop broadcasting and remove entire section\n"
                    "• `!broadcast_status` - Check broadcast status\n"
                    "• `!system_status` - Check system health",
                    inline=False,
                )

                # Add role information and setup guidance
                if self.access_control and control_channel_permissions_set:
                    role_info = []
                    if speaker_role:
                        role_info.append(
                            f"• **{speaker_role.name}** - Required to join speaker channel"
                        )
                    if broadcast_admin_role:
                        role_info.append(
                            f"• **{broadcast_admin_role.name}** - Required to use bot commands"
                        )

                    if role_info:
                        embed.add_field(
                            name="👥 Role Information",
                            value="\n".join(role_info),
                            inline=False,
                        )

                        embed.add_field(
                            name="📝 Setup Instructions",
                            value="**To get started:**\n"
                            "1. **Assign Roles:** Give users the appropriate roles\n"
                            "2. **Join Channels:**\n"
                            f"   • Speakers join: <#{speaker_channel.id}>\n"
                            f"   • Listeners join: <#{listener_channel_ids[0] if listener_channel_ids else 'N/A'}> (and others)\n"
                            "3. **Need Help?** Run `!help` for full setup guide",
                            inline=False,
                        )

                await control_channel.send(embed=embed)
                welcome_message_sent = True
                logger.info(
                    f"Sent welcome message to control channel: {control_channel.name}"
                )
            except discord.Forbidden:
                logger.warning(
                    f"Cannot send welcome message to control channel: {control_channel.name} - bot lacks send message permission"
                )
                # Try to fix permissions and send message again
                try:
                    logger.info("Attempting to fix control channel permissions...")
                    if guild.me.guild_permissions.manage_channels:
                        # Try to give bot permission to send messages
                        await control_channel.set_permissions(
                            guild.me,
                            read_messages=True,
                            send_messages=True,
                            manage_messages=True,
                            embed_links=True,
                        )
                        # Try sending message again
                        await control_channel.send(embed=embed)
                        welcome_message_sent = True
                        logger.info("Successfully sent welcome message after fixing permissions")
                    else:
                        logger.error("Bot lacks 'Manage Channels' permission - cannot fix control channel permissions")
                except Exception as fix_error:
                    logger.error(f"Failed to fix permissions and send welcome message: {fix_error}")
            except Exception as e:
                logger.warning(f"Failed to send welcome message: {e}")
            
            if not welcome_message_sent:
                logger.error(f"CRITICAL: Could not send welcome message to control channel {control_channel.name} - users will not see setup instructions!")

            logger.info(
                f"Created broadcast section '{section_name}' in {guild.name} with {listener_count} listeners"
            )

            return {
                "success": True,
                "message": f"Broadcast section '{section_name}' created successfully!",
                "section": section,
                "category_id": category.id,
                "control_channel_id": control_channel.id,
                "was_existing": False,
                "simple_message": f"✅ Broadcast section '{section_name}' created! Go to the control channel and use `!start_broadcast` to begin.",
            }

        except Exception as e:
            logger.error(f"Error creating new section: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Failed to create broadcast section: {str(e)}",
            }

    async def create_broadcast_section(
        self, guild: discord.Guild, section_name: str, listener_count: int
    ) -> Dict[str, Any]:
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
                    "success": True,
                    "message": f"Using existing broadcast section '{existing_section.section_name}'",
                    "section": existing_section,
                    "was_existing": True,
                    "simple_message": f"✅ Using existing broadcast section '{existing_section.section_name}'! Go to the control channel and use `!start_broadcast` to begin.",
                }

            # Check if a category with the same name already exists (exact match only)
            existing_category = discord.utils.get(
                guild.categories, name=section_name
            ) or discord.utils.get(
                guild.categories, name=f"🔴 {section_name}"
            )
            
            if existing_category:
                # Check if the existing category has the correct structure
                structure_valid, validation_message = self._validate_section_structure(
                    existing_category, listener_count
                )
                
                if structure_valid:
                    # Structure is correct, adopt the existing section
                    return await self._adopt_existing_category(
                        guild, existing_category, section_name, listener_count
                    )
                else:
                    # Structure is incorrect, return error
                    return {
                        "success": False,
                        "message": f"Section '{section_name}' already exists but has a different structure. {validation_message}",
                        "simple_message": f"❌ Section '{section_name}' already exists with different channels. Please use a different section name or delete the existing section first.",
                    }

            # No existing section found, create a new one
            category_name = f"🔴 {section_name}"
            category = await guild.create_category(
                name=category_name,
                reason=f"Creating broadcast section: {section_name}",
            )
            
            # Position the category at the top for maximum visibility
            try:
                await category.edit(position=0)
                logger.info(f"Positioned category '{category_name}' at the top")
            except discord.Forbidden:
                logger.warning("Could not position category at top - insufficient permissions")
            except Exception as e:
                logger.warning(f"Could not position category at top: {e}")

            # Use the helper method to create the section
            return await self._create_new_section(
                guild, category, section_name, listener_count
            )

        except Exception as e:
            logger.error(
                f"Error creating broadcast section in {guild.name}: {e}", exc_info=True
            )
            return {
                "success": False,
                "message": f"Failed to create broadcast section: {str(e)}",
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
                    "success": False,
                    "message": "No active broadcast section found in this server!",
                }

            section = self.active_sections[guild.id]

            if section.is_active:
                return {
                    "success": False,
                    "message": "Broadcast is already active for this section!",
                }

            # Start speaker bot process
            speaker_bot_id = await self.process_manager.start_speaker_bot(
                section.speaker_channel_id, guild.id
            )
            if not speaker_bot_id:
                return {
                    "success": False,
                    "message": "Failed to start speaker bot process!",
                }

            # Start listener bot processes with improved batch processing
            # Sort listener channels by numeric order (Channel-1, Channel-2, Channel-3, etc.)
            def extract_channel_number(channel_id):
                """Extract the numeric part from channel name for proper sorting."""
                channel = guild.get_channel(channel_id)
                if not channel:
                    return float('inf')  # Put unknown channels at the end
                
                # Extract number from "group-X" format
                import re
                match = re.search(r'group-(\d+)', channel.name)
                if match:
                    return int(match.group(1))
                else:
                    return float('inf')  # Put non-group channels at the end
            
            sorted_listener_channel_ids = sorted(
                section.listener_channel_ids,
                key=extract_channel_number
            )
            
            # Log the sorted channel order for debugging
            channel_names = []
            for cid in sorted_listener_channel_ids:
                channel = guild.get_channel(cid)
                channel_names.append(channel.name if channel else f"Unknown({cid})")
            
            logger.info(f"Starting {len(sorted_listener_channel_ids)} listener bots in batches...")
            logger.info(f"Channel order: {channel_names}")
            
            batch_size = 10
            listener_bot_ids = []
            failed_channels = []
            
            for i in range(0, len(sorted_listener_channel_ids), batch_size):
                batch = sorted_listener_channel_ids[i:i + batch_size]
                logger.info(f"Starting batch {i//batch_size + 1}: channels {[guild.get_channel(cid).name if guild.get_channel(cid) else cid for cid in batch]}")
                
                # Start all bots in this batch concurrently
                batch_tasks = []
                for channel_id in batch:
                    task = self.process_manager.start_listener_bot(
                        channel_id, guild.id, section.speaker_channel_id
                    )
                    batch_tasks.append((channel_id, task))
                
                # Wait for all bots in this batch to start
                for channel_id, task in batch_tasks:
                    try:
                        listener_bot_id = await task
                        if listener_bot_id:
                            listener_bot_ids.append(listener_bot_id)
                            channel_name = guild.get_channel(channel_id).name if guild.get_channel(channel_id) else str(channel_id)
                            logger.info(f"✅ Started listener bot for {channel_name} (ID: {listener_bot_id})")
                        else:
                            failed_channels.append(channel_id)
                            channel_name = guild.get_channel(channel_id).name if guild.get_channel(channel_id) else str(channel_id)
                            logger.warning(f"❌ Failed to start listener bot for {channel_name}")
                    except Exception as e:
                        failed_channels.append(channel_id)
                        channel_name = guild.get_channel(channel_id).name if guild.get_channel(channel_id) else str(channel_id)
                        logger.error(f"❌ Exception starting listener bot for {channel_name}: {e}")
                
                # Add a small delay between batches to avoid rate limiting
                if i + batch_size < len(sorted_listener_channel_ids):
                    logger.info("Waiting 2 seconds before starting next batch...")
                    await asyncio.sleep(2)
            
            # Retry failed channels once
            if failed_channels:
                logger.info(f"Retrying {len(failed_channels)} failed channels...")
                retry_tasks = []
                for channel_id in failed_channels:
                    task = self.process_manager.start_listener_bot(
                        channel_id, guild.id, section.speaker_channel_id
                    )
                    retry_tasks.append((channel_id, task))
                
                for channel_id, task in retry_tasks:
                    try:
                        listener_bot_id = await task
                        if listener_bot_id:
                            listener_bot_ids.append(listener_bot_id)
                            channel_name = guild.get_channel(channel_id).name if guild.get_channel(channel_id) else str(channel_id)
                            logger.info(f"✅ Retry successful for {channel_name} (ID: {listener_bot_id})")
                    except Exception as e:
                        channel_name = guild.get_channel(channel_id).name if guild.get_channel(channel_id) else str(channel_id)
                        logger.error(f"❌ Retry failed for {channel_name}: {e}")
            
            logger.info(f"Successfully started {len(listener_bot_ids)} out of {len(sorted_listener_channel_ids)} listener bots")

            if not listener_bot_ids:
                # Stop speaker bot if no listeners started
                await self.process_manager.stop_bot(speaker_bot_id)
                return {
                    "success": False,
                    "message": "Failed to start any listener bot processes!",
                }

            # Update section with successful connections
            section.speaker_bot_id = speaker_bot_id
            section.listener_bot_ids = listener_bot_ids

            section.is_active = True

            logger.info(
                f"Started broadcast for section '{section.section_name}' in {guild.name}"
            )

            return {
                "success": True,
                "message": f"Broadcast started for section '{section.section_name}'!",
                "speaker_channel": section.speaker_channel_id,
                "listener_count": len(listener_bot_ids),
            }

        except Exception as e:
            logger.error(f"Error starting broadcast in {guild.name}: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Failed to start broadcast: {str(e)}",
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
                    "success": False,
                    "message": "No active broadcast section found in this server!",
                }

            section = self.active_sections[guild.id]

            if not section.is_active:
                return {
                    "success": False,
                    "message": "Broadcast is not active for this section!",
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

            logger.info(
                f"Stopped broadcast for section '{section.section_name}' in {guild.name}"
            )

            return {
                "success": True,
                "message": f"Broadcast stopped for section '{section.section_name}'!",
            }

        except Exception as e:
            logger.error(f"Error stopping broadcast in {guild.name}: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Failed to stop broadcast: {str(e)}",
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
                    "success": False,
                    "message": "No active broadcast section found in this server!",
                }

            section = self.active_sections[guild.id]

            # Stop broadcast if active
            if section.is_active:
                await self.stop_broadcast(guild)

            # Stop all bot processes for this guild
            await self.process_manager.stop_bots_by_guild(guild.id)

            # Find and delete the category (check both with and without icon prefix)
            for category in guild.categories:
                if (category.name == section.section_name or 
                    category.name == f"🔴 {section.section_name}"):
                    for channel in category.channels:
                        await channel.delete(
                            reason="Cleaning up broadcast section"
                        )
                    await category.delete(
                        reason="Cleaning up broadcast section"
                    )
                    break

            # Remove from active sections
            del self.active_sections[guild.id]

            logger.info(
                f"Cleaned up section '{section.section_name}' in {guild.name}"
            )

            return {
                "success": True,
                "message": f"Broadcast section '{section.section_name}' cleaned up successfully!",
            }

        except Exception as e:
            logger.error(f"Error cleaning up section in {guild.name}: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Failed to cleanup section: {str(e)}",
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
                "active": False,
                "message": "No active broadcast section in this server",
            }

        section = self.active_sections[guild.id]

        return {
            "active": True,
            "section_name": section.section_name,
            "is_broadcasting": section.is_active,
            "speaker_channel_id": section.speaker_channel_id,
            "listener_count": len(section.listener_channel_ids),
            "listener_channel_ids": section.listener_channel_ids,
        }
