"""
Centralized logging configuration for the Discord Audio Router bot system.

This module provides consistent logging setup across all bot components
using YAML configuration for better maintainability with production controls.
"""

import logging
from typing import Optional

from .logging_manager import setup_logging as _setup_logging, get_logger as _get_logger


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
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL). If None, uses environment-appropriate level:
                  Development=DEBUG, Staging=INFO, Production=WARNING
        log_file: Optional log file path (if None, uses YAML config)
        max_file_size: Maximum size of log file before rotation (unused in YAML mode)
        backup_count: Number of backup log files to keep (unused in YAML mode)

    Returns:
        logging.Logger: Configured logger instance
    """
    return _setup_logging(component_name, log_level, log_file)


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
    return _get_logger(component_name)
