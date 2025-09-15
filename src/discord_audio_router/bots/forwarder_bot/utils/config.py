"""Configuration utilities for the Audio Forwarder Bot."""

import os

import discord

from discord_audio_router.core.types import (
    BOT_TYPE_FWD,
    ENV_BOT_TOKEN,
    ENV_BOT_ID,
    ENV_BOT_TYPE,
    ENV_CHANNEL_ID,
    ENV_GUILD_ID,
    ENV_CENTRALIZED_WEBSOCKET_URL,
    DEFAULT_WEBSOCKET_URL,
)


class BotConfig:
    """Configuration class for the Audio Forwarder Bot."""

    def __init__(self):
        """Initialize bot configuration from environment variables."""
        self.bot_token = os.getenv(ENV_BOT_TOKEN)
        self.bot_id = os.getenv(ENV_BOT_ID)
        self.bot_type = os.getenv(ENV_BOT_TYPE, BOT_TYPE_FWD)
        self.channel_id = int(os.getenv(ENV_CHANNEL_ID, "0"))
        self.guild_id = int(os.getenv(ENV_GUILD_ID, "0"))
        self.centralized_server_url = os.getenv(
            ENV_CENTRALIZED_WEBSOCKET_URL, DEFAULT_WEBSOCKET_URL
        )

        self._validate_config()

    def _validate_config(self) -> None:
        """Validate required configuration values."""
        if not self.bot_token:
            raise ValueError(f"{ENV_BOT_TOKEN} environment variable is required")

        if not self.channel_id:
            raise ValueError(f"{ENV_CHANNEL_ID} environment variable is required")

    def get_discord_intents(self):
        """Get Discord intents for the bot."""
        intents = discord.Intents.default()
        intents.voice_states = True
        intents.guilds = True
        return intents
