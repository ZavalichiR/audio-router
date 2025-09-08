"""
REST API module for Discord Audio Router.

This module provides REST API endpoints for subscription management.
"""

from .app import create_app

__all__ = ["create_app"]
