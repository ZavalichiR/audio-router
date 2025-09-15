"""
Simplified control message handler for WebSocket relay server.

This module handles control messages using the simplified ClientRegistry structure.
"""

import json
import logging
from typing import Any, Dict

from websockets.asyncio.server import ServerConnection

from discord_audio_router.core.types import (
    WS_CLIENT_TYPE_FWD,
    WS_CLIENT_TYPE_RCV,
    WS_MSG_REGISTER,
    WS_MSG_REGISTERED,
    WS_MSG_PING,
    WS_MSG_PONG,
    WS_MSG_ERROR,
)

from ...core import ConnectionManager


class ControlMessageHandler:
    """Handles control messages (registration, ping, etc.)."""

    def __init__(self, connections: ConnectionManager, logger: logging.Logger) -> None:
        self.connections = connections
        self.logger = logger

    async def process_control_message(
        self, websocket: ServerConnection, message: str
    ) -> None:
        """Process control messages (registration, ping, etc.)."""
        try:
            data = json.loads(message)
            message_type = data.get("type")
            client_id = data.get("id")

            if not client_id:
                await self._send_error(websocket, "Missing client ID")
                return

            if message_type == WS_MSG_REGISTER:
                await self._handle_register(websocket, data)
            elif message_type == WS_MSG_PING:
                await self._handle_ping(websocket, data)
            else:
                self.logger.warning(f"Unknown message type: {message_type}")
                await self._send_error(
                    websocket, f"Unknown message type: {message_type}"
                )

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse message: {e}")
            await self._send_error(websocket, "Invalid JSON")
        except Exception as e:
            self.logger.error(f"Error processing control message: {e}", exc_info=True)
            await self._send_error(websocket, "Internal server error")

    async def _handle_register(
        self, websocket: ServerConnection, data: Dict[str, Any]
    ) -> None:
        """Handle client registration."""
        client_id = data.get("id")
        client_type = data.get("client_type")

        if client_type == WS_CLIENT_TYPE_FWD:
            # Forwarder registration
            self.connections.register_speaker(client_id, websocket)
            self.logger.info(f"Forwarder registered: {client_id}")

            await websocket.send(
                json.dumps(
                    {
                        "type": WS_MSG_REGISTERED,
                        "client_id": client_id,
                        "listener_count": len(
                            self.connections.get_speaker_listeners(client_id)
                        ),
                    }
                )
            )

        elif client_type == WS_CLIENT_TYPE_RCV:
            # Listener registration - need speaker_id
            speaker_id = data.get("speaker_id")
            if not speaker_id:
                await self._send_error(websocket, "Missing speaker_id for receiver")
                return

            self.connections.register_listener(client_id, speaker_id, websocket)
            self.logger.info(f"Receiver registered: {client_id} -> {speaker_id}")

            await websocket.send(
                json.dumps(
                    {
                        "type": WS_MSG_REGISTERED,
                        "client_id": client_id,
                        "speaker_id": speaker_id,
                    }
                )
            )

        else:
            await self._send_error(websocket, f"Invalid client_type: {client_type}")

    async def _handle_ping(
        self, websocket: ServerConnection, data: Dict[str, Any]
    ) -> None:
        """Handle ping messages."""
        await websocket.send(
            json.dumps({"type": WS_MSG_PONG, "timestamp": data.get("timestamp")})
        )

    async def _send_error(self, websocket: ServerConnection, message: str) -> None:
        """Send error message to client."""
        try:
            await websocket.send(json.dumps({"type": WS_MSG_ERROR, "message": message}))
        except Exception as e:
            self.logger.error(f"Failed to send error message: {e}")
