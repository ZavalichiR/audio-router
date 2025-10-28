"""
Unified WebSocket client for Discord Audio Router.

This module provides a unified WebSocket client that can handle both
forwarder and receiver roles with automatic ping management.
"""

import asyncio
import logging
from typing import Any, Callable, Dict, Optional

import websockets
import websockets.exceptions
from websockets.asyncio.client import connect, ClientConnection

from discord_audio_router.core.types import WS_CLIENT_TYPE_FWD, WS_CLIENT_TYPE_RCV

from .process_messages import ControlMessageHandler, AudioMessageHandler

# Type alias for client types
ClientType = str  # WS_CLIENT_TYPE_FWD | WS_CLIENT_TYPE_RCV


class WebSocketClient:
    """
    Unified WebSocket client for both forwarder and receiver bots.

    This client supports automatic ping management and can handle
    both audio forwarding and receiving roles.
    """

    def __init__(
        self,
        client_id: str,
        client_type: ClientType,
        server_url: str,
        logger: logging.Logger,
        main_client_id: Optional[str] = None,
        audio_callback: Optional[Callable[[bytes], None]] = None,
        event_loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        """
        Initialize the WebSocket client.

        Args:
            client_id: Unique client identifier
            client_type: Type of client (WS_CLIENT_TYPE_FWD or WS_CLIENT_TYPE_RCV)
            server_url: WebSocket server URL
            logger: Logger instance
            main_client_id: Main client ID for receiver clients
            audio_callback: Callback for audio data (for receiver clients)
            event_loop: Event loop for thread-safe operations (defaults to current loop)
        """
        # Validate parameters
        if not client_id:
            raise ValueError("client_id cannot be empty")
        if client_type not in (WS_CLIENT_TYPE_FWD, WS_CLIENT_TYPE_RCV):
            raise ValueError(
                f"client_type must be '{WS_CLIENT_TYPE_FWD}' or '{WS_CLIENT_TYPE_RCV}'"
            )
        if not server_url:
            raise ValueError("server_url cannot be empty")
        if not server_url.startswith(("ws://", "wss://")):
            raise ValueError("server_url must start with 'ws://' or 'wss://'")

        self.client_id: str = client_id
        self.client_type: ClientType = client_type
        self.server_url: str = server_url
        self.logger: logging.Logger = logger
        self.main_client_id: Optional[str] = main_client_id

        # WebSocket connection
        self.websocket: Optional[ClientConnection] = None
        self.is_connected: bool = False

        # Message processing handlers
        self.control_handler: ControlMessageHandler = ControlMessageHandler(
            client_id=client_id,
            client_type=client_type,
            logger=logger,
            speaker_id=main_client_id,
        )

        self.audio_handler: AudioMessageHandler = AudioMessageHandler(
            logger=logger,
            audio_callback=audio_callback,
            track_audio_callback=self._track_received_audio,
        )

        # Connection management
        self._connection_task: Optional[asyncio.Task[None]] = None
        self._reconnect_task: Optional[asyncio.Task[None]] = None
        self._should_reconnect: bool = True

        # Event loop for thread-safe operations
        self.event_loop: asyncio.AbstractEventLoop = (
            event_loop or asyncio.get_running_loop()
        )

        # Performance tracking
        self._audio_packets_sent: int = 0
        self._audio_packets_received: int = 0
        self._connection_errors: int = 0

    async def connect(self, max_retries: int = 5, retry_delay: float = 1.0) -> bool:
        """
        Connect to the WebSocket server with retry logic.

        Args:
            max_retries: Maximum number of connection attempts
            retry_delay: Initial delay between retries (exponential backoff)

        Returns:
            True if connection successful, False otherwise
        """
        for attempt in range(max_retries):
            try:
                self.logger.info(
                    f"[{self.client_id}] Connecting to server (attempt {attempt + 1}/{max_retries})"
                )

                # Connect with optimized settings for audio
                self.websocket = await connect(
                    self.server_url,
                    compression=None,
                )

                self.logger.info(
                    f"[{self.client_id}] Connection created, registering..."
                )

                # Start message processing task BEFORE registration
                # so it can receive and process the registration acknowledgment
                self._connection_task = asyncio.create_task(
                    self._process_messages()
                )

                # Register with server and wait for acknowledgment
                if await self.control_handler.register_with_server(self.websocket):
                    # Only set flag after successful registration
                    self.is_connected = True
                    self.logger.info(f"[{self.client_id}] Client ready")
                    return True
                else:
                    self.logger.error(f"[{self.client_id}] Registration failed")
                    await self.disconnect()
                    return False

            except ConnectionRefusedError as e:
                self.logger.error(
                    f"[{self.client_id}] Connection refused (attempt {attempt + 1}): {e}",
                    exc_info=True,
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    self.logger.error(
                        f"[{self.client_id}] Connection refused (attempt {attempt + 1}): {e}",
                        exc_info=True,
                    )
                    return False

            except Exception as e:
                self.logger.error(
                    f"[{self.client_id}] Error connecting (attempt {attempt + 1}): {e}",
                    exc_info=True,
                )
                self._connection_errors += 1
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    return False

        return False

    async def _process_messages(self) -> None:
        """Process incoming messages from the server."""
        try:
            async for message in self.websocket:
                if isinstance(message, str):
                    await self.control_handler.process_control_message(message)
                elif isinstance(message, bytes):
                    await self.audio_handler.process_audio_message(message)
        except websockets.exceptions.ConnectionClosed:
            self.logger.error(f"[{self.client_id}] Connection closed by server")
        except Exception as e:
            self.logger.error(
                f"[{self.client_id}] Error processing messages: {e}", exc_info=True
            )
        finally:
            self.is_connected = False
            self.control_handler.is_registered = False

            # Start reconnection if enabled
            if self._should_reconnect and not self._reconnect_task:
                self._reconnect_task = asyncio.create_task(self._handle_reconnection())

    def forward_audio(self, audio_data: bytes) -> None:
        """
        Forward audio data to the server (thread-safe).

        This method is designed to be called from the audio sink thread,
        so it uses run_coroutine_threadsafe to schedule the WebSocket send.

        Args:
            audio_data: Binary audio data to send
        """
        if not self.is_connected or not self.websocket:
            self.logger.warning(
                f"[{self.client_id}] Cannot send audio - not connected (is_connected: {self.is_connected}, websocket: {self.websocket is not None})"
            )
            return

        try:
            # Send to server using thread-safe scheduling
            # Note: This is called from the audio sink thread, so we need to schedule
            # the WebSocket send on the event loop using run_coroutine_threadsafe
            if self.event_loop:
                asyncio.run_coroutine_threadsafe(
                    self._send_binary_data(audio_data), self.event_loop
                )
                self._audio_packets_sent += 1
                # Don't wait for the result to avoid blocking the audio thread
            else:
                self.logger.warning(
                    f"[{self.client_id}] No event loop set - cannot send audio"
                )

        except Exception as e:
            self.logger.error(
                f"[{self.client_id}] Error forwarding audio: {e}", exc_info=True
            )

    async def _send_binary_data(self, audio_data: bytes) -> None:
        """Send binary audio data to server (internal async method)."""
        try:
            if self.websocket:
                await self.websocket.send(audio_data)
        except websockets.exceptions.ConnectionClosed:
            self.logger.warning(
                f"[{self.client_id}] Connection closed while sending audio"
            )
            self.is_connected = False
        except Exception as e:
            self.logger.error(
                f"[{self.client_id}] Error sending audio: {e}", exc_info=True
            )

    async def _handle_reconnection(self) -> None:
        """Handle automatic reconnection with exponential backoff."""
        base_delay = 1.0
        max_delay = 60.0  # Cap at 60 seconds between retries
        retry_count = 0

        while self._should_reconnect:
            try:
                retry_count += 1
                # Exponential backoff capped at max_delay
                delay = min(base_delay * (2 ** (retry_count - 1)), max_delay)

                self.logger.info(
                    f"[{self.client_id}] Attempting reconnection #{retry_count} in {delay:.1f}s..."
                )
                await asyncio.sleep(delay)

                await self.connect()
                self.logger.info(
                    f"[{self.client_id}] Reconnection successful after {retry_count} attempts"
                )
                return

            except Exception as e:
                self.logger.error(
                    f"[{self.client_id}] Reconnection attempt #{retry_count} failed: {e}"
                )
                # Continue trying indefinitely while _should_reconnect is True

    def _track_received_audio(self) -> None:
        """Track received audio packets for performance monitoring."""
        self._audio_packets_received += 1

    async def disconnect(self) -> None:
        """Disconnect from the WebSocket server."""
        self._should_reconnect = False

        # Cancel tasks
        if self._connection_task:
            self._connection_task.cancel()
            try:
                await self._connection_task
            except asyncio.CancelledError:
                pass
            self._connection_task = None

        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
            self._reconnect_task = None

        # Close WebSocket
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception as e:
                self.logger.error(
                    f"[{self.client_id}] Error disconnecting: {e}", exc_info=True
                )
            finally:
                self.websocket = None
                self.is_connected = False

        self.logger.info(f"[{self.client_id}] Disconnected from server")

    def get_status(self) -> Dict[str, Any]:
        """Get client status and performance information."""
        return {
            "client_id": self.client_id,
            "client_type": self.client_type,
            "is_connected": self.is_connected,
            "is_registered": self.control_handler.is_registered,
            "server_url": self.server_url,
            "audio_packets_sent": self._audio_packets_sent,
            "audio_packets_received": self._audio_packets_received,
            "connection_errors": self._connection_errors,
        }
