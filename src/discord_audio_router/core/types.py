"""
Common types and constants for the Discord Audio Router system.

This module centralizes all bot types and constants to avoid hardcoding
throughout the codebase.
"""

from typing import Final

# Bot Types
BOT_TYPE_FWD: Final[str] = "fwd"
BOT_TYPE_RCV: Final[str] = "rcv"

# Bot Script Paths
BOT_SCRIPT_PATHS = {
    BOT_TYPE_FWD: "forwarder_bot.py",
    BOT_TYPE_RCV: "receiver_bot.py",
}

# Environment Variable Names (from .env file)
ENV_BOT_TOKEN: Final[str] = "BOT_TOKEN"
ENV_BOT_ID: Final[str] = "BOT_ID"
ENV_BOT_TYPE: Final[str] = "BOT_TYPE"
ENV_CHANNEL_ID: Final[str] = "CHANNEL_ID"
ENV_GUILD_ID: Final[str] = "GUILD_ID"
ENV_SPEAKER_CHANNEL_ID: Final[str] = "SPEAKER_CHANNEL_ID"
ENV_CENTRALIZED_WEBSOCKET_URL: Final[str] = "CENTRALIZED_SERVER_URL"

# Role Names (from .env file)
ENV_SPEAKER_ROLE_NAME: Final[str] = "SPEAKER_ROLE_NAME"
ENV_LISTENER_ROLE_NAME: Final[str] = "LISTENER_ROLE_NAME"
ENV_BROADCAST_ADMIN_ROLE_NAME: Final[str] = "BROADCAST_ADMIN_ROLE_NAME"

# WebSocket Message Types
WS_MSG_REGISTER: Final[str] = "register"
WS_MSG_REGISTERED: Final[str] = "registered"
WS_MSG_PING: Final[str] = "ping"
WS_MSG_PONG: Final[str] = "pong"
WS_MSG_ERROR: Final[str] = "error"

# WebSocket Client Types
WS_CLIENT_TYPE_FWD: Final[str] = "fwd"
WS_CLIENT_TYPE_RCV: Final[str] = "rcv"

# Default Values
DEFAULT_WEBSOCKET_URL: Final[str] = "ws://localhost:8765"
