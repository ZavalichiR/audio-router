"""Configuration utilities for the Audio Receiver Bot."""

import os

import discord


class BotConfig:
    """Configuration class for the Audio Receiver Bot."""

    def __init__(self):
        """Initialize bot configuration from environment variables."""
        self.bot_token = os.getenv("BOT_TOKEN")
        self.bot_id = os.getenv("BOT_ID", "audioreceiver_bot")
        self.bot_type = os.getenv("BOT_TYPE", "listener")
        self.channel_id = int(os.getenv("CHANNEL_ID", "0"))
        self.guild_id = int(os.getenv("GUILD_ID", "0"))
        self.speaker_channel_id = int(os.getenv("SPEAKER_CHANNEL_ID", "0"))
        self.centralized_server_url = os.getenv(
            "CENTRALIZED_WEBSOCKET_URL", "ws://localhost:8765"
        )

        self._validate_config()

    def _validate_config(self) -> None:
        """Validate required configuration values."""
        if not self.bot_token:
            raise ValueError("BOT_TOKEN environment variable is required")

        if not self.channel_id:
            raise ValueError("CHANNEL_ID environment variable is required")

        if not self.speaker_channel_id:
            raise ValueError("SPEAKER_CHANNEL_ID environment variable is required")

    def get_discord_intents(self):
        """Get Discord intents for the bot."""
        intents = discord.Intents.default()
        intents.voice_states = True
        intents.guilds = True
        return intents
