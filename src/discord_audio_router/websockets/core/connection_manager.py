"""
Client registry for WebSocket relay server.

This module provides a simple, efficient client registry that manages
speaker-listener relationships with O(1) lookups.
"""

from collections import defaultdict
from typing import Dict, Set, Optional

from websockets.asyncio.server import ServerConnection


class ConnectionManager:
    """Simple and efficient client registry for audio routing."""

    def __init__(self) -> None:
        # Map client_id -> WebSocket protocol
        self.clients: Dict[str, ServerConnection] = {}

        # Map speaker_id -> set of listener_ids
        self.speakers: Dict[str, Set[str]] = defaultdict(set)

        # Map listener_id -> speaker_id
        self.listeners: Dict[str, str] = {}

    def register_speaker(self, speaker_id: str, ws: ServerConnection) -> None:
        """Register a speaker client."""
        self.clients[speaker_id] = ws
        # Ensure entry exists even if no listeners yet
        _ = self.speakers[speaker_id]

    def register_listener(
        self, listener_id: str, speaker_id: str, ws: ServerConnection
    ) -> None:
        """Register a listener client."""
        self.clients[listener_id] = ws
        # Point listener → speaker
        self.listeners[listener_id] = speaker_id
        # Add listener to speaker's set
        self.speakers[speaker_id].add(listener_id)

    def unregister(self, client_id: str) -> None:
        """Unregister a client and clean up all relationships."""
        # Remove from clients map
        self.clients.pop(client_id, None)

        # If client is a speaker, remove all its listener links
        if client_id in self.speakers:
            for lid in self.speakers.pop(client_id):
                self.listeners.pop(lid, None)

        # If client is a listener, remove it from its speaker's set
        elif client_id in self.listeners:
            spk = self.listeners.pop(client_id)
            self.speakers[spk].discard(client_id)

    def get_speaker_listeners(self, speaker_id: str) -> Set[str]:
        """Get all listener IDs for a speaker - O(1) lookup."""
        return self.speakers.get(speaker_id, set())

    def get_listener_speaker(self, listener_id: str) -> Optional[str]:
        """Get speaker ID for a listener - O(1) lookup."""
        return self.listeners.get(listener_id)

    def get_client_websocket(self, client_id: str) -> Optional[ServerConnection]:
        """Get WebSocket for a client - O(1) lookup."""
        return self.clients.get(client_id)

    def is_registered(self, client_id: str) -> bool:
        """Check if client is registered."""
        return client_id in self.clients

    def get_stats(self) -> Dict[str, int]:
        """Get registry statistics."""
        return {
            "total_clients": len(self.clients),
            "speakers": len(self.speakers),
            "listeners": len(self.listeners),
        }
