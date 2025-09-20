"""
WebSocket client components for Discord Audio Router.

This module provides unified WebSocket client functionality for both
forwarder and receiver bots with automatic ping management.
"""

from .websocket_client import WebSocketClient

__all__ = ["WebSocketClient"]
