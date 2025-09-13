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

        # Auto-cleanup configuration
        self.auto_cleanup_timeout = auto_cleanup_timeout * 60  # seconds
        self._last_activity: Dict[int, float] = {}
        self._cleanup_task: Optional[asyncio.Task] = None

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
                if now - last > self.auto_cleanup_timeout:
                    to_cleanup.append(guild_id)
                else:
                    self._last_activity.setdefault(guild_id, now)
            else:
                self._last_activity[guild_id] = now

        for guild_id in to_cleanup:
            logger.info(f"Cleaning up inactive section for guild {guild_id}")
            guild = main_bot.get_guild(guild_id)
            if guild:
                await self.stop_broadcast(guild)
            else:
                logger.warning(f"Guild {guild_id} not in cache")

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
        for category in guild.categories:
            if category.name == category_name:
                for channel in category.channels:
                    try:
                        await channel.delete(reason="Cleaning up broadcast section")
                    except discord.Forbidden:
                        logger.warning(
                            f"Cannot delete channel {channel.name}: Insufficient permissions"
                        )
                try:
                    await category.delete(reason="Cleaning up broadcast section")
                except discord.Forbidden:
                    logger.warning(
                        f"Cannot delete category {category.name}: Insufficient permissions"
                    )
                break

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

        # 2. Create control channel (text)
        control = await category.create_text_channel(
            name="broadcast-control",
            topic=f"Control channel for {category_name}",
            overwrites=cat_overwrites,
            reason="Control channel",
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
        logger.info(f"Created broadcast section '{section_name}' (Guild {guild.id})")

        return {
            "success": True,
            "section": section,
            "message": f"Broadcast section '{section_name}' created",
        }

    async def start_broadcast(self, guild: discord.Guild) -> Dict[str, Any]:
        section = self.active_sections.get(guild.id)
        if not section:
            return {"success": False, "message": "No section found"}
        if section.is_active:
            return {"success": False, "message": "Broadcast already active"}

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

        del self.active_sections[guild.id]
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
