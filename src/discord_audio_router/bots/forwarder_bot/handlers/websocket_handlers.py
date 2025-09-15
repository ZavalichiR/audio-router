"""WebSocket connection handlers for the Audio Forwarder Bot."""

import asyncio
import json
import logging
from typing import Optional

import websockets
import websockets.exceptions
from websockets.asyncio.client import connect, ClientConnection

from discord_audio_router.core.types import (
    WS_CLIENT_TYPE_FWD,
    WS_MSG_REGISTER,
)


class WebSocketHandlers:
    """Handles WebSocket connections and communication."""

    def __init__(
        self,
        bot_id: str,
        channel_id: int,
        guild_id: int,
        server_url: str,
        logger: logging.Logger,
    ):
        """Initialize WebSocket handlers."""
        self.bot_id = bot_id
        self.channel_id = channel_id
        self.guild_id = guild_id
        self.server_url = server_url
        self.logger = logger
        self.websocket: Optional[ClientConnection] = None
        self.event_loop: Optional[asyncio.AbstractEventLoop] = None

    async def connect(self) -> bool:
        """Connect to the centralized WebSocket server."""
        try:
            self.logger.info(
                f"Connecting to centralized WebSocket server: {self.server_url}"
            )

            # Connect to centralized server with settings
            self.websocket = await connect(
                self.server_url,
                ping_interval=None,  # Disable automatic pings
                ping_timeout=None,  # Disable ping timeout
                close_timeout=5,  # Shorter close timeout
                open_timeout=30,  # Longer connection timeout
                max_size=2**20,  # 1MB max message size
                compression=None,  # Disable compression for lower latency
            )

            # Register as a forwarder with the centralized server
            client_id = f"{self.guild_id}_{self.channel_id}"
            registration_msg = {
                "type": WS_MSG_REGISTER,
                "id": client_id,
                "client_type": WS_CLIENT_TYPE_FWD,
            }
            await self.websocket.send(json.dumps(registration_msg))

            # Wait for confirmation
            response = await self.websocket.recv()
            self.logger.info(f"Registration response: {response}")

            self.logger.info(
                f"Connected to centralized WebSocket server for {self.bot_id}"
            )

            # Start connection health monitoring
            asyncio.create_task(self._monitor_connection())

            return True

        except Exception as e:
            self.logger.error(
                f"Failed to connect to centralized WebSocket server: {e}", exc_info=True
            )
            return False

    async def _monitor_connection(self) -> None:
        """Monitor connection to centralized server."""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds

                if self.websocket:
                    try:
                        # Try to check if connection is closed
                        if hasattr(self.websocket, "closed") and self.websocket.closed:
                            self.logger.warning(
                                "Centralized WebSocket connection lost, attempting to reconnect..."
                            )
                            await self.connect()
                    except AttributeError:
                        # Connection object doesn't have 'closed' attribute, assume it's open
                        pass

            except Exception as e:
                self.logger.error(
                    f"Error monitoring centralized connection: {e}", exc_info=True
                )
                await asyncio.sleep(5)  # Wait before retrying

    def forward_audio(self, audio_data: bytes) -> None:
        """Forward audio data to the centralized server."""
        if not self.websocket:
            return

        try:
            # Send to centralized server
            # Note: This is called from the audio sink thread, so we need to schedule
            # the WebSocket send on the event loop using run_coroutine_threadsafe
            if self.event_loop:
                asyncio.run_coroutine_threadsafe(
                    self._send_binary_data(audio_data), self.event_loop
                )
                # Don't wait for the result to avoid blocking the audio thread

        except Exception as e:
            self.logger.error(
                f"Error forwarding audio to centralized server: {e}", exc_info=True
            )

    async def _send_binary_data(self, audio_data: bytes) -> None:
        """Send binary audio data to centralized server."""
        try:
            if self.websocket:
                await self.websocket.send(audio_data)
            else:
                self.logger.warning("Centralized WebSocket connection not available")
        except websockets.exceptions.ConnectionClosed:
            self.logger.warning("Centralized WebSocket connection closed")
            self.websocket = None
        except Exception as e:
            self.logger.error(
                f"Error sending audio to centralized server: {e}", exc_info=True
            )

    async def disconnect(self) -> None:
        """Disconnect from the WebSocket server."""
        try:
            if self.websocket:
                await self.websocket.close()
                self.websocket = None
                self.logger.info("Disconnected from centralized WebSocket server")
        except Exception as e:
            self.logger.error(f"Error disconnecting from WebSocket: {e}", exc_info=True)

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Set the event loop for thread-safe operations."""
        self.event_loop = loop
