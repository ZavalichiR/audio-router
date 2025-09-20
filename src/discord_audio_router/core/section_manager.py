"""
Section Manager for handling broadcast sections.

This module manages broadcast sections, including channel creation,
bot deployment, and audio routing coordination.
"""

import asyncio
import time
from typing import Any, Dict, List, Optional

import discord

from discord_audio_router.infrastructure.logging import setup_logging
from .access_control import AccessControl
from .bot_manager import BotManager
from .section_storage import SectionStorage

logger = setup_logging(
    component_name="section_manager",
    log_file="logs/section_manager.log",
)


class BroadcastSection:
    """
    Represents a broadcast section with speaker and listener channels.
    """

    def __init__(
        self,
        guild_id: int,
        section_name: str,
        category_id: int,
        control_channel_id: int,
        speaker_channel_id: int,
        listener_channel_ids: List[int],
    ):
        self.guild_id = guild_id
        self.section_name = section_name
        self.category_id = category_id
        self.control_channel_id = control_channel_id
        self.speaker_channel_id = speaker_channel_id
        self.listener_channel_ids = listener_channel_ids
        self.is_active = False
        self.speaker_bot_id: Optional[str] = None
        self.listener_bot_ids: List[str] = []
        self.original_message: Optional[discord.Message] = None


class SectionManager:
    """
    Manages broadcast sections and their associated resources.
    """

    def __init__(
        self,
        bot_manager: BotManager,
        access_control: AccessControl,
        auto_cleanup_timeout: int = 10,  # minutes
    ):
        self.bot_manager = bot_manager
        self.access_control = access_control
        self.active_sections: Dict[int, BroadcastSection] = {}
        self.storage = SectionStorage()

        # Auto-cleanup configuration
        self.auto_cleanup_timeout = auto_cleanup_timeout * 60  # seconds
        self._last_activity: Dict[int, float] = {}
        self._cleanup_task: Optional[asyncio.Task] = None

    async def recover_sections_from_storage(self, main_bot: discord.Client) -> None:
        """
        Recover broadcast sections from storage after bot restart.
        This allows the bot to rejoin existing channels instead of recreating them.
        """
        logger.info("Attempting to recover broadcast sections from storage...")

        for guild_id, section_data in self.storage.get_all_sections().items():
            try:
                guild = main_bot.get_guild(guild_id)
                if not guild:
                    logger.warning(
                        f"Guild {guild_id} not found, skipping section recovery"
                    )
                    continue

                # Try to detect the existing section
                existing_section = await self._detect_existing_section(
                    guild,
                    section_data.section_name,
                    len(section_data.listener_channel_ids),
                )

                if existing_section:
                    # Restore bot IDs from storage
                    existing_section.speaker_bot_id = section_data.speaker_bot_id
                    existing_section.listener_bot_ids = (
                        section_data.listener_bot_ids or []
                    )
                    # Don't mark as active until bots are actually started
                    existing_section.is_active = False

                    self.active_sections[guild_id] = existing_section
                    logger.info(
                        f"Recovered section '{section_data.section_name}' for guild {guild_id} (channels exist, bots need to be restarted)"
                    )
                else:
                    logger.warning(
                        f"Could not detect existing section '{section_data.section_name}' for guild {guild_id}"
                    )
                    # Remove from storage if section no longer exists
                    self.storage.remove_section(guild_id)

            except Exception as e:
                logger.error(
                    f"Failed to recover section for guild {guild_id}: {e}",
                    exc_info=True,
                )

        logger.info(
            f"Section recovery completed. Active sections: {len(self.active_sections)}"
        )

    async def _detect_existing_section(
        self, guild: discord.Guild, section_name: str, expected_listener_count: int
    ) -> Optional[BroadcastSection]:
        """
        Detect if a broadcast section already exists and can be recovered.

        Args:
            guild: Discord guild to search in
            section_name: Name of the section to look for
            expected_listener_count: Expected number of listener channels

        Returns:
            BroadcastSection if found and valid, None otherwise
        """
        category_name = f"🔴 {section_name}"

        # Find the category
        category = discord.utils.get(guild.categories, name=category_name)
        if not category:
            return None

        # Find the chat channel
        control_channel = discord.utils.get(category.channels, name="💬-chat")
        if not control_channel:
            logger.warning(f"Found category '{category_name}' but no chat channel")
            return None

        # Find the speaker channel
        speaker_channel = discord.utils.get(category.channels, name="Speaker")
        if not speaker_channel:
            logger.warning(f"Found category '{category_name}' but no speaker channel")
            return None

        # Find listener channels
        listener_channels = []
        for channel in category.channels:
            if channel.name.startswith("Channel-") and isinstance(
                channel, discord.VoiceChannel
            ):
                listener_channels.append(channel)

        # Sort by channel number for consistency
        def extract_channel_number(channel):
            import re

            match = re.search(r"Channel-(\d+)", channel.name)
            return int(match.group(1)) if match else float("inf")

        listener_channels.sort(key=extract_channel_number)

        # Check if we have the expected number of listener channels
        if len(listener_channels) != expected_listener_count:
            logger.warning(
                f"Found {len(listener_channels)} listener channels, expected {expected_listener_count}"
            )
            return None

        # Create the section object
        section = BroadcastSection(
            guild_id=guild.id,
            section_name=section_name,
            category_id=category.id,
            control_channel_id=control_channel.id,
            speaker_channel_id=speaker_channel.id,
            listener_channel_ids=[ch.id for ch in listener_channels],
        )

        logger.info(
            f"Successfully detected existing section '{section_name}' with {len(listener_channels)} listener channels"
        )
        return section

    async def start_auto_cleanup(self, main_bot: discord.Client) -> None:
        if self._cleanup_task and not self._cleanup_task.done():
            logger.debug("Auto-cleanup task already running")
            return
        self._cleanup_task = asyncio.create_task(self._auto_cleanup_loop(main_bot))
        logger.info(f"Auto-cleanup started, timeout={self.auto_cleanup_timeout // 60}m")

    async def stop_auto_cleanup(self) -> None:
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("Auto-cleanup stopped")

    async def _auto_cleanup_loop(self, main_bot: discord.Client) -> None:
        while True:
            try:
                await asyncio.sleep(60)
                await self._check_inactive_sections(main_bot)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Auto-cleanup error: {e}", exc_info=True)

    async def _check_inactive_sections(self, main_bot: discord.Client) -> None:
        now = time.time()
        to_cleanup: List[int] = []

        for guild_id, section in self.active_sections.items():
            if not section.is_active:
                continue

            empty = await self._is_speaker_channel_empty(main_bot, section)
            last = self._last_activity.get(guild_id, now)

            if empty:
                # Channel is empty - check if timeout has been reached
                if now - last >= self.auto_cleanup_timeout:
                    to_cleanup.append(guild_id)
                else:
                    # Timeout not reached yet - set default for first time tracking
                    # This only sets the value if the key doesn't exist (first time)
                    self._last_activity.setdefault(guild_id, now)
            else:
                # Channel has activity - only update if we're not already tracking an empty channel
                # This prevents resetting the timer when speaker rejoins after leaving
                if guild_id not in self._last_activity:
                    self._last_activity[guild_id] = now

        # Clean up sections that have timed out
        for guild_id in to_cleanup:
            logger.info(f"Cleaning up inactive section for guild {guild_id}")
            guild = main_bot.get_guild(guild_id)
            if guild:
                await self.stop_broadcast(guild)
            else:
                logger.warning(f"Guild {guild_id} not in cache")

            # Clean up activity tracking for removed sections
            self._last_activity.pop(guild_id, None)

    async def _is_speaker_channel_empty(
        self, main_bot: discord.Client, section: BroadcastSection
    ) -> bool:
        guild = main_bot.get_guild(section.guild_id)
        if not guild:
            return True
        channel = guild.get_channel(section.speaker_channel_id)
        if not isinstance(channel, discord.VoiceChannel):
            return True
        human = [m for m in channel.members if not m.bot]
        return len(human) == 0

    async def create_broadcast_section(
        self,
        guild: discord.Guild,
        section_name: str,
        listener_count: int,
        custom_role_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        # Precondition checks
        if listener_count < 0:
            return {"success": False, "message": "Listener count cannot be negative"}
        if guild.id in self.active_sections:
            sec = self.active_sections[guild.id]
            return {
                "success": True,
                "message": f"Section '{sec.section_name}' already exists",
                "section": sec,
            }

        category_name = f"🔴 {section_name}"

        # Check if section already exists and try to recover it
        existing_section = await self._detect_existing_section(
            guild, section_name, listener_count
        )
        if existing_section:
            logger.info(
                f"Found existing broadcast section '{section_name}', recovering..."
            )
            self.active_sections[guild.id] = existing_section
            return {
                "success": True,
                "message": f"Recovered existing section '{section_name}'",
                "section": existing_section,
            }

        # Note: We no longer clean up existing sections here because
        # our new logic always tries to reuse existing channels first.
        # If we reach this point, it means no existing section was found
        # and we should create a new one.

        # Ensure roles
        roles = await self.access_control.ensure_roles_exist(guild, custom_role_name)

        # 1. Create category with overwrites
        cat_overwrites = self.access_control.get_category_overwrites(guild, roles)
        category = await guild.create_category(
            name=category_name,
            overwrites=cat_overwrites,
            reason="Broadcast section creation",
        )
        try:
            await category.edit(position=0)
        except discord.Forbidden:
            logger.warning(
                "Could not position category at top: Insufficient permissions"
            )
        except discord.HTTPException as e:
            logger.warning(f"Could not position category at top: {e}")

        # 2. Create chat channel (text)
        chat_overwrites = self.access_control.get_listener_overwrites(guild, roles)
        control = await category.create_text_channel(
            name="💬-chat",
            topic=f"Discussion channel for {category_name}",
            overwrites=chat_overwrites,
            reason="Chat channel",
        )

        # 3. Create speaker channel
        sp_ow = self.access_control.get_speaker_overwrites(guild, roles)
        speaker = await category.create_voice_channel(
            name="Speaker",
            overwrites=sp_ow,
            bitrate=96000,
            user_limit=10,
            reason="Speaker channel",
        )

        # 4. Create listener channels
        ln_ow = self.access_control.get_listener_overwrites(guild, roles)
        listener_ids: List[int] = []
        for idx in range(1, listener_count + 1):
            ch = await category.create_voice_channel(
                name=f"Channel-{idx}",
                overwrites=ln_ow,
                bitrate=96000,
                user_limit=0,
                reason=f"Listener channel {idx}",
            )
            listener_ids.append(ch.id)

        # Register section
        section = BroadcastSection(
            guild_id=guild.id,
            section_name=section_name,
            category_id=category.id,
            control_channel_id=control.id,
            speaker_channel_id=speaker.id,
            listener_channel_ids=listener_ids,
        )
        self.active_sections[guild.id] = section

        # Save to storage
        self.storage.save_section(
            guild_id=guild.id,
            section_name=section_name,
            category_id=category.id,
            control_channel_id=control.id,
            speaker_channel_id=speaker.id,
            listener_channel_ids=listener_ids,
            is_active=False,  # Will be set to True when broadcast starts
        )

        logger.info(f"Created broadcast section '{section_name}' (Guild {guild.id})")

        # Send welcome message to chat channel after setup is complete
        await self._send_chat_welcome_message(control, section_name)

        return {
            "success": True,
            "section": section,
            "message": f"Broadcast section '{section_name}' created",
        }

    async def start_broadcast(self, guild: discord.Guild) -> Dict[str, Any]:
        section = self.active_sections.get(guild.id)
        if not section:
            return {"success": False, "message": "No section found"}

        # If already active, stop the current bots first before restarting
        if section.is_active:
            logger.info(
                f"Broadcast already active for section '{section.section_name}', stopping current bots..."
            )
            await self._stop_all_bots(
                section.listener_bot_ids + [section.speaker_bot_id]
            )
            section.speaker_bot_id = None
            section.listener_bot_ids = []
            section.is_active = False

        def extract_channel_number(channel_id):
            channel = guild.get_channel(channel_id)
            if not channel:
                return float("inf")
            import re

            match = re.search(r"Channel-(\d+)", channel.name)
            return int(match.group(1)) if match else float("inf")

        # Start speaker bot
        section.speaker_bot_id = await self.bot_manager.start_speaker_bot(
            section.speaker_channel_id, guild.id
        )

        # Start listener bots sequentially
        for channel_id in section.listener_channel_ids:
            lid = await self.bot_manager.start_listener_bot(
                channel_id,
                guild.id,
                section.speaker_channel_id,
                extract_channel_number(channel_id),
            )
            if lid:
                section.listener_bot_ids.append(lid)

        section.is_active = True

        # Update storage with bot IDs
        self.storage.update_section(
            guild_id=guild.id,
            is_active=True,
            speaker_bot_id=section.speaker_bot_id,
            listener_bot_ids=section.listener_bot_ids,
        )

        logger.info(f"Broadcast started for section '{section.section_name}'")
        return {"success": True}

    async def stop_broadcast(self, guild: discord.Guild) -> Dict[str, Any]:
        section = self.active_sections.get(guild.id)
        if not section:
            return {"success": False, "message": "No section to stop"}

        await self._stop_all_bots(section.listener_bot_ids + [section.speaker_bot_id])

        # Clean up channels & category
        category = discord.utils.get(guild.categories, id=section.category_id)
        if category:
            for ch in category.channels:
                try:
                    await ch.delete(reason="Broadcast cleanup")
                except Exception:
                    pass
            try:
                await category.delete(reason="Broadcast cleanup")
            except Exception:
                pass

        # Update storage
        self.storage.update_section(
            guild_id=guild.id,
            is_active=False,
            speaker_bot_id=None,
            listener_bot_ids=[],
        )

        del self.active_sections[guild.id]

        # Clean up activity tracking for this section
        self._last_activity.pop(guild.id, None)

        logger.info(f"Broadcast section '{section.section_name}' stopped and removed")
        return {"success": True}

    async def _stop_all_bots(self, bot_ids: List[str], batch_size: int = 10):
        semaphore = asyncio.Semaphore(batch_size)

        async def stop_one(bot_id):
            async with semaphore:
                return await self.bot_manager.stop_bot(bot_id)

        tasks = [stop_one(bot_id) for bot_id in bot_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results

    async def _send_chat_welcome_message(
        self, chat_channel: discord.TextChannel, section_name: str
    ) -> None:
        """Send welcome message to chat channel after broadcast setup is complete."""
        try:
            timeout_minutes = self.auto_cleanup_timeout // 60
            description = (
                f"🎉 **Broadcast section is ready!** You can now join the voice channels.\n\n"
                f"🤖 **Bots are connecting...** Audio forwarding will start once the bots join the channels.\n\n"
                f"💬 **Discussion:** Use this channel to discuss during the meeting or ask questions.\n\n"
                f"⏰ **Auto-cleanup:** This section will be automatically deleted in {timeout_minutes} minutes "
                f"after the speaker leaves the voice channel."
            )

            embed = discord.Embed(
                title=f"🎉 {section_name} is Ready!",
                description=description,
                color=discord.Color.blue(),
            )

            await chat_channel.send(embed=embed)

        except Exception as e:
            logger.warning(f"Could not send welcome message to chat channel: {e}")
