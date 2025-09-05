#!/usr/bin/env python3
"""
WebSocket Relay Server for Discord Audio Router.

This script starts the centralized WebSocket relay server that handles
audio routing between speaker and listener bots.
"""

import asyncio
import sys
import os
import logging
from pathlib import Path

# Add the bots directory to the Python path
bots_dir = Path(__file__).parent / "bots"
sys.path.insert(0, str(bots_dir))

from bots.core.audio_relay_server import AudioRelayServer
from bots.logging_config import setup_logging

# Configure logging
logger = setup_logging(
    component_name="websocket_relay",
    log_level="INFO",
    log_file="logs/websocket_relay.log"
)


async def main():
    """Main function to start the WebSocket relay server."""
    try:
        logger.info("Starting WebSocket Relay Server...")
        
        # Create and start the relay server
        relay_server = AudioRelayServer(host="localhost", port=8765)
        await relay_server.start()
        
        logger.info("WebSocket Relay Server started on localhost:8765")
        logger.info("Press Ctrl+C to stop the server")
        
        # Keep the server running
        try:
            await asyncio.Future()  # Run forever
        except KeyboardInterrupt:
            logger.info("Shutdown requested by user")
        finally:
            await relay_server.stop()
            logger.info("WebSocket Relay Server stopped")
        
    except Exception as e:
        logger.critical(f"Failed to start WebSocket Relay Server: {e}")
        raise


if __name__ == "__main__":
    # Ensure logs directory exists
    os.makedirs("logs", exist_ok=True)
    
    # Run the relay server
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nWebSocket Relay Server shutdown requested")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)
