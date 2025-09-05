#!/usr/bin/env python3
"""
Startup script for the Discord Audio Router Bot.

This script starts the main bot with the new multi-bot architecture.
"""

import asyncio
import sys
import os
import logging
from pathlib import Path

# Add the bots directory to the Python path
bots_dir = Path(__file__).parent / "bots"
sys.path.insert(0, str(bots_dir))

# Import the AudioBroadcast bot
from bots.audiobroadcast_bot import main

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/bot_startup.log")
    ]
)

logger = logging.getLogger(__name__)


async def startup():
    """Startup function with error handling."""
    try:
        logger.info("Starting AudioBroadcast Bot...")
        
        # Check if .env file exists
        env_file = Path(".env")
        if not env_file.exists():
            logger.warning("No .env file found!")
        
        # Start the bot
        await main()
        
    except KeyboardInterrupt:
        logger.info("Bot shutdown requested by user")
    except Exception as e:
        logger.critical(f"Fatal error during startup: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    # Ensure logs directory exists
    os.makedirs("logs", exist_ok=True)
    
    # Run the bot
    try:
        asyncio.run(startup())
    except KeyboardInterrupt:
        print("\nBot shutdown requested")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)
