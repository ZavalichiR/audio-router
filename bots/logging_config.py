"""
Centralized logging configuration for the Discord Audio Router bot system.

This module provides consistent logging setup across all bot components
with proper formatting, levels, and handlers.
"""

import logging
import logging.handlers
import os
import sys
from typing import Optional


def setup_logging(
    component_name: str,
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    max_file_size: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> logging.Logger:
    """
    Set up logging for a bot component.
    
    Args:
        component_name: Name of the component (e.g., 'main_bot', 'receiver_bot')
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path (if None, logs only to console)
        max_file_size: Maximum size of log file before rotation
        backup_count: Number of backup log files to keep
        
    Returns:
        logging.Logger: Configured logger instance
    """
    # Create logger
    logger = logging.getLogger(component_name)
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
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
            encoding='utf-8'
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
        'discord.voice_state',
        'discord.gateway', 
        'discord.client',
        'websockets',
        'aiohttp.access',
        'aiohttp.client'
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
