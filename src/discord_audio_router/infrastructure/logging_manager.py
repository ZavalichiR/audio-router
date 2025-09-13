"""
Production-ready logging management for the Discord Audio Router system.

This module provides centralized logging configuration with environment-based
log levels and YAML configuration support.

Environment Log Levels:
- Development: DEBUG and above
- Staging: INFO and above
- Production: WARNING and above
"""

import logging
import logging.config
import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any
from enum import Enum


class LogLevel(Enum):
    """Log level enumeration."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Environment(Enum):
    """Environment enumeration."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LoggingManager:
    """Centralized logging management with production controls."""

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize logging manager.

        Args:
            config_path: Path to YAML configuration file. If None, uses default location.
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent / "logging.yaml"

        self.config_path = config_path
        self._config_cache: Optional[Dict[str, Any]] = None
        self._environment = self._detect_environment()
        self._production_mode = self._environment == Environment.PRODUCTION

    def _detect_environment(self) -> Environment:
        """Detect current environment from environment variables."""
        env = os.getenv("ENVIRONMENT", "development").lower()

        if env in ["prod", "production"]:
            return Environment.PRODUCTION
        elif env in ["staging", "stage"]:
            return Environment.STAGING
        else:
            return Environment.DEVELOPMENT

    def _load_yaml_config(self) -> Optional[Dict[str, Any]]:
        """Load YAML logging configuration."""
        if self._config_cache is not None:
            return self._config_cache

        if not self.config_path.exists():
            return None

        try:
            with open(self.config_path, "r") as f:
                config = yaml.safe_load(f)
            self._config_cache = config
            return config
        except (yaml.YAMLError, IOError) as e:
            print(f"Warning: Failed to load YAML logging config: {e}")
            return None

    def _get_environment_log_level(self) -> str:
        """Get appropriate log level for current environment."""
        if self._production_mode:
            return "WARNING"  # Production: WARNING and above
        elif self._environment == Environment.STAGING:
            return "INFO"  # Staging: INFO and above
        else:
            return "DEBUG"  # Development: DEBUG and above

    def _apply_production_overrides(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply production-specific overrides to configuration."""
        if not self._production_mode:
            return config

        # Override log levels for production
        env_log_level = self._get_environment_log_level()

        # Update root logger level
        if "root" in config:
            config["root"]["level"] = env_log_level

        # Update all loggers to production-appropriate levels
        if "loggers" in config:
            for logger_name, logger_config in config["loggers"].items():
                # Skip third-party noisy loggers - they should stay at WARNING
                if logger_name in [
                    "discord.voice_state",
                    "discord.gateway",
                    "discord.client",
                    "websockets",
                    "aiohttp.access",
                    "aiohttp.client",
                ]:
                    continue

                # Set application loggers to production level
                logger_config["level"] = env_log_level

        # Disable debug handlers in production
        if "handlers" in config:
            for handler_name, handler_config in config["handlers"].items():
                if "file_" in handler_name and handler_config.get("level") == "DEBUG":
                    # Keep file handlers but set to production level
                    handler_config["level"] = env_log_level

        return config

    def setup_logging(
        self,
        component_name: str,
        log_level: Optional[str] = None,
        log_file: Optional[str] = None,
        force_development: bool = False,
    ) -> logging.Logger:
        """
        Set up logging for a component with environment-aware configuration.

        Args:
            component_name: Name of the component
            log_level: Override log level (if None, uses environment-appropriate level:
                      Development=DEBUG, Staging=INFO, Production=WARNING)
            log_file: Override log file path
            force_development: Force development mode regardless of environment

        Returns:
            Configured logger instance
        """
        # Determine effective environment
        effective_production = self._production_mode and not force_development

        # Get appropriate log level
        if log_level is None:
            log_level = self._get_environment_log_level()

        # Load YAML configuration
        config = self._load_yaml_config()

        if config and not force_development:
            # Apply production overrides if needed
            config = self._apply_production_overrides(config)

            # Ensure logs directory exists
            os.makedirs("logs", exist_ok=True)

            # Apply YAML configuration
            logging.config.dictConfig(config)

            # Get component logger
            logger = logging.getLogger(component_name)

            # Override log level if specified
            if log_level:
                logger.setLevel(getattr(logging, log_level.upper()))

            # Suppress noisy third-party loggers
            self._suppress_noisy_loggers()

            return logger
        else:
            # Fallback to basic logging
            return self._setup_basic_logging(
                component_name, log_level, log_file, effective_production
            )

    def _setup_basic_logging(
        self,
        component_name: str,
        log_level: str,
        log_file: Optional[str],
        production_mode: bool,
    ) -> logging.Logger:
        """Set up basic logging when YAML config is not available."""
        logger = logging.getLogger(component_name)

        # Set log level
        logger.setLevel(getattr(logging, log_level.upper()))

        # Clear existing handlers
        logger.handlers.clear()

        # Create formatter
        if production_mode:
            # Simpler format for production
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        else:
            # More detailed format for development
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logger.level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # File handler if specified
        if log_file:
            os.makedirs("logs", exist_ok=True)
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(
                logging.DEBUG if not production_mode else logging.WARNING
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        # Suppress noisy loggers
        self._suppress_noisy_loggers()

        return logger

    def _suppress_noisy_loggers(self):
        """Suppress noisy third-party library loggers."""
        noisy_loggers = [
            "discord.voice_state",
            "discord.gateway",
            "discord.client",
            "websockets",
            "aiohttp.access",
            "aiohttp.client",
        ]

        for logger_name in noisy_loggers:
            logging.getLogger(logger_name).setLevel(logging.WARNING)

    def get_environment(self) -> Environment:
        """Get current environment."""
        return self._environment

    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self._production_mode

    def get_effective_log_level(self, component_name: str) -> str:
        """Get effective log level for a component."""
        logger = logging.getLogger(component_name)
        return logging.getLevelName(logger.level)

    def set_production_mode(self, enabled: bool):
        """Manually set production mode."""
        self._production_mode = enabled
        self._environment = (
            Environment.PRODUCTION if enabled else Environment.DEVELOPMENT
        )

    def reload_config(self):
        """Reload YAML configuration."""
        self._config_cache = None
        self._load_yaml_config()


# Global logging manager instance
_logging_manager = LoggingManager()


def setup_logging(
    component_name: str,
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    force_development: bool = False,
) -> logging.Logger:
    """
    Set up logging for a component (convenience function).

    Args:
        component_name: Name of the component
        log_level: Override log level
        log_file: Override log file path
        force_development: Force development mode

    Returns:
        Configured logger instance
    """
    return _logging_manager.setup_logging(
        component_name, log_level, log_file, force_development
    )


def get_logger(component_name: str) -> logging.Logger:
    """
    Get a logger for a component.

    Args:
        component_name: Name of the component

    Returns:
        Logger instance
    """
    return logging.getLogger(component_name)


def is_production() -> bool:
    """Check if running in production mode."""
    return _logging_manager.is_production()


def get_environment() -> Environment:
    """Get current environment."""
    return _logging_manager.get_environment()
