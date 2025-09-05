"""
Centralized logging configuration for the Discord Audio Router bot system.

This module provides consistent logging setup across all bot components
using YAML configuration for better maintainability.
"""

import logging
import logging.config
import os
import sys
from pathlib import Path
from typing import Optional


def setup_logging(
    component_name: str,
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    max_file_size: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
) -> logging.Logger:
    """
    Set up logging for a bot component using YAML configuration.

    Args:
        component_name: Name of the component (e.g., 'main_bot', 'speaker_bot')
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL). If None, reads from LOG_LEVEL env var
        log_file: Optional log file path (if None, uses YAML config)
        max_file_size: Maximum size of log file before rotation
        backup_count: Number of backup log files to keep

    Returns:
        logging.Logger: Configured logger instance
    """
    # Get log level from environment if not provided
    if log_level is None:
        log_level = os.getenv("LOG_LEVEL", "INFO")
    
    # Get verbose logging setting
    verbose_logging = os.getenv("VERBOSE_LOGGING", "false").lower() == "true"
    debug_mode = os.getenv("DEBUG", "false").lower() == "true"
    
    # Adjust log level based on debug/verbose settings
    if debug_mode:
        log_level = "DEBUG"
    elif verbose_logging and log_level == "INFO":
        log_level = "DEBUG"
    # Try to load YAML configuration first
    yaml_config_path = Path(__file__).parent.parent / "logging.yaml"
    if yaml_config_path.exists():
        try:
            import yaml

            with open(yaml_config_path, "r") as f:
                config = yaml.safe_load(f)

            # Ensure logs directory exists
            os.makedirs("logs", exist_ok=True)

            # Apply configuration
            logging.config.dictConfig(config)

            # Get the logger for this component
            logger = logging.getLogger(component_name)

            # Override log level if specified
            if log_level.upper() != "INFO":
                logger.setLevel(getattr(logging, log_level.upper()))

            return logger

        except ImportError:
            print(
                "Warning: PyYAML not available, falling back to basic logging"
            )
        except Exception as e:
            print(
                f"Warning: Failed to load YAML logging config: {e}, falling back to basic logging"
            )

    # Fallback to basic logging setup
    return _setup_basic_logging(
        component_name, log_level, log_file, max_file_size, backup_count
    )


def _setup_basic_logging(
    component_name: str,
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    max_file_size: int = 10 * 1024 * 1024,
    backup_count: int = 5,
) -> logging.Logger:
    """Fallback basic logging setup."""
    # Create logger
    logger = logging.getLogger(component_name)
    logger.setLevel(getattr(logging, log_level.upper()))

    # Clear any existing handlers
    logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        # Ensure log directory exists
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Suppress noisy third-party loggers
    _suppress_noisy_loggers()

    return logger


def _suppress_noisy_loggers():
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


class LoggingContext:
    """Context manager for temporary logging configuration."""

    def __init__(self, logger: logging.Logger, level: int):
        self.logger = logger
        self.original_level = logger.level
        self.new_level = level

    def __enter__(self):
        self.logger.setLevel(self.new_level)
        return self.logger

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger.setLevel(self.original_level)


def get_logger(component_name: str) -> logging.Logger:
    """
    Get a logger for a specific component.

    Args:
        component_name: Name of the component

    Returns:
        logging.Logger: Logger instance
    """
    return logging.getLogger(component_name)
