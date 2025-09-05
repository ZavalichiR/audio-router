"""
Centralized Audio Relay Server for Discord Audio Router.

This module provides a centralized WebSocket server that can handle
audio routing between multiple speaker and listener bots, providing
better scalability and fault tolerance.
"""

import asyncio
import json
import logging
import websockets
from typing import Dict, Set, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AudioRoute:
    """Represents an audio routing path."""
    speaker_id: str
    speaker_channel_id: int
    listener_ids: Set[str]
    is_active: bool = True


class AudioRelayServer:
    """
    Centralized WebSocket server for audio routing.
    
    This server acts as a hub for audio data, allowing multiple
    speaker bots to broadcast to multiple listener bots.
    """
    
    def __init__(self, host: str = "localhost", port: int = 8765):
        """
        Initialize the audio relay server.
        
        Args:
            host: Host address to bind to
            port: Port to listen on
        """
        self.host = host
        self.port = port
        self.server: Optional[websockets.WebSocketServerProtocol] = None
        
        # Audio routing state
        self.audio_routes: Dict[str, AudioRoute] = {}  # speaker_id -> route
        self.connected_speakers: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.connected_listeners: Dict[str, websockets.WebSocketServerProtocol] = {}
        
        # Statistics
        self.stats = {
            'total_connections': 0,
            'active_routes': 0,
            'audio_packets_forwarded': 0,
            'bytes_forwarded': 0
        }
    
    async def start(self):
        """Start the audio relay server."""
        try:
            self.server = await websockets.serve(
                self._handle_connection,
                self.host,
                self.port
            )
            logger.info(f"Audio relay server started on {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to start audio relay server: {e}")
            return False
    
    async def stop(self):
        """Stop the audio relay server."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("Audio relay server stopped")
    
    async def _handle_connection(self, websocket, path):
        """Handle incoming WebSocket connections."""
        client_address = websocket.remote_address
        logger.info(f"New connection from {client_address}")
        
        self.stats['total_connections'] += 1
        
        try:
            async for message in websocket:
                await self._process_message(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Connection closed: {client_address}")
        except Exception as e:
            logger.error(f"Error handling connection from {client_address}: {e}")
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
            elif message_type == "audio":
                await self._handle_audio_data(websocket, data)
            elif message_type == "ping":
                await self._handle_ping(websocket, data)
            else:
                logger.warning(f"Unknown message type: {message_type}")
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message: {e}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    async def _handle_speaker_register(self, websocket, data):
        """Handle speaker bot registration."""
        speaker_id = data.get("speaker_id")
        channel_id = data.get("channel_id")
        
        if not speaker_id or not channel_id:
            await websocket.send(json.dumps({
                "type": "error",
                "message": "Missing speaker_id or channel_id"
            }))
            return
        
        # Register speaker
        self.connected_speakers[speaker_id] = websocket
        
        # Create or update audio route
        if speaker_id not in self.audio_routes:
            self.audio_routes[speaker_id] = AudioRoute(
                speaker_id=speaker_id,
                speaker_channel_id=channel_id,
                listener_ids=set()
            )
            self.stats['active_routes'] += 1
        
        logger.info(f"Speaker registered: {speaker_id} (channel: {channel_id})")
        
        # Send confirmation
        await websocket.send(json.dumps({
            "type": "speaker_registered",
            "speaker_id": speaker_id,
            "listener_count": len(self.audio_routes[speaker_id].listener_ids)
        }))
    
    async def _handle_listener_register(self, websocket, data):
        """Handle listener bot registration."""
        listener_id = data.get("listener_id")
        speaker_id = data.get("speaker_id")
        channel_id = data.get("channel_id")
        
        if not all([listener_id, speaker_id, channel_id]):
            await websocket.send(json.dumps({
                "type": "error",
                "message": "Missing listener_id, speaker_id, or channel_id"
            }))
            return
        
        # Register listener
        self.connected_listeners[listener_id] = websocket
        
        # Add to audio route
        if speaker_id in self.audio_routes:
            self.audio_routes[speaker_id].listener_ids.add(listener_id)
        else:
            # Create new route if speaker not registered yet
            self.audio_routes[speaker_id] = AudioRoute(
                speaker_id=speaker_id,
                speaker_channel_id=channel_id,
                listener_ids={listener_id}
            )
            self.stats['active_routes'] += 1
        
        logger.info(f"Listener registered: {listener_id} -> {speaker_id}")
        
        # Send confirmation
        await websocket.send(json.dumps({
            "type": "listener_registered",
            "listener_id": listener_id,
            "speaker_id": speaker_id
        }))
    
    async def _handle_audio_data(self, websocket, data):
        """Handle audio data forwarding."""
        speaker_id = data.get("speaker_id")
        audio_data = data.get("audio_data")
        
        if not speaker_id or not audio_data:
            return
        
        # Check if speaker is registered
        if speaker_id not in self.audio_routes:
            logger.warning(f"Audio from unregistered speaker: {speaker_id}")
            return
        
        route = self.audio_routes[speaker_id]
        if not route.is_active:
            return
        
        # Forward to all connected listeners
        disconnected_listeners = set()
        for listener_id in route.listener_ids:
            if listener_id in self.connected_listeners:
                try:
                    listener_websocket = self.connected_listeners[listener_id]
                    await listener_websocket.send(json.dumps({
                        "type": "audio",
                        "speaker_id": speaker_id,
                        "audio_data": audio_data
                    }))
                    
                    self.stats['audio_packets_forwarded'] += 1
                    self.stats['bytes_forwarded'] += len(audio_data)
                    
                except websockets.exceptions.ConnectionClosed:
                    disconnected_listeners.add(listener_id)
                except Exception as e:
                    logger.error(f"Error forwarding audio to {listener_id}: {e}")
                    disconnected_listeners.add(listener_id)
        
        # Clean up disconnected listeners
        for listener_id in disconnected_listeners:
            route.listener_ids.discard(listener_id)
            self.connected_listeners.pop(listener_id, None)
            logger.info(f"Removed disconnected listener: {listener_id}")
    
    async def _handle_ping(self, websocket, data):
        """Handle ping messages for connection health checks."""
        await websocket.send(json.dumps({
            "type": "pong",
            "timestamp": data.get("timestamp")
        }))
    
    async def _cleanup_connection(self, websocket):
        """Clean up when a connection is closed."""
        # Remove from speakers
        for speaker_id, ws in list(self.connected_speakers.items()):
            if ws == websocket:
                del self.connected_speakers[speaker_id]
                if speaker_id in self.audio_routes:
                    self.audio_routes[speaker_id].is_active = False
                logger.info(f"Speaker disconnected: {speaker_id}")
                break
        
        # Remove from listeners
        for listener_id, ws in list(self.connected_listeners.items()):
            if ws == websocket:
                del self.connected_listeners[listener_id]
                # Remove from all routes
                for route in self.audio_routes.values():
                    route.listener_ids.discard(listener_id)
                logger.info(f"Listener disconnected: {listener_id}")
                break
    
    def get_stats(self) -> Dict:
        """Get server statistics."""
        return {
            **self.stats,
            'connected_speakers': len(self.connected_speakers),
            'connected_listeners': len(self.connected_listeners),
            'active_routes': len([r for r in self.audio_routes.values() if r.is_active])
        }
    
    def get_route_info(self) -> Dict:
        """Get detailed route information."""
        routes = {}
        for speaker_id, route in self.audio_routes.items():
            routes[speaker_id] = {
                'speaker_channel_id': route.speaker_channel_id,
                'listener_count': len(route.listener_ids),
                'listener_ids': list(route.listener_ids),
                'is_active': route.is_active
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
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
