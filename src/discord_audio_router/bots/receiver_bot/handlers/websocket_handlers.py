"""WebSocket connection handlers for the Audio Receiver Bot."""

import asyncio
import json
import logging
from typing import Optional, Callable

import websockets
import websockets.exceptions
from websockets.asyncio.client import connect, ClientConnection

from discord_audio_router.core.types import (
    WS_CLIENT_TYPE_RCV,
    WS_MSG_REGISTER,
)


class WebSocketHandlers:
    """Handles WebSocket connections and communication for the receiver bot."""

    def __init__(
        self,
        bot_id: str,
        channel_id: int,
        guild_id: int,
        speaker_channel_id: int,
        server_url: str,
        logger: logging.Logger,
    ):
        """Initialize WebSocket handlers."""
        self.bot_id = bot_id
        self.channel_id = channel_id
        self.guild_id = guild_id
        self.speaker_channel_id = speaker_channel_id
        self.server_url = server_url
        self.logger = logger
        self.websocket: Optional[ClientConnection] = None
        self.audio_callback: Optional[Callable] = None
        self._reconnecting = False

    def set_audio_callback(self, callback: Callable) -> None:
        """Set the callback function for received audio data."""
        self.audio_callback = callback

    async def connect(self) -> bool:
        """Connect to the centralized WebSocket server with retry logic."""
        try:
            if not self.speaker_channel_id:
                self.logger.error(
                    "No speaker channel ID provided - cannot connect to AudioForwarder bot"
                )
                return False

            self.logger.info(
                f"Attempting to connect to centralized WebSocket server for channel {self.speaker_channel_id}"
            )

            # Add retry logic with exponential backoff
            max_retries = 5
            retry_delay = 1.0

            for attempt in range(max_retries):
                try:
                    # Connect to centralized server with connection settings
                    self.websocket = await connect(
                        self.server_url,
                        ping_interval=None,  # Disable automatic pings
                        ping_timeout=None,  # Disable ping timeout
                        close_timeout=10,  # Shorter close timeout
                        open_timeout=30,  # Longer connection timeout
                        max_size=2**20,  # 1MB max message size
                        compression=None,  # Disable compression for lower latency
                    )

                    # Register as a receiver with the centralized server
                    client_id = f"{self.guild_id}_{self.channel_id}"
                    speaker_id = f"{self.guild_id}_{self.speaker_channel_id}"
                    registration_msg = {
                        "type": WS_MSG_REGISTER,
                        "id": client_id,
                        "client_type": WS_CLIENT_TYPE_RCV,
                        "speaker_id": speaker_id,
                    }
                    await self.websocket.send(json.dumps(registration_msg))

                    # Wait for confirmation
                    response = await self.websocket.recv()
                    self.logger.info(f"Registration response: {response}")

                    # Start listening for audio data
                    asyncio.create_task(self._listen_for_audio())

                    # Start ping task to keep connection alive
                    asyncio.create_task(self._ping_server())

                    self.logger.info(
                        f"Connected to centralized WebSocket server on attempt {attempt + 1}"
                    )
                    return True  # Success, exit the retry loop

                except ConnectionRefusedError as e:
                    self.logger.warning(
                        f"Connection refused on attempt {attempt + 1}/{max_retries}: {e}"
                    )
                    if attempt < max_retries - 1:
                        self.logger.info(f"Retrying in {retry_delay} seconds...")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        self.logger.error("Max retries reached, giving up")
                        raise
                except Exception as e:
                    self.logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2
                    else:
                        raise

        except Exception as e:
            self.logger.error(
                f"Failed to connect to AudioForwarder WebSocket after all retries: {e}"
            )
            # Retry connection after a delay
            asyncio.create_task(self._retry_connection())
            return False

    async def _retry_connection(self) -> None:
        """Retry connection to AudioForwarder bot."""
        retry_delay = 5.0
        max_retries = 10
        retry_count = 0

        while retry_count < max_retries:
            try:
                await asyncio.sleep(retry_delay)
                await self.connect()
                return
            except Exception as e:
                retry_count += 1
                self.logger.warning(f"Retry {retry_count}/{max_retries} failed: {e}")
                retry_delay = min(retry_delay * 1.5, 30.0)  # Exponential backoff

        self.logger.error(
            "Failed to connect to centralized WebSocket server after maximum retries"
        )

    async def _ping_server(self) -> None:
        """Send periodic pings to keep the WebSocket connection alive."""
        while True:
            try:
                await asyncio.sleep(15)  # Ping every 15 seconds

                if self.websocket and not getattr(self.websocket, "closed", True):
                    try:
                        await self.websocket.send('{"type": "ping", "timestamp": null}')
                        self.logger.debug("Sent ping to centralized server")
                    except websockets.exceptions.ConnectionClosed:
                        self.logger.debug("Connection closed while sending ping")
                        break
                    except Exception as e:
                        self.logger.error(f"Error sending ping: {e}", exc_info=True)
                        break
                else:
                    self.logger.debug("WebSocket not available for ping")
                    break

            except Exception as e:
                self.logger.error(f"Error in ping task: {e}", exc_info=True)
                break

    async def _listen_for_audio(self) -> None:
        """Listen for audio data from the centralized WebSocket server."""
        while True:
            try:
                async for message in self.websocket:
                    try:
                        # Check if message is binary (audio data) or text (control)
                        if isinstance(message, bytes):
                            # Raw binary audio data from centralized server
                            if self.audio_callback:
                                # Call the audio callback with the received data
                                await self.audio_callback(message)
                            else:
                                self.logger.warning(
                                    "Received binary audio but no callback available"
                                )
                        else:
                            # Text control message
                            try:
                                # Parse JSON control messages
                                data = json.loads(message)

                                if data.get("type") == "registered":
                                    self.logger.info(
                                        f"Successfully registered as listener: {data.get('client_id')}"
                                    )
                                    # Notify performance monitor that binary protocol is enabled
                                    if hasattr(self, "performance_monitor"):
                                        self.performance_monitor.set_binary_protocol_enabled(
                                            True
                                        )
                                    self.logger.info(
                                        "Binary protocol enabled for audio transmission"
                                    )

                                elif data.get("type") == "pong":
                                    # Handle pong responses
                                    pass

                            except Exception as e:
                                self.logger.error(
                                    f"Failed to parse control message: {e}"
                                )

                    except Exception as e:
                        self.logger.error(
                            f"Error processing message: {e}", exc_info=True
                        )

                # If we exit the async for loop, the connection was closed
                self.logger.warning(
                    "WebSocket connection closed, attempting to reconnect..."
                )
                break

            except websockets.exceptions.ConnectionClosed:
                self.logger.warning(
                    "AudioForwarder WebSocket connection closed, attempting to reconnect..."
                )
                break
            except Exception as e:
                self.logger.error(f"Error listening for audio: {e}", exc_info=True)
                break

    async def disconnect(self) -> None:
        """Disconnect from the WebSocket server."""
        try:
            if self.websocket:
                await self.websocket.close()
                self.websocket = None
                self.logger.info("Disconnected from centralized WebSocket server")
        except Exception as e:
            self.logger.error(f"Error disconnecting from WebSocket: {e}", exc_info=True)
