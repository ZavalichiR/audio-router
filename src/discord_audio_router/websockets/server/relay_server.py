"""
Simplified WebSocket relay server for audio routing.

This server uses a much simpler architecture with ConnectionManager
for efficient speaker-listener management.
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional

if __name__ == "__main__":
    src_path = Path(__file__).parent.parent.parent.parent / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from discord_audio_router.infrastructure import setup_logging
from ..core import ConnectionManager
from .process_messages import (
    ControlMessageHandler,
    AudioMessageHandler,
    ConnectionUtils,
)

logger = setup_logging(
    component_name="websocket_relay",
    log_file="logs/websocket_relay.log",
)


class AudioRelayServer:
    """Simplified high-performance WebSocket server for audio routing."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8765,
        ping_interval: int = 30,
        max_connections: int = 100,
    ) -> None:
        """Initialize the audio relay server."""
        self.host = host
        self.port = port
        self.server: Optional[Server] = None
        self.ping_interval = ping_interval

        self.connections = ConnectionManager()
        self._connection_semaphore = asyncio.Semaphore(max_connections)
        self._health_task: Optional[asyncio.Task] = None

        # Initialize message handlers
        self.control_handler = ControlMessageHandler(self.connections, logger)
        self.audio_handler = AudioMessageHandler(self.connections, logger)

    async def start(self) -> bool:
        """Start the audio relay server."""
        try:
            self.server = await serve(
                self._handle_connection,
                self.host,
                self.port,
                ping_interval=None,  # Manual ping handling
                max_size=2**20,  # 1MB max message size
                compression=None,  # No compression for low latency
            )
            logger.info(f"Audio relay server started on {self.host}:{self.port}")
            self._health_task = asyncio.create_task(
                ConnectionUtils.health_monitor(
                    self.connections, self.ping_interval, logger
                )
            )
            return True
        except Exception as e:
            logger.error(f"Failed to start audio relay server: {e}", exc_info=True)
            return False

    async def stop(self) -> None:
        """Stop the audio relay server."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("Audio relay server stopped")

        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass

    async def _handle_connection(
        self, websocket: ServerConnection, path: Optional[str] = None
    ) -> None:
        """Handle incoming WebSocket connections."""
        client_address = websocket.remote_address
        logger.info(f"New connection from {client_address}")

        async with self._connection_semaphore:
            try:
                async for message in websocket:
                    if isinstance(message, str):
                        await self.control_handler.process_control_message(
                            websocket, message
                        )
                    elif isinstance(message, bytes):
                        await self.audio_handler.process_audio_message(
                            websocket, message
                        )
            except ConnectionClosed:
                logger.info(f"Connection closed: {client_address}")
            except Exception as e:
                logger.error(
                    f"Error handling connection from {client_address}: {e}",
                    exc_info=True,
                )
            finally:
                await ConnectionUtils.cleanup_connection(
                    self.connections, websocket, logger
                )

    def get_stats(self) -> dict:
        """Get server statistics."""
        return {
            "server_running": self.server is not None,
            "registry_stats": self.connections.get_stats(),
        }


async def main() -> None:
    """Run the audio relay server."""
    server = AudioRelayServer()

    try:
        if await server.start():
            logger.info("Audio relay server running. Press Ctrl+C to stop.")
            await asyncio.Future()  # Run forever
    except KeyboardInterrupt:
        logger.info("Shutting down audio relay server...")
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
