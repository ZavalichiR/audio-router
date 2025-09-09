"""
Simplified configuration management for the Discord Audio Router bot.

This module provides a clean, simple configuration system focused on
the core requirements without unnecessary complexity.
"""

import logging
import os
from dataclasses import dataclass
from typing import List

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


@dataclass
class SimpleConfig:
    """Simple configuration class for the audio router bot."""

    # Required configuration
    audio_broadcast_token: str
    audio_forwarder_token: str

    # Optional configuration with defaults
    command_prefix: str = "!"
    log_level: str = "INFO"

    # AudioReceiver bot tokens (for multiple bot instances)
    audio_receiver_tokens: List[str] = None

    # Access control configuration (simplified)
    speaker_role_name: str = "Speaker"
    listener_role_name: str = "Listener"
    broadcast_admin_role_name: str = "Broadcast Admin"
    auto_create_roles: bool = True

    def __post_init__(self):
        """Post-initialization processing."""
        if self.audio_receiver_tokens is None:
            self.audio_receiver_tokens = []


class SimpleConfigManager:
    """Simple configuration manager."""

    def __init__(self, env_file_path: str = ".env"):
        """
        Initialize configuration manager.

        Args:
            env_file_path: Path to environment file
        """
        self.env_file_path = env_file_path
        self._load_environment()

    def _load_environment(self):
        """Load environment variables from file."""
        if os.path.exists(self.env_file_path):
            load_dotenv(dotenv_path=self.env_file_path)
            logger.info(f"Loaded environment from {self.env_file_path}")
        else:
            logger.warning(f"Environment file {self.env_file_path} not found")

    def _get_required_env(self, key: str) -> str:
        """
        Get required environment variable.

        Args:
            key: Environment variable name

        Returns:
            str: Environment variable value

        Raises:
            ValueError: If environment variable is not set
        """
        value = os.getenv(key)
        if not value:
            raise ValueError(f"Required environment variable {key} is not set")
        return value

    def _get_optional_env(self, key: str, default: str = None) -> str:
        """
        Get optional environment variable.

        Args:
            key: Environment variable name
            default: Default value if not set

        Returns:
            Environment variable value or default
        """
        return os.getenv(key, default)

    def _get_audio_receiver_tokens(self) -> List[str]:
        """
        Get AudioReceiver bot tokens from environment variables.

        Always expects multi-line format:
        AUDIO_RECEIVER_TOKENS=[
            "token1",
            "token2",
            ...
        ]

        Returns:
            List of AudioReceiver bot tokens

        Raises:
            ValueError: If no AudioReceiver tokens are configured
        """
        tokens = self._parse_multiline_tokens_from_env_file()
        if not tokens:
            raise ValueError(
                "AUDIO_RECEIVER_TOKENS is required. Each AudioReceiver bot "
                "needs its own unique token. Create additional bots in "
                "Discord Developer Portal and add their tokens to "
                "AUDIO_RECEIVER_TOKENS."
            )
        logger.info(f"Loaded {len(tokens)} AudioReceiver bot tokens")
        return tokens

    def _parse_multiline_tokens_from_env_file(self) -> List[str]:
        """
        Parse multi-line AUDIO_RECEIVER_TOKENS directly from .env file.

        Assumes the format:
        AUDIO_RECEIVER_TOKENS=[
            "token1",
            "token2",
            ...
        ]

        Returns:
            List of parsed tokens
        """
        tokens = []
        try:
            # Look for .env file in current directory and parent directories
            env_file_path = None
            current_dir = os.getcwd()
            for _ in range(3):  # Check up to 3 levels up
                potential_path = os.path.join(current_dir, ".env")
                if os.path.exists(potential_path):
                    env_file_path = potential_path
                    break
                current_dir = os.path.dirname(current_dir)

            if not env_file_path:
                logger.warning("Could not find .env file to parse multi-line tokens")
                return tokens

            with open(env_file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            in_tokens_section = False
            for line in lines:
                stripped = line.strip()
                if not in_tokens_section:
                    if stripped.startswith("AUDIO_RECEIVER_TOKENS=["):
                        in_tokens_section = True
                        # Check if tokens are on the same line
                        after_bracket = stripped[len("AUDIO_RECEIVER_TOKENS=["):].strip()
                        if after_bracket and after_bracket != "]":
                            # Handle inline tokens, e.g. AUDIO_RECEIVER_TOKENS=["token1","token2"]
                            inline = after_bracket
                            if inline.endswith("]"):
                                inline = inline[:-1]
                                in_tokens_section = False
                            for token in inline.split(","):
                                token = token.strip().strip('"').strip("'")
                                if token:
                                    tokens.append(token)
                        continue
                else:
                    if stripped == "]":
                        break
                    if not stripped or stripped.startswith("#"):
                        continue
                    # Remove trailing comma and quotes
                    token = stripped.rstrip(",").strip().strip('"').strip("'")
                    if token:
                        tokens.append(token)
            # Remove duplicates while preserving order
            seen = set()
            unique_tokens = []
            for token in tokens:
                if token and token not in seen:
                    seen.add(token)
                    unique_tokens.append(token)
            return unique_tokens
        except Exception as e:
            logger.error(f"Error parsing multi-line tokens from .env file: {e}")
            return tokens

    def _get_speaker_role_name(self) -> str:
        """Get speaker role name from environment variables."""
        return self._get_optional_env("SPEAKER_ROLE_NAME", "Speaker")

    def _get_listener_role_name(self) -> str:
        """Get listener role name from environment variables."""
        return self._get_optional_env("LISTENER_ROLE_NAME", "Listener")

    def _get_broadcast_admin_role_name(self) -> str:
        """Get broadcast admin role name from environment variables."""
        return self._get_optional_env(
            "BROADCAST_ADMIN_ROLE_NAME", "Broadcast Admin"
        )

    def _get_auto_create_roles(self) -> bool:
        """Get auto-create roles setting from environment variables."""
        return (
            self._get_optional_env("AUTO_CREATE_ROLES", "true").lower()
            == "true"
        )

    def get_config(self) -> SimpleConfig:
        """
        Get the bot configuration.

        Returns:
            SimpleConfig: Bot configuration

        Raises:
            ValueError: If required configuration is missing
        """
        try:
            audio_broadcast_token = self._get_required_env(
                "AUDIO_BROADCAST_TOKEN"
            )
            audio_forwarder_token = self._get_required_env(
                "AUDIO_FORWARDER_TOKEN"
            )
            audio_receiver_tokens = self._get_audio_receiver_tokens()

            config = SimpleConfig(
                audio_broadcast_token=audio_broadcast_token,
                audio_forwarder_token=audio_forwarder_token,
                command_prefix=self._get_optional_env("BOT_PREFIX", "!"),
                log_level=self._get_optional_env("LOG_LEVEL", "INFO"),
                audio_receiver_tokens=audio_receiver_tokens,
                speaker_role_name=self._get_speaker_role_name(),
                listener_role_name=self._get_listener_role_name(),
                broadcast_admin_role_name=self._get_broadcast_admin_role_name(),
                auto_create_roles=self._get_auto_create_roles(),
            )

            logger.info("Configuration loaded successfully")
            return config

        except Exception as e:
            logger.error(f"Failed to load configuration: {e}", exc_info=True)
            raise


# Global configuration manager instance
config_manager = SimpleConfigManager()
