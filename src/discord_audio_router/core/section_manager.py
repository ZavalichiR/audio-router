"""
Section Manager for handling broadcast sections.

This module manages broadcast sections, including channel creation,
bot deployment, and audio routing coordination.
"""

import asyncio
from typing import Any, Dict, List, Optional

import discord

from discord_audio_router.infrastructure.logging import setup_logging

from .access_control import AccessControl
from .bot_manager import BotManager

# Configure logging
logger = setup_logging(
    component_name="section_manager",
    log_file="logs/section_manager.log",
)

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
        self.speaker_bot_id: Optional[str] = None
        self.listener_bot_ids: List[str] = []
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

    Handles the creation, management, and cleanup of broadcast sections,
    including channel creation and bot deployment.
    """

    def __init__(
        self,
        bot_manager: BotManager,
        access_control: Optional[AccessControl] = None,
    ):
        """
        Initialize the section manager.

        Args:
            bot_manager: Bot manager instance
            access_control: Access control instance (optional)
        """
        self.bot_manager = bot_manager
        self.access_control = access_control
        self.active_sections: Dict[int, BroadcastSection] = {}

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

        speaker_channel = next(
            (ch for ch in voice_channels if "🎤" in ch.name or "speaker" in ch.name.lower()), None
        )
        listener_channels = [
            ch for ch in voice_channels if ch.name.startswith("Channel-") and ch.name[8:].isdigit()
        ]
        control_channel = next(
            (ch for ch in text_channels if "control" in ch.name.lower() or "broadcast" in ch.name.lower()),
            None,
        )

        if not speaker_channel:
            return False, "Missing speaker channel"
        if not listener_channels:
            return False, "No listener channels found (expected Channel-1, Channel-2, etc.)"
        if len(listener_channels) != expected_listener_count:
            return False, f"Expected {expected_listener_count} listener channels, found {len(listener_channels)}"
        if not control_channel:
            return False, "Missing control channel"

        expected_numbers = set(range(1, expected_listener_count + 1))
        actual_numbers = set()
        for channel in listener_channels:
            try:
                num = int(channel.name[8:])
                actual_numbers.add(num)
            except ValueError:
                return False, f"Invalid listener channel name: {channel.name}"

        if expected_numbers != actual_numbers:
            return False, f"Listener channels not properly numbered. Expected Channel-1 to Channel-{expected_listener_count}"

        return True, "Structure is valid"

    async def _adopt_existing_category(
        self,
        guild: discord.Guild,
        existing_category: discord.CategoryChannel,
        section_name: str,
        role_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Adopt an existing category that has been validated to have the correct structure.

        Args:
            guild: Discord guild
            existing_category: Existing category to adopt (already validated)
            section_name: Name of the section
            role_name: Optional role name for category visibility restriction

        Returns:
            Dict with adoption results
        """
        try:
            if not guild.me.guild_permissions.manage_channels or not guild.me.guild_permissions.manage_roles:
                return {
                    "success": False,
                    "message": "Bot lacks 'Manage Channels' or 'Manage Roles' permissions",
                }

            voice_channels = [ch for ch in existing_category.channels if isinstance(ch, discord.VoiceChannel)]
            text_channels = [ch for ch in existing_category.channels if isinstance(ch, discord.TextChannel)]

            speaker_channel = next(
                (ch for ch in voice_channels if "🎤" in ch.name or "speaker" in ch.name.lower()), None
            )
            listener_channels = [
                ch for ch in voice_channels if ch.name.startswith("Channel-") and ch.name[8:].isdigit()
            ]
            control_channel = next(
                (ch for ch in text_channels if "control" in ch.name.lower() or "broadcast" in ch.name.lower()),
                None,
            )

            def sort_key(channel):
                return int(channel.name[8:])

            listener_channels.sort(key=sort_key)

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=True),
                guild.me: discord.PermissionOverwrite(view_channel=True, manage_channels=True),
            }
            if role_name:
                target_role = discord.utils.get(guild.roles, name=role_name)
                if target_role:
                    overwrites[guild.default_role] = discord.PermissionOverwrite(view_channel=False)
                    overwrites[target_role] = discord.PermissionOverwrite(view_channel=True)
            
            # Always ensure Speaker and Listener roles can see the category (for bots)
            speaker_role = discord.utils.get(guild.roles, name="Speaker")
            listener_role = discord.utils.get(guild.roles, name="Listener")
            if speaker_role:
                overwrites[speaker_role] = discord.PermissionOverwrite(view_channel=True)
            if listener_role:
                overwrites[listener_role] = discord.PermissionOverwrite(view_channel=True)

            await existing_category.edit(overwrites=overwrites)

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

            if self.access_control:
                roles = await self.access_control.ensure_roles_exist(guild, role_name)
                speaker_role = roles.get("speaker_role")
                listener_role = roles.get("listener_role")
                broadcast_admin_role = roles.get("broadcast_admin_role")
                custom_role = roles.get("custom_role")

                if speaker_channel:
                    await self.access_control.setup_voice_channel_permissions(
                        speaker_channel,
                        listener_channels,
                        broadcast_admin_role,
                        speaker_role,
                        listener_role,
                        custom_role,
                    )

                if control_channel and guild.me.guild_permissions.manage_channels:
                    try:
                        control_overwrites = {
                            guild.default_role: discord.PermissionOverwrite(read_messages=False, send_messages=False),
                            guild.me: discord.PermissionOverwrite(
                                read_messages=True, send_messages=True, manage_messages=True, embed_links=True
                            ),
                            broadcast_admin_role: discord.PermissionOverwrite(
                                read_messages=True, send_messages=True, embed_links=True
                            ) if broadcast_admin_role else None,
                            custom_role: discord.PermissionOverwrite(
                                read_messages=True, send_messages=True, embed_links=True
                            ) if custom_role else None,
                        }
                        for role, overwrite in control_overwrites.items():
                            if role and overwrite:
                                await control_channel.set_permissions(role, overwrite=overwrite)
                        logger.info(f"Set up control channel permissions for: {control_channel.name}")
                    except discord.Forbidden:
                        logger.warning(f"Cannot set control channel permissions for: {control_channel.name}")

            logger.info(f"Adopted existing section '{section_name}' in {guild.name}")

            return {
                "success": True,
                "message": f"Using existing broadcast section '{section_name}' with {len(listener_channels)} listener channels",
                "section": section,
                "was_existing": True,
                "adopted": True,
                "simple_message": f"✅ Using existing broadcast section '{section_name}'! Go to the control channel and use `!start_broadcast` to begin.",
            }

        except discord.Forbidden:
            logger.error("Bot lacks permissions to adopt category")
            return {"success": False, "message": "Bot lacks permissions to adopt category"}
        except Exception as e:
            logger.error(f"Error adopting existing category: {e}", exc_info=True)
            return {"success": False, "message": f"Failed to adopt existing category: {str(e)}"}

    async def _create_new_section(
        self,
        guild: discord.Guild,
        category: discord.CategoryChannel,
        section_name: str,
        listener_count: int,
        role_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new broadcast section with the given category.

        Args:
            guild: Discord guild
            category: Category to use for the section
            section_name: Name of the section
            listener_count: Number of listener channels to create
            role_name: Optional role name for category visibility restriction

        Returns:
            Dict with creation results
        """
        try:
            if not guild.me.guild_permissions.manage_channels or not guild.me.guild_permissions.manage_roles:
                return {
                    "success": False,
                    "message": "Bot lacks 'Manage Channels' or 'Manage Roles' permissions",
                }

            if listener_count < 0:
                return {"success": False, "message": "Listener count cannot be negative"}

            control_channel = await category.create_text_channel(
                name="broadcast-control",
                topic=f"Control channel for {section_name} broadcast section",
                reason="Creating control channel",
            )

            speaker_channel = await category.create_voice_channel(
                name="Speaker",
                bitrate=96000,
                user_limit=10,
                reason="Creating speaker channel",
            )

            listener_channel_ids = []
            for i in range(1, listener_count + 1):
                listener_channel = await category.create_voice_channel(
                    name=f"Channel-{i}",
                    bitrate=96000,
                    user_limit=0,
                    reason=f"Creating listener channel {i}",
                )
                listener_channel_ids.append(listener_channel.id)

            if self.access_control:
                roles = await self.access_control.ensure_roles_exist(guild, role_name)
                speaker_role = roles.get("speaker_role")
                listener_role = roles.get("listener_role")
                broadcast_admin_role = roles.get("broadcast_admin_role")
                custom_role = roles.get("custom_role")

                permission_setup_success = await self.access_control.setup_voice_channel_permissions(
                    speaker_channel,
                    [guild.get_channel(cid) for cid in listener_channel_ids if guild.get_channel(cid)],
                    broadcast_admin_role,
                    speaker_role,
                    listener_role,
                    custom_role,
                )
                logger.info(f"Voice channel permission setup: {'success' if permission_setup_success else 'failed'}")
            else:
                logger.warning("No access control configured - skipping role-based permission setup")

            if self.access_control and guild.me.guild_permissions.manage_channels:
                try:
                    control_overwrites = {
                        guild.default_role: discord.PermissionOverwrite(read_messages=False, send_messages=False),
                        guild.me: discord.PermissionOverwrite(
                            read_messages=True, send_messages=True, manage_messages=True, embed_links=True
                        ),
                        broadcast_admin_role: discord.PermissionOverwrite(
                            read_messages=True, send_messages=True, embed_links=True
                        ) if broadcast_admin_role else None,
                    }
                    for role, overwrite in control_overwrites.items():
                        if role and overwrite:
                            await control_channel.set_permissions(role, overwrite=overwrite)

                except discord.Forbidden:
                    logger.warning(f"Cannot set control channel permissions: {control_channel.name}")
                except Exception as e:
                    logger.error(f"Unexpected error setting control channel permissions: {e}", exc_info=True)
            else:
                logger.warning("No access control or insufficient permissions - control channel remains public")

            section = BroadcastSection(
                guild_id=guild.id,
                section_name=section_name,
                speaker_channel_id=speaker_channel.id,
                listener_channel_ids=listener_channel_ids,
            )
            section.category_id = category.id
            section.control_channel_id = control_channel.id
            self.active_sections[guild.id] = section

            welcome_message_sent = False
            try:
                embed = discord.Embed(
                    title=f"🎵 {section_name} Broadcast Section Created!",
                    description="Your broadcast section is ready to use!",
                    color=discord.Color.green(),
                )
                embed.add_field(name="🎤 Speaker Channel", value=f"<#{speaker_channel.id}>", inline=True)
                embed.add_field(name="📢 Listener Channels", value=f"{listener_count} channels created", inline=True)
                embed.add_field(name="🎛️ Control Channel", value=f"<#{control_channel.id}>", inline=True)
                embed.add_field(
                    name="🎛️ Available Commands",
                    value="• `!stop_broadcast` - Stop broadcasting and remove entire section\n"
                          "• `!broadcast_status` - Check broadcast status\n"
                          "• `!system_status` - Check system health",
                    inline=False,
                )

                if self.access_control and broadcast_admin_role:
                    role_info = []
                    if speaker_role:
                        role_info.append(f"• **{speaker_role.name}** - Required to join speaker channel")
                    if broadcast_admin_role:
                        role_info.append(f"• **{broadcast_admin_role.name}** - Required to use bot commands")
                    if role_name and custom_role:
                        role_info.append(f"• **{custom_role.name}** - Required to view the section")

                    if role_info:
                        embed.add_field(name="👥 Role Information", value="\n".join(role_info), inline=False)
                        embed.add_field(
                            name="📝 Setup Instructions",
                            value="**To get started:**\n"
                                  "1. **Assign Roles:** Give users the appropriate roles\n"
                                  f"2. **Join Channels:**\n"
                                  f"   • Speakers join: <#{speaker_channel.id}>\n"
                                  f"   • Listeners join: <#{listener_channel_ids[0] if listener_channel_ids else 'N/A'}> (and others)\n"
                                  "3. **Need Help?** Run `!help` for full setup guide",
                            inline=False,
                        )

                await control_channel.send(embed=embed)
                welcome_message_sent = True
                logger.info(f"Sent welcome message to control channel: {control_channel.name}")
            except discord.Forbidden:
                logger.warning(f"Cannot send welcome message to {control_channel.name}: Bot lacks send message permission")
                try:
                    if guild.me.guild_permissions.manage_channels:
                        await control_channel.set_permissions(
                            guild.me, read_messages=True, send_messages=True, manage_messages=True, embed_links=True
                        )
                        await control_channel.send(embed=embed)
                        welcome_message_sent = True
                        logger.info("Sent welcome message after fixing permissions")
                    else:
                        logger.error("Bot lacks 'Manage Channels' permission to fix control channel")
                except Exception as fix_error:
                    logger.error(f"Failed to fix permissions and send welcome message: {fix_error}")
            except Exception as e:
                logger.warning(f"Failed to send welcome message: {e}")

            if not welcome_message_sent:
                logger.error(f"CRITICAL: Could not send welcome message to {control_channel.name}")

            logger.info(f"Created broadcast section '{section_name}' in {guild.name} with {listener_count} listeners")

            return {
                "success": True,
                "message": f"Broadcast section '{section_name}' created successfully!",
                "section": section,
                "category_id": category.id,
                "control_channel_id": control_channel.id,
                "was_existing": False,
                "simple_message": f"✅ Broadcast section '{section_name}' created! Go to the control channel and use `!start_broadcast` to begin.",
            }

        except discord.Forbidden:
            logger.error("Bot lacks permissions to create section")
            return {"success": False, "message": "Bot lacks permissions to create section"}
        except Exception as e:
            logger.error(f"Error creating new section: {e}", exc_info=True)
            return {"success": False, "message": f"Failed to create broadcast section: {str(e)}"}

    async def create_broadcast_section(
        self,
        guild: discord.Guild,
        section_name: str,
        listener_count: int,
        role_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a broadcast section with speaker and listener channels.

        Args:
            guild: Discord guild
            section_name: Name of the section (e.g., 'War Room')
            listener_count: Number of listener channels to create
            role_name: Optional role name for category visibility restriction

        Returns:
            Dict with creation results
        """
        try:
            if not guild.me.guild_permissions.manage_channels or not guild.me.guild_permissions.manage_roles:
                return {
                    "success": False,
                    "message": "Bot lacks 'Manage Channels' or 'Manage Roles' permissions",
                }

            if guild.id in self.active_sections:
                existing_section = self.active_sections[guild.id]
                return {
                    "success": True,
                    "message": f"Using existing broadcast section '{existing_section.section_name}'",
                    "section": existing_section,
                    "was_existing": True,
                    "simple_message": f"✅ Using existing broadcast section '{existing_section.section_name}'! Go to the control channel and use `!start_broadcast` to begin.",
                }

            existing_category = discord.utils.get(guild.categories, name=section_name) or discord.utils.get(
                guild.categories, name=f"🔴 {section_name}"
            )

            if existing_category:
                structure_valid, validation_message = self._validate_section_structure(existing_category, listener_count)
                if structure_valid:
                    return await self._adopt_existing_category(guild, existing_category, section_name, role_name)
                else:
                    return {
                        "success": False,
                        "message": f"Section '{section_name}' already exists but has a different structure. {validation_message}",
                        "simple_message": f"❌ Section '{section_name}' already exists with different channels. Use a different name or delete the existing section.",
                    }

            category_name = f"🔴 {section_name}"
            category_overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=True),
            }
            if role_name:
                target_role = discord.utils.get(guild.roles, name=role_name)
                if target_role:
                    category_overwrites[guild.default_role] = discord.PermissionOverwrite(view_channel=False)
                    category_overwrites[target_role] = discord.PermissionOverwrite(view_channel=True)
            
            category = await guild.create_category(
                name=category_name,
                overwrites=category_overwrites,
                reason=f"Creating broadcast section: {section_name}",
            )

            try:
                await category.edit(position=0)
            except discord.Forbidden:
                logger.warning("Could not position category at top: Insufficient permissions")
            except discord.HTTPException as e:
                logger.warning(f"Could not position category at top: {e}")

            return await self._create_new_section(guild, category, section_name, listener_count, role_name)

        except discord.Forbidden:
            logger.error("Bot lacks permissions to create category")
            return {"success": False, "message": "Bot lacks permissions to create category"}
        except Exception as e:
            logger.error(f"Error creating broadcast section in {guild.name}: {e}", exc_info=True)
            return {"success": False, "message": f"Failed to create broadcast section: {str(e)}"}

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
                return {"success": False, "message": "No active broadcast section found in this server!"}

            section = self.active_sections[guild.id]
            if section.is_active:
                return {"success": False, "message": "Broadcast is already active for this section!"}

            speaker_bot_id = await self.bot_manager.start_speaker_bot(section.speaker_channel_id, guild.id)
            if not speaker_bot_id:
                return {"success": False, "message": "Failed to start speaker bot process!"}

            def extract_channel_number(channel_id):
                channel = guild.get_channel(channel_id)
                if not channel:
                    return float("inf")
                import re
                match = re.search(r"Channel-(\d+)", channel.name)
                return int(match.group(1)) if match else float("inf")

            sorted_listener_channel_ids = sorted(section.listener_channel_ids, key=extract_channel_number)
            batch_size = 10
            listener_bot_ids = []
            failed_channels = []

            for i in range(0, len(sorted_listener_channel_ids), batch_size):
                batch = sorted_listener_channel_ids[i : i + batch_size]
                logger.info(f"Starting batch {i // batch_size + 1}: channels {[guild.get_channel(cid).name if guild.get_channel(cid) else cid for cid in batch]}")

                batch_tasks = [
                    (channel_id, self.bot_manager.start_listener_bot(channel_id, guild.id, section.speaker_channel_id))
                    for channel_id in batch
                ]

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

                if i + batch_size < len(sorted_listener_channel_ids):
                    logger.info("Waiting 2 seconds before starting next batch...")
                    await asyncio.sleep(2)

            if failed_channels:
                logger.info(f"Retrying {len(failed_channels)} failed channels...")
                retry_tasks = [
                    (channel_id, self.bot_manager.start_listener_bot(channel_id, guild.id, section.speaker_channel_id))
                    for channel_id in failed_channels
                ]

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
                await self.bot_manager.stop_bot(speaker_bot_id)
                return {"success": False, "message": "Failed to start any listener bot processes!"}

            section.speaker_bot_id = speaker_bot_id
            section.listener_bot_ids = listener_bot_ids
            section.is_active = True

            logger.info(f"Started broadcast for section '{section.section_name}' in {guild.name}")

            return {
                "success": True,
                "message": f"Broadcast started for section '{section.section_name}'!",
                "speaker_channel": section.speaker_channel_id,
                "listener_count": len(listener_bot_ids),
            }

        except Exception as e:
            logger.error(f"Error starting broadcast in {guild.name}: {e}", exc_info=True)
            return {"success": False, "message": f"Failed to start broadcast: {str(e)}"}

    async def stop_broadcast(self, guild: discord.Guild) -> Dict[str, Any]:
        """
        Clean up an entire broadcast section.

        Args:
            guild: Discord guild

        Returns:
            Dict with cleanup results
        """
        try:
            if guild.id not in self.active_sections:
                return {"success": False, "message": "No active broadcast section found in this server!"}

            section = self.active_sections[guild.id]
            if section.is_active:
                # Stop all bots concurrently for better performance
                stop_tasks = []
                
                if section.speaker_bot_id:
                    stop_tasks.append(self.bot_manager.stop_bot(section.speaker_bot_id))
                
                for listener_bot_id in section.listener_bot_ids:
                    stop_tasks.append(self.bot_manager.stop_bot(listener_bot_id))
                
                # Wait for all bots to stop concurrently
                if stop_tasks:
                    logger.info(f"Stopping {len(stop_tasks)} bot processes concurrently...")
                    results = await asyncio.gather(*stop_tasks, return_exceptions=True)
                    
                    # Log any failures
                    for i, result in enumerate(results):
                        if isinstance(result, Exception):
                            logger.error(f"Bot stop task {i} failed: {result}")
                        elif not result:
                            logger.warning(f"Bot stop task {i} returned False")

                section.speaker_bot_id = None
                section.listener_bot_ids.clear()
                section.is_active = False

            for category in guild.categories:
                if category.name == section.section_name or category.name == f"🔴 {section.section_name}":
                    for channel in category.channels:
                        try:
                            await channel.delete(reason="Cleaning up broadcast section")
                        except discord.Forbidden:
                            logger.warning(f"Cannot delete channel {channel.name}: Insufficient permissions")
                    try:
                        await category.delete(reason="Cleaning up broadcast section")
                    except discord.Forbidden:
                        logger.warning(f"Cannot delete category {category.name}: Insufficient permissions")
                    break

            del self.active_sections[guild.id]
            logger.info(f"Cleaned up section '{section.section_name}' in {guild.name}")

            return {
                "success": True,
                "message": f"Broadcast section '{section.section_name}' cleaned up successfully!",
            }

        except discord.Forbidden:
            logger.error("Bot lacks permissions to cleanup section")
            return {"success": False, "message": "Bot lacks permissions to cleanup section"}
        except Exception as e:
            logger.error(f"Error cleaning up section in {guild.name}: {e}", exc_info=True)
            return {"success": False, "message": f"Failed to cleanup section: {str(e)}"}

    async def get_section_status(self, guild: discord.Guild) -> Dict[str, Any]:
        """
        Get the status of a broadcast section.

        Args:
            guild: Discord guild

        Returns:
            Dict with status information
        """
        if guild.id not in self.active_sections:
            return {"active": False, "message": "No active broadcast section in this server"}

        section = self.active_sections[guild.id]
        return {
            "active": True,
            "section_name": section.section_name,
            "is_broadcasting": section.is_active,
            "speaker_channel_id": section.speaker_channel_id,
            "listener_count": len(section.listener_channel_ids),
            "listener_channel_ids": section.listener_channel_ids,
        }
