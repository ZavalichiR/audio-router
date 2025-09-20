"""
Client-side control message handler.

This module handles control messages (registration, ping/pong, errors) for WebSocket clients.
"""

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from websockets.asyncio.client import ClientConnection

from discord_audio_router.core.types import (
    WS_CLIENT_TYPE_RCV,
    WS_MSG_REGISTER,
    WS_MSG_REGISTERED,
    WS_MSG_ERROR,
)

# Type alias for client types
ClientType = str  # WS_CLIENT_TYPE_FWD | WS_CLIENT_TYPE_RCV


def create_registration_message(
    client_id: str, client_type: ClientType, speaker_id: Optional[str] = None
) -> str:
    """
    Create a registration message for WebSocket server.

    Args:
        client_id: Unique client identifier
        client_type: Type of client (WS_CLIENT_TYPE_FWD or WS_CLIENT_TYPE_RCV)
        speaker_id: Speaker ID for receiver clients

    Returns:
        JSON string registration message
    """
    message = {
        "type": WS_MSG_REGISTER,
        "id": client_id,
        "client_type": client_type,
    }

    if client_type == WS_CLIENT_TYPE_RCV and speaker_id:
        message["speaker_id"] = speaker_id

    return json.dumps(message)


def validate_registration_response(
    data: Dict[str, Any], expected_client_id: str
) -> bool:
    """
    Validate registration response from server.

    Args:
        data: Parsed response data
        expected_client_id: Expected client ID

    Returns:
        True if response is valid
    """
    return (
        data.get("type") == WS_MSG_REGISTERED
        and data.get("client_id") == expected_client_id
    )


class ControlMessageHandler:
    """Handles control messages for WebSocket clients."""

    def __init__(
        self,
        client_id: str,
        client_type: ClientType,
        logger: logging.Logger,
        speaker_id: Optional[str] = None,
    ) -> None:
        """
        Initialize the control message handler.

        Args:
            client_id: Unique client identifier
            client_type: Type of client (WS_CLIENT_TYPE_FWD or WS_CLIENT_TYPE_RCV)
            logger: Logger instance
            speaker_id: Speaker ID for receiver clients
        """
        self.client_id: str = client_id
        self.client_type: ClientType = client_type
        self.logger: logging.Logger = logger
        self.speaker_id: Optional[str] = speaker_id
        self.is_registered: bool = False
        self.registration_future: Optional[asyncio.Future[bool]] = None

    async def register_with_server(self, websocket: ClientConnection) -> bool:
        """
        Register client with the WebSocket server.

        Args:
            websocket: WebSocket connection

        Returns:
            True if registration successful
        """
        try:
            self.logger.debug(f"[{self.client_id}] Registering with server")
            message = {
                "type": WS_MSG_REGISTER,
                "id": self.client_id,
                "client_type": self.client_type,
            }
            if self.client_type == WS_CLIENT_TYPE_RCV and self.speaker_id:
                message["speaker_id"] = self.speaker_id

            await websocket.send(json.dumps(message))
            self.logger.debug(
                f"[{self.client_id}] Sent registration message to server:{message}"
            )
            registration_future = self.create_registration_future()
            await registration_future

            return self.is_registered
        except Exception as e:
            self.logger.error(f"[{self.client_id}] Registration failed: {e}")
            return False

    def create_registration_future(self) -> asyncio.Future[bool]:
        """Create a new future for registration response."""
        self.registration_future = asyncio.Future()
        return self.registration_future

    async def process_control_message(self, message: str) -> None:
        """Process control messages (JSON)."""
        data = json.loads(message)
        if not data:
            return

        message_type = data.get("type")
        if message_type == WS_MSG_REGISTERED:
            self._handle_registration_response(data)
        elif message_type == WS_MSG_ERROR:
            self._handle_error_response(data)
        else:
            self.logger.warning(
                f"[{self.client_id}] Unknown control message: {message_type}"
            )

    def _handle_registration_response(self, data: Dict[str, Any]) -> None:
        """Handle successful registration response."""
        if validate_registration_response(data, self.client_id):
            self.is_registered = True
            self.logger.info(f"[{self.client_id}] Successfully registered with server")

            if self.registration_future and not self.registration_future.done():
                self.registration_future.set_result(True)
        else:
            self.logger.error(
                f"[{self.client_id}] Invalid registration response: {data}"
            )
            if self.registration_future and not self.registration_future.done():
                self.registration_future.set_exception(
                    Exception("Invalid registration response")
                )

    def _handle_error_response(self, data: Dict[str, Any]) -> None:
        """Handle error response from server."""
        error_msg = data.get("message", "Unknown error")
        self.logger.error(f"[{self.client_id}] Server error: {error_msg}")

        if self.registration_future and not self.registration_future.done():
            self.registration_future.set_exception(Exception(error_msg))
