"""
Audio source implementations for the Discord Audio Router system.

This module provides various audio source implementations for different use cases,
including silence generation for keeping Discord voice connections alive.
"""

import logging

import discord

logger = logging.getLogger(__name__)


class SilentSource(discord.AudioSource):
    """
    Generates Opus silence frames to keep Discord voice connections alive.

    This source continuously provides silence frames to prevent Discord from
    disconnecting the bot due to inactivity.
    """

    def __init__(self):
        """Initialize the silent source."""
        self.frame_count = 0

    def is_opus(self) -> bool:
        """Return True to indicate we provide Opus-encoded audio."""
        return True

    def read(self) -> bytes:
        """
        Generate the next silence frame.

        Returns:
            bytes: Opus silence frame
        """
        self.frame_count += 1
        return b"\xf8\xff\xfe"  # Standard Opus silence frame
