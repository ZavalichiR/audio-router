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
    main_bot_token: str

    # Optional configuration with defaults
    command_prefix: str = "!"
    log_level: str = "INFO"

    # Listener bot tokens (for multiple bot instances)
    listener_bot_tokens: List[str] = None

    # Access control configuration
    authorized_roles: List[str] = None
    authorized_users: List[int] = None
    create_authorized_role: bool = True
    authorized_role_name: str = "Broadcast Controller"

    def __post_init__(self):
        """Post-initialization processing."""
        if self.listener_bot_tokens is None:
            self.listener_bot_tokens = []
        if self.authorized_roles is None:
            self.authorized_roles = []
        if self.authorized_users is None:
            self.authorized_users = []


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

    def _get_listener_tokens(self) -> List[str]:
        """
        Get listener bot tokens from environment variables.

        Supports multiple formats:
        - LISTENER_BOT_TOKEN: Single token
        - LISTENER_BOT_TOKENS: Comma-separated tokens
        - LISTENER_BOT_TOKEN_1, LISTENER_BOT_TOKEN_2, etc.: Numbered tokens

        Returns:
            List of listener bot tokens
        """
        tokens = []

        # Try single token first
        single_token = self._get_optional_env("LISTENER_BOT_TOKEN")
        if single_token:
            tokens.append(single_token)

        # Try comma-separated tokens
        multiple_tokens = self._get_optional_env("LISTENER_BOT_TOKENS")
        if multiple_tokens:
            for token in multiple_tokens.split(","):
                token = token.strip()
                if token and token not in tokens:
                    tokens.append(token)

        # Try numbered tokens
        token_index = 1
        while True:
            numbered_token = self._get_optional_env(f"LISTENER_BOT_TOKEN_{token_index}")
            if not numbered_token:
                break
            if numbered_token not in tokens:
                tokens.append(numbered_token)
            token_index += 1

        # If no listener tokens found, use main token for all bots
        if not tokens:
            logger.warning(
                "No listener bot tokens found, will use main token for all bots"
            )
            main_token = self._get_required_env("MAIN_BOT_TOKEN")
            tokens = [main_token] * 10  # Support up to 10 listener bots

        logger.info(f"Loaded {len(tokens)} listener bot tokens")
        return tokens

    def _get_authorized_roles(self) -> List[str]:
        """Get authorized roles from environment variables."""
        roles_env = self._get_optional_env("AUTHORIZED_ROLES", "")
        if roles_env:
            return [role.strip() for role in roles_env.split(",") if role.strip()]
        return []

    def _get_authorized_users(self) -> List[int]:
        """Get authorized user IDs from environment variables."""
        users_env = self._get_optional_env("AUTHORIZED_USERS", "")
        if users_env:
            try:
                return [
                    int(user_id.strip())
                    for user_id in users_env.split(",")
                    if user_id.strip()
                ]
            except ValueError:
                logger.warning("Invalid user IDs in AUTHORIZED_USERS, ignoring")
        return []

    def get_config(self) -> SimpleConfig:
        """
        Get the bot configuration.

        Returns:
            SimpleConfig: Bot configuration

        Raises:
            ValueError: If required configuration is missing
        """
        try:
            main_bot_token = self._get_required_env("MAIN_BOT_TOKEN")
            listener_tokens = self._get_listener_tokens()
            authorized_roles = self._get_authorized_roles()
            authorized_users = self._get_authorized_users()

            config = SimpleConfig(
                main_bot_token=main_bot_token,
                command_prefix=self._get_optional_env("BOT_PREFIX", "!"),
                log_level=self._get_optional_env("LOG_LEVEL", "INFO"),
                listener_bot_tokens=listener_tokens,
                authorized_roles=authorized_roles,
                authorized_users=authorized_users,
                create_authorized_role=self._get_optional_env(
                    "CREATE_AUTHORIZED_ROLE", "true"
                ).lower()
                == "true",
                authorized_role_name=self._get_optional_env(
                    "AUTHORIZED_ROLE_NAME", "Broadcast Controller"
                ),
            )

            logger.info("Configuration loaded successfully")
            return config

        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise


# Global configuration manager instance
config_manager = SimpleConfigManager()
