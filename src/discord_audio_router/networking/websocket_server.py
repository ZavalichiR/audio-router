"""
Centralized Audio Relay Server for Discord Audio Router.

This module provides a centralized WebSocket server that can handle
audio routing between multiple speaker and listener bots, providing
better scalability and fault tolerance.
"""

import asyncio
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Set, Any

# Add src directory to Python path for direct execution
if __name__ == "__main__":
    src_path = Path(__file__).parent.parent.parent.parent / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

import websockets

from discord_audio_router.infrastructure import setup_logging

# Configure logging
logger = setup_logging(
    component_name="websocket_server",
    log_file="logs/websocket_server.log",
)


@dataclass
class AudioRoute:
    """Represents an audio routing path."""

    speaker_id: str
    speaker_channel_id: int
    guild_id: int = 0  # Add guild support
    listener_ids: Set[str] = field(default_factory=set)
    is_active: bool = True
    last_audio_ts: float = field(default_factory=time.time)


class AudioRelayServer:
    """
    Centralized WebSocket server for audio routing.

    This server acts as a hub for audio data, allowing multiple
    speaker bots to broadcast to multiple listener bots.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8765,
        ping_interval: int = 30,
    ):
        """
        Initialize the audio relay server.

        Args:
            host: Host address to bind to
            port: Port to listen on
            ping_interval: Interval in seconds to send pings to clients
        """
        self.host = host
        self.port = port
        self.server: Optional[websockets.WebSocketServer] = None

        # Audio routing state
        self.audio_routes: Dict[str, AudioRoute] = {}  # speaker_id -> route
        self.guild_routes: Dict[int, Dict[int, AudioRoute]] = {}  # guild_id -> {speaker_channel: route}
        self.connected_speakers: Dict[
            str, websockets.WebSocketServerProtocol
        ] = {}
        self.connected_listeners: Dict[
            str, websockets.WebSocketServerProtocol
        ] = {}

        # Reverse lookup for fast cleanup
        self.websocket_to_id: Dict[websockets.WebSocketServerProtocol, str] = (
            {}
        )

        # Statistics
        self.stats = {
            "total_connections": 0,
            "active_routes": 0,
            "audio_packets_forwarded": 0,
            "bytes_forwarded": 0,
        }

        self.ping_interval = ping_interval
        self._health_task: Optional[asyncio.Task] = None
        
        # Connection pool optimization
        self._connection_semaphore = asyncio.Semaphore(100)  # Limit concurrent connections

    async def start(self):
        """Start the audio relay server."""
        try:
            self.server = await websockets.serve(
                self._handle_connection,
                self.host,
                self.port,
                ping_interval=None,  # We'll handle pings manually
                max_size=2**20,  # 1MB max message size
                compression=None,  # Disable compression for lower latency
            )
            logger.info(
                f"Audio relay server started on {self.host}:{self.port}"
            )
            self._health_task = asyncio.create_task(
                self._monitor_connections()
            )
            return True
        except Exception as e:
            logger.error(f"Failed to start audio relay server: {e}", exc_info=True)
            return False

    async def stop(self):
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

    async def _handle_connection(self, websocket, path=None):
        """Handle incoming WebSocket connections with connection pool management."""
        client_address = websocket.remote_address
        logger.info(f"New connection from {client_address}")

        # Use semaphore to limit concurrent connections
        async with self._connection_semaphore:
            self.stats["total_connections"] += 1

            try:
                async for message in websocket:
                    # Handle both text (control) and binary (audio) messages
                    if isinstance(message, str):
                        await self._process_message(websocket, message)
                    elif isinstance(message, bytes):
                        # Get the speaker ID from the websocket connection
                        speaker_id = self.websocket_to_id.get(websocket)
                        if speaker_id:
                            # Use existing binary audio forwarding function
                            await self._forward_binary_audio(speaker_id, message)
                        else:
                            logger.warning(f"Received binary message from unregistered connection")
            except websockets.exceptions.ConnectionClosed:
                logger.info(f"Connection closed: {client_address}")
            except Exception as e:
                logger.error(
                    f"Error handling connection from {client_address}: {e}", exc_info=True
                )
            finally:
                await self._cleanup_connection(websocket)

    async def _process_message(self, websocket, message: str):
        """Process incoming WebSocket messages."""
        try:
            data = json.loads(message)
            message_type = data.get("type")

            if message_type == "speaker_register":
                await self._handle_speaker_register(websocket, data)
            elif message_type == "listener_register":
                await self._handle_listener_register(websocket, data)
            elif message_type == "ping":
                await self._handle_ping(websocket, data)
            elif message_type == "stats":
                await self._handle_stats_request(websocket, data)
            else:
                logger.warning(f"Unknown message type: {message_type}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)


    async def _handle_speaker_register(self, websocket, data):
        """Handle speaker bot registration."""
        speaker_id = data.get("speaker_id")
        channel_id = data.get("channel_id")
        guild_id = data.get("guild_id", 0)  # Add guild support

        if not speaker_id or not channel_id:
            await websocket.send(
                json.dumps(
                    {
                        "type": "error",
                        "message": "Missing speaker_id or channel_id",
                    }
                )
            )
            return

        # Register speaker
        self.connected_speakers[speaker_id] = websocket
        self.websocket_to_id[websocket] = speaker_id

        # Create or update audio route
        if speaker_id not in self.audio_routes:
            self.audio_routes[speaker_id] = AudioRoute(
                speaker_id=speaker_id,
                speaker_channel_id=channel_id,
                guild_id=guild_id,
                listener_ids=set(),
            )
            self.stats["active_routes"] += 1
        else:
            self.audio_routes[speaker_id].is_active = True
            self.audio_routes[speaker_id].speaker_channel_id = channel_id
            self.audio_routes[speaker_id].guild_id = guild_id

        # Add to guild routes for efficient lookup
        if guild_id not in self.guild_routes:
            self.guild_routes[guild_id] = {}
        self.guild_routes[guild_id][channel_id] = self.audio_routes[speaker_id]

        logger.info(
            f"Speaker registered: {speaker_id} (channel: {channel_id}, guild: {guild_id})"
        )

        # Send confirmation
        await websocket.send(
            json.dumps(
                {
                    "type": "speaker_registered",
                    "speaker_id": speaker_id,
                    "listener_count": len(
                        self.audio_routes[speaker_id].listener_ids
                    ),
                }
            )
        )

    async def _handle_listener_register(self, websocket, data):
        """Handle listener bot registration."""
        listener_id = data.get("listener_id")
        speaker_id = data.get("speaker_id")
        channel_id = data.get("channel_id")

        if not all([listener_id, speaker_id, channel_id]):
            await websocket.send(
                json.dumps(
                    {
                        "type": "error",
                        "message": "Missing listener_id, speaker_id, or channel_id",
                    }
                )
            )
            return

        # Register listener
        self.connected_listeners[listener_id] = websocket
        self.websocket_to_id[websocket] = listener_id

        # Add to audio route
        if speaker_id in self.audio_routes:
            self.audio_routes[speaker_id].listener_ids.add(listener_id)
        else:
            # Create new route if speaker not registered yet
            self.audio_routes[speaker_id] = AudioRoute(
                speaker_id=speaker_id,
                speaker_channel_id=channel_id,
                listener_ids={listener_id},
            )
            self.stats["active_routes"] += 1

        logger.info(f"Listener registered: {listener_id} -> {speaker_id}")

        # Send confirmation
        await websocket.send(
            json.dumps(
                {
                    "type": "listener_registered",
                    "listener_id": listener_id,
                    "speaker_id": speaker_id,
                }
            )
        )


    async def _safe_send_audio(self, websocket, message, listener_id):
        try:
            await websocket.send(message)
        except websockets.exceptions.ConnectionClosed:
            raise
        except Exception as e:
            logger.error(f"Error sending audio to {listener_id}: {e}", exc_info=True)
            raise

    async def _forward_binary_audio(self, speaker_id: str, audio_data: bytes):
        """Forward binary audio from speaker to all connected listeners."""
        try:
            if speaker_id not in self.audio_routes:
                logger.warning(f"Audio from unregistered speaker: {speaker_id}")
                return

            route = self.audio_routes[speaker_id]
            if not route.is_active:
                return

            route.last_audio_ts = time.time()

            # Forward to all connected listeners concurrently for performance
            listeners_to_send = [
                (listener_id, self.connected_listeners[listener_id])
                for listener_id in list(route.listener_ids)
                if listener_id in self.connected_listeners
            ]

            if not listeners_to_send:
                return

            # Send binary audio to all listeners concurrently
            send_tasks = []
            for listener_id, listener_websocket in listeners_to_send:
                send_tasks.append(
                    self._safe_send_audio(listener_websocket, audio_data, listener_id)
                )

            # Wait for all sends to complete concurrently
            results = await asyncio.gather(*send_tasks, return_exceptions=True)

            # Clean up disconnected listeners efficiently
            disconnected_listeners = []
            for idx, result in enumerate(results):
                if isinstance(result, Exception):
                    listener_id = listeners_to_send[idx][0]
                    disconnected_listeners.append(listener_id)
                    if isinstance(result, websockets.exceptions.ConnectionClosed):
                        logger.debug(f"Listener {listener_id} disconnected")
                    else:
                        logger.error(f"Error sending binary audio to listener {listener_id}: {result}")

            # Batch cleanup of disconnected listeners
            for listener_id in disconnected_listeners:
                route.listener_ids.discard(listener_id)
                self.connected_listeners.pop(listener_id, None)

            if disconnected_listeners:
                logger.debug(f"Removed {len(disconnected_listeners)} disconnected listeners")

            # Update statistics
            successful_sends = len(listeners_to_send) - len(disconnected_listeners)
            self.stats["audio_packets_forwarded"] += successful_sends
            self.stats["bytes_forwarded"] += len(audio_data) * successful_sends

        except Exception as e:
            logger.error(f"Error forwarding binary audio: {e}", exc_info=True)


    async def _handle_ping(self, websocket, data):
        """Handle ping messages for connection health checks."""
        await websocket.send(
            json.dumps({"type": "pong", "timestamp": data.get("timestamp")})
        )

    async def _handle_stats_request(self, websocket, data):
        """Handle stats request from client."""
        await websocket.send(
            json.dumps(
                {
                    "type": "stats",
                    "stats": self.get_stats(),
                    "routes": self.get_route_info(),
                }
            )
        )

    async def _cleanup_connection(self, websocket):
        """Clean up when a connection is closed."""
        # Remove from speakers
        id_ = self.websocket_to_id.pop(websocket, None)
        if id_:
            if (
                id_ in self.connected_speakers
                and self.connected_speakers[id_] == websocket
            ):
                del self.connected_speakers[id_]
                if id_ in self.audio_routes:
                    route = self.audio_routes[id_]
                    route.is_active = False
                    # Remove from guild routes
                    if route.guild_id in self.guild_routes and route.speaker_channel_id in self.guild_routes[route.guild_id]:
                        del self.guild_routes[route.guild_id][route.speaker_channel_id]
                        if not self.guild_routes[route.guild_id]:
                            del self.guild_routes[route.guild_id]
                logger.info(f"Speaker disconnected: {id_}")
            elif (
                id_ in self.connected_listeners
                and self.connected_listeners[id_] == websocket
            ):
                del self.connected_listeners[id_]
                # Remove from all routes
                for route in self.audio_routes.values():
                    route.listener_ids.discard(id_)
                logger.info(f"Listener disconnected: {id_}")

    async def _monitor_connections(self):
        """Periodically check connection health and clean up stale routes."""
        while True:
            await asyncio.sleep(self.ping_interval)
            now = time.time()
            # Remove inactive routes (no audio for 5 minutes)
            for speaker_id, route in list(self.audio_routes.items()):
                if route.is_active and now - route.last_audio_ts > 300:
                    logger.info(
                        f"Route {speaker_id} inactive for 5 minutes, marking as inactive."
                    )
                    route.is_active = False
            # Optionally, send pings to all clients to keep connections alive
            for ws in list(self.websocket_to_id.keys()):
                try:
                    await ws.ping()
                except Exception:
                    # Will be cleaned up on next message or disconnect
                    pass

    def get_stats(self) -> Dict[str, Any]:
        """Get server statistics."""
        return {
            **self.stats,
            "connected_speakers": len(self.connected_speakers),
            "connected_listeners": len(self.connected_listeners),
            "active_routes": len(
                [r for r in self.audio_routes.values() if r.is_active]
            ),
        }

    def get_route_info(self) -> Dict[str, Any]:
        """Get detailed route information."""
        routes = {}
        for speaker_id, route in self.audio_routes.items():
            routes[speaker_id] = {
                "speaker_channel_id": route.speaker_channel_id,
                "guild_id": route.guild_id,
                "listener_count": len(route.listener_ids),
                "listener_ids": list(route.listener_ids),
                "is_active": route.is_active,
                "last_audio_ts": route.last_audio_ts,
            }
        return routes


async def main():
    """Main function to run the audio relay server."""
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
