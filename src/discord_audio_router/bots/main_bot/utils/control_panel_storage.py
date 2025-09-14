"""
Control Panel Storage Manager

This module handles persistent storage for control panel settings across bot restarts.
Uses JSON files with file locking to handle concurrent writes safely.
"""

import json
import threading
import time
from pathlib import Path
from typing import Dict, Optional, Any
import fcntl

from discord_audio_router.infrastructure.logging import setup_logging

logger = setup_logging(
    component_name="control_panel_storage",
    log_file="logs/control_panel.log",
)


class ControlPanelSettings:
    """Data class for control panel settings."""

    def __init__(
        self,
        section_name: str = "LIVE",
        listener_channels: int = 1,  # Will be overridden by max_listeners in get_settings
        permission_role: Optional[str] = None,
        guild_id: Optional[int] = None,
    ):
        self.section_name = section_name
        self.listener_channels = listener_channels
        self.permission_role = permission_role
        self.guild_id = guild_id
        self.last_updated = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "section_name": self.section_name,
            "listener_channels": self.listener_channels,
            "permission_role": self.permission_role,
            "guild_id": self.guild_id,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ControlPanelSettings":
        """Create from dictionary."""
        settings = cls()
        settings.section_name = data.get("section_name", "LIVE")
        settings.listener_channels = data.get(
            "listener_channels", 1
        )  # Will be updated by max_listeners if needed
        settings.permission_role = data.get("permission_role")
        settings.guild_id = data.get("guild_id")
        settings.last_updated = data.get("last_updated", time.time())
        return settings


class ControlPanelInfo:
    """Data class for control panel message information."""

    def __init__(
        self,
        guild_id: int,
        channel_id: int,
        message_id: int,
        created_at: float = None,
    ):
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.message_id = message_id
        self.created_at = created_at or time.time()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "guild_id": self.guild_id,
            "channel_id": self.channel_id,
            "message_id": self.message_id,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ControlPanelInfo":
        """Create from dictionary."""
        return ControlPanelInfo(
            guild_id=data["guild_id"],
            channel_id=data["channel_id"],
            message_id=data["message_id"],
            created_at=data.get("created_at", time.time()),
        )


class ControlPanelStorage:
    """Manages persistent storage for control panel settings."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.settings_file = self.data_dir / "control_panel_settings.json"
        self.panels_file = self.data_dir / "control_panel_panels.json"
        self._lock = threading.RLock()
        self._settings_cache: Dict[int, ControlPanelSettings] = {}
        self._panels_cache: Dict[int, ControlPanelInfo] = {}
        self._load_settings()
        self._load_panels()

    def _load_settings(self) -> None:
        """Load settings from file."""
        if not self.settings_file.exists():
            logger.info("Control panel settings file not found, using defaults")
            return

        try:
            with open(self.settings_file, "r", encoding="utf-8") as f:
                with self._lock:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)  # Shared lock for reading
                    data = json.load(f)
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # Release lock

            for guild_id_str, settings_data in data.items():
                guild_id = int(guild_id_str)
                settings = ControlPanelSettings.from_dict(settings_data)
                settings.guild_id = guild_id
                self._settings_cache[guild_id] = settings

            logger.info(
                f"Loaded control panel settings for {len(self._settings_cache)} guilds"
            )
        except Exception as e:
            logger.error(f"Failed to load control panel settings: {e}", exc_info=True)

    def _save_settings(self) -> None:
        """Save settings to file with proper locking."""
        try:
            # Create temporary file first
            temp_file = self.settings_file.with_suffix(".tmp")

            with open(temp_file, "w", encoding="utf-8") as f:
                with self._lock:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # Exclusive lock for writing
                    data = {
                        str(guild_id): settings.to_dict()
                        for guild_id, settings in self._settings_cache.items()
                    }
                    json.dump(data, f, indent=2, ensure_ascii=False)
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # Release lock

            # Atomic move
            temp_file.replace(self.settings_file)
            logger.debug("Control panel settings saved successfully")
        except Exception as e:
            logger.error(f"Failed to save control panel settings: {e}", exc_info=True)
            # Clean up temp file if it exists
            if temp_file.exists():
                temp_file.unlink()

    def get_settings(
        self, guild_id: int, max_listeners: int = 1
    ) -> ControlPanelSettings:
        """Get settings for a guild, creating default if not exists."""
        with self._lock:
            if guild_id not in self._settings_cache:
                self._settings_cache[guild_id] = ControlPanelSettings(
                    section_name="LIVE",
                    listener_channels=max_listeners,
                    permission_role=None,
                    guild_id=guild_id,
                )
            return self._settings_cache[guild_id]

    def update_settings(
        self,
        guild_id: int,
        section_name: Optional[str] = None,
        listener_channels: Optional[int] = None,
        permission_role: Optional[str] = None,
    ) -> ControlPanelSettings:
        """Update settings for a guild."""
        with self._lock:
            settings = self.get_settings(guild_id)

            if section_name is not None:
                settings.section_name = section_name
            if listener_channels is not None:
                settings.listener_channels = listener_channels
            if permission_role is not None:
                settings.permission_role = permission_role

            settings.last_updated = time.time()
            self._save_settings()

            logger.info(f"Updated control panel settings for guild {guild_id}")
            return settings

    def _load_panels(self) -> None:
        """Load panel information from file."""
        if not self.panels_file.exists():
            logger.info("Control panel panels file not found, using defaults")
            return

        try:
            with open(self.panels_file, "r", encoding="utf-8") as f:
                with self._lock:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)  # Shared lock for reading
                    data = json.load(f)
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # Release lock

            for guild_id_str, panel_data in data.items():
                guild_id = int(guild_id_str)
                self._panels_cache[guild_id] = ControlPanelInfo.from_dict(panel_data)

            logger.info(f"Loaded {len(self._panels_cache)} control panel records")
        except Exception as e:
            logger.error(f"Failed to load control panel panels: {e}", exc_info=True)

    def _save_panels(self) -> None:
        """Save panel information to file."""
        try:
            with open(self.panels_file, "w", encoding="utf-8") as f:
                with self._lock:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # Exclusive lock for writing
                    data = {
                        str(guild_id): panel_info.to_dict()
                        for guild_id, panel_info in self._panels_cache.items()
                    }
                    json.dump(data, f, indent=2, ensure_ascii=False)
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # Release lock

            logger.debug("Control panel panels saved successfully")
        except Exception as e:
            logger.error(f"Failed to save control panel panels: {e}", exc_info=True)

    def save_panel_info(self, guild_id: int, channel_id: int, message_id: int) -> None:
        """Save panel information for a guild."""
        with self._lock:
            panel_info = ControlPanelInfo(
                guild_id=guild_id,
                channel_id=channel_id,
                message_id=message_id,
            )
            self._panels_cache[guild_id] = panel_info
            self._save_panels()
            logger.info(f"Saved control panel info for guild {guild_id}")

    def get_panel_info(self, guild_id: int) -> Optional[ControlPanelInfo]:
        """Get panel information for a guild."""
        with self._lock:
            return self._panels_cache.get(guild_id)

    def remove_panel_info(self, guild_id: int) -> None:
        """Remove panel information for a guild."""
        with self._lock:
            if guild_id in self._panels_cache:
                del self._panels_cache[guild_id]
                self._save_panels()
                logger.info(f"Removed control panel info for guild {guild_id}")

    def get_all_panels(self) -> Dict[int, ControlPanelInfo]:
        """Get all panel information."""
        with self._lock:
            return self._panels_cache.copy()


# Global storage instance
_storage_instance: Optional[ControlPanelStorage] = None


def get_storage() -> ControlPanelStorage:
    """Get the global storage instance."""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = ControlPanelStorage()
    return _storage_instance
