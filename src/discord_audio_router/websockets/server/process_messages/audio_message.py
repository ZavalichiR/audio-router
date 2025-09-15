"""
Simplified audio message handler for WebSocket relay server.

This module handles audio message processing using the simplified ClientRegistry structure.
"""

import asyncio
import logging

from websockets.asyncio.server import ServerConnection
from websockets.exceptions import ConnectionClosed

from ...core import ConnectionManager


class AudioMessageHandler:
    """Handles audio message processing and routing."""

    def __init__(self, connections: ConnectionManager, logger: logging.Logger) -> None:
        self.connections = connections
        self.logger = logger

    async def process_audio_message(
        self, websocket: ServerConnection, audio_data: bytes
    ) -> None:
        """Process binary audio messages."""
        try:
            # Find which client this websocket belongs to
            client_id = None
            for cid, ws in self.connections.clients.items():
                if ws == websocket:
                    client_id = cid
                    break

            if not client_id:
                self.logger.warning("Received audio from unregistered connection")
                return

            # Check if this client is a speaker or listener
            if client_id in self.connections.speakers:
                # Speaker audio: broadcast to all listeners
                await self._broadcast_to_listeners(client_id, audio_data)
            elif client_id in self.connections.listeners:
                # Listener audio: send back to speaker
                await self._send_to_speaker(client_id, audio_data)

        except Exception as e:
            self.logger.error(f"Error processing audio message: {e}", exc_info=True)

    async def _broadcast_to_listeners(self, speaker_id: str, audio_data: bytes) -> None:
        """Broadcast audio from speaker to all listeners."""
        listener_ids = self.connections.get_speaker_listeners(speaker_id)

        if not listener_ids:
            self.logger.debug(f"No listeners for speaker {speaker_id}")
            return

        # Send to all listeners concurrently
        send_tasks = []
        for listener_id in listener_ids:
            listener_ws = self.connections.get_client_websocket(listener_id)
            if listener_ws:
                send_tasks.append(
                    self._safe_send_audio(listener_ws, audio_data, listener_id)
                )

        if send_tasks:
            results = await asyncio.gather(*send_tasks, return_exceptions=True)

            # Handle disconnected listeners
            for idx, result in enumerate(results):
                if isinstance(result, Exception):
                    listener_id = list(listener_ids)[idx]
                    if isinstance(result, ConnectionClosed):
                        self.logger.debug(f"Listener {listener_id} disconnected")
                        self.connections.unregister(listener_id)
                    else:
                        self.logger.error(f"Error sending to {listener_id}: {result}")

    async def _send_to_speaker(self, listener_id: str, audio_data: bytes) -> None:
        """Send audio from listener back to speaker."""
        speaker_id = self.connections.get_listener_speaker(listener_id)
        if not speaker_id:
            self.logger.warning(f"No speaker found for listener {listener_id}")
            return

        speaker_ws = self.connections.get_client_websocket(speaker_id)
        if speaker_ws:
            await self._safe_send_audio(speaker_ws, audio_data, speaker_id)
        else:
            self.logger.warning(f"Speaker {speaker_id} not connected")

    async def _safe_send_audio(
        self, websocket: ServerConnection, audio_data: bytes, client_id: str
    ) -> None:
        """Safely send audio data to a websocket."""
        try:
            await websocket.send(audio_data)
        except ConnectionClosed:
            raise  # Let caller handle cleanup
        except Exception as e:
            self.logger.error(f"Error sending audio to {client_id}: {e}")
            raise
