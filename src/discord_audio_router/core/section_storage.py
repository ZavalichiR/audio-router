"""
Broadcast Section Storage Manager

This module handles persistent storage for broadcast section data across bot restarts.
Uses JSON files with file locking to handle concurrent writes safely.
"""

import json
import threading
import time
from pathlib import Path
from typing import Dict, Optional, Any, List
import fcntl

from discord_audio_router.infrastructure.logging import setup_logging

logger = setup_logging(
    component_name="section_storage",
    log_file="logs/section_manager.log",
)


class BroadcastSectionData:
    """Data class for broadcast section storage."""

    def __init__(
        self,
        guild_id: int,
        section_name: str,
        category_id: int,
        control_channel_id: int,
        speaker_channel_id: int,
        listener_channel_ids: List[int],
        is_active: bool = False,
        speaker_bot_id: Optional[str] = None,
        listener_bot_ids: Optional[List[str]] = None,
    ):
        self.guild_id = guild_id
        self.section_name = section_name
        self.category_id = category_id
        self.control_channel_id = control_channel_id
        self.speaker_channel_id = speaker_channel_id
        self.listener_channel_ids = listener_channel_ids or []
        self.is_active = is_active
        self.speaker_bot_id = speaker_bot_id
        self.listener_bot_ids = listener_bot_ids or []
        self.last_updated = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "guild_id": self.guild_id,
            "section_name": self.section_name,
            "category_id": self.category_id,
            "control_channel_id": self.control_channel_id,
            "speaker_channel_id": self.speaker_channel_id,
            "listener_channel_ids": self.listener_channel_ids,
            "is_active": self.is_active,
            "speaker_bot_id": self.speaker_bot_id,
            "listener_bot_ids": self.listener_bot_ids,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BroadcastSectionData":
        """Create from dictionary."""
        return cls(
            guild_id=data.get("guild_id"),
            section_name=data.get("section_name", ""),
            category_id=data.get("category_id"),
            control_channel_id=data.get("control_channel_id"),
            speaker_channel_id=data.get("speaker_channel_id"),
            listener_channel_ids=data.get("listener_channel_ids", []),
            is_active=data.get("is_active", False),
            speaker_bot_id=data.get("speaker_bot_id"),
            listener_bot_ids=data.get("listener_bot_ids", []),
        )


class SectionStorage:
    """Manages persistent storage for broadcast section data."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.sections_file = self.data_dir / "broadcast_sections.json"
        self._lock = threading.RLock()
        self._sections_cache: Dict[int, BroadcastSectionData] = {}
        self._load_sections()

    def _load_sections(self) -> None:
        """Load sections from file."""
        if not self.sections_file.exists():
            logger.info("Broadcast sections file not found, using defaults")
            return

        try:
            with open(self.sections_file, "r", encoding="utf-8") as f:
                with self._lock:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)  # Shared lock for reading
                    data = json.load(f)
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # Release lock

            for guild_id_str, section_data in data.items():
                guild_id = int(guild_id_str)
                section = BroadcastSectionData.from_dict(section_data)
                self._sections_cache[guild_id] = section

            logger.info(
                f"Loaded broadcast section data for {len(self._sections_cache)} guilds"
            )
        except Exception as e:
            logger.error(f"Failed to load broadcast sections: {e}", exc_info=True)

    def _save_sections(self) -> None:
        """Save sections to file with proper locking."""
        try:
            with open(self.sections_file, "w", encoding="utf-8") as f:
                with self._lock:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # Exclusive lock for writing
                    json.dump(
                        {
                            str(guild_id): section.to_dict()
                            for guild_id, section in self._sections_cache.items()
                        },
                        f,
                        indent=2,
                        ensure_ascii=False,
                    )
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # Release lock
        except Exception as e:
            logger.error(f"Failed to save broadcast sections: {e}", exc_info=True)

    def get_section(self, guild_id: int) -> Optional[BroadcastSectionData]:
        """Get section data for a guild."""
        with self._lock:
            return self._sections_cache.get(guild_id)

    def save_section(
        self,
        guild_id: int,
        section_name: str,
        category_id: int,
        control_channel_id: int,
        speaker_channel_id: int,
        listener_channel_ids: List[int],
        is_active: bool = False,
        speaker_bot_id: Optional[str] = None,
        listener_bot_ids: Optional[List[str]] = None,
    ) -> BroadcastSectionData:
        """Save section data for a guild."""
        with self._lock:
            section = BroadcastSectionData(
                guild_id=guild_id,
                section_name=section_name,
                category_id=category_id,
                control_channel_id=control_channel_id,
                speaker_channel_id=speaker_channel_id,
                listener_channel_ids=listener_channel_ids,
                is_active=is_active,
                speaker_bot_id=speaker_bot_id,
                listener_bot_ids=listener_bot_ids or [],
            )
            self._sections_cache[guild_id] = section
            self._save_sections()
            logger.info(f"Saved broadcast section data for guild {guild_id}")
            return section

    def update_section(
        self,
        guild_id: int,
        is_active: Optional[bool] = None,
        speaker_bot_id: Optional[str] = None,
        listener_bot_ids: Optional[List[str]] = None,
    ) -> Optional[BroadcastSectionData]:
        """Update section data for a guild."""
        with self._lock:
            section = self._sections_cache.get(guild_id)
            if not section:
                return None

            if is_active is not None:
                section.is_active = is_active
            if speaker_bot_id is not None:
                section.speaker_bot_id = speaker_bot_id
            if listener_bot_ids is not None:
                section.listener_bot_ids = listener_bot_ids

            section.last_updated = time.time()
            self._save_sections()
            logger.info(f"Updated broadcast section data for guild {guild_id}")
            return section

    def remove_section(self, guild_id: int) -> bool:
        """Remove section data for a guild."""
        with self._lock:
            if guild_id in self._sections_cache:
                del self._sections_cache[guild_id]
                self._save_sections()
                logger.info(f"Removed broadcast section data for guild {guild_id}")
                return True
            return False

    def get_all_sections(self) -> Dict[int, BroadcastSectionData]:
        """Get all section data."""
        with self._lock:
            return self._sections_cache.copy()
