"""
Utility functions for connection management.

This module provides utility functions for the simplified WebSocket relay server.
"""

import asyncio
import logging

from websockets.asyncio.server import ServerConnection

from ...core import ConnectionManager


class ConnectionUtils:
    """Utility functions for connection management."""

    @staticmethod
    async def cleanup_connection(
        connections: ConnectionManager,
        websocket: ServerConnection,
        logger: logging.Logger,
    ) -> None:
        """Clean up when connection is closed."""
        # Find and unregister the client
        for client_id, ws in list(connections.clients.items()):
            if ws == websocket:
                connections.unregister(client_id)
                logger.info(f"Client disconnected: {client_id}")
                break

    @staticmethod
    async def health_monitor(
        connections: ConnectionManager,
        ping_interval: int,
        logger: logging.Logger,
    ) -> None:
        """Monitor connection health and send pings."""
        while True:
            await asyncio.sleep(ping_interval)

            # Send pings to keep connections alive
            for websocket in list(connections.clients.values()):
                try:
                    await websocket.ping()
                except Exception:
                    pass
