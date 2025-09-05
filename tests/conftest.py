"""
Pytest configuration and shared fixtures for the Discord Audio Router test suite.

This module provides common fixtures and configuration for all tests.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

import discord
from discord.ext import commands

from src.discord_audio_router.config.settings import SimpleConfig
from src.discord_audio_router.core.audio_router import AudioRouter


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    return SimpleConfig(
        audio_broadcast_token="mock_broadcast_token",
        audio_forwarder_token="mock_forwarder_token",
        audio_receiver_tokens=["mock_receiver_token_1", "mock_receiver_token_2"],
        command_prefix="!",
        log_level="DEBUG",
        speaker_role_name="Speaker",
        broadcast_admin_role_name="Broadcast Admin",
        auto_create_roles=True,
    )


@pytest.fixture
def mock_guild():
    """Create a mock Discord guild for testing."""
    guild = MagicMock(spec=discord.Guild)
    guild.id = 123456789
    guild.name = "Test Guild"
    guild.me = MagicMock(spec=discord.Member)
    guild.me.guild_permissions.manage_channels = True
    guild.me.guild_permissions.manage_roles = True
    guild.me.guild_permissions.administrator = True
    guild.default_role = MagicMock(spec=discord.Role)
    guild.roles = []
    guild.categories = []
    guild.channels = []
    guild.members = []
    return guild


@pytest.fixture
def mock_channel():
    """Create a mock Discord voice channel for testing."""
    channel = MagicMock(spec=discord.VoiceChannel)
    channel.id = 987654321
    channel.name = "Test Channel"
    channel.guild = mock_guild()
    channel.permissions_for = MagicMock()
    return channel


@pytest.fixture
def mock_member():
    """Create a mock Discord member for testing."""
    member = MagicMock(spec=discord.Member)
    member.id = 111222333
    member.display_name = "Test User"
    member.guild_permissions.administrator = False
    member.roles = []
    return member


@pytest.fixture
def mock_context(mock_guild, mock_member):
    """Create a mock Discord command context for testing."""
    context = MagicMock(spec=commands.Context)
    context.guild = mock_guild
    context.author = mock_member
    context.send = AsyncMock()
    context.channel = MagicMock(spec=discord.TextChannel)
    return context


@pytest.fixture
def mock_audio_router(mock_config):
    """Create a mock AudioRouter for testing."""
    router = MagicMock(spec=AudioRouter)
    router.config = mock_config
    router.section_manager = MagicMock()
    router.process_manager = MagicMock()
    router.access_control = MagicMock()
    return router


@pytest.fixture
def mock_voice_client():
    """Create a mock Discord voice client for testing."""
    voice_client = MagicMock()
    voice_client.is_connected.return_value = True
    voice_client.channel = MagicMock(spec=discord.VoiceChannel)
    voice_client.listen = MagicMock()
    return voice_client


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket connection for testing."""
    websocket = MagicMock()
    websocket.remote_address = ("127.0.0.1", 12345)
    websocket.send = AsyncMock()
    websocket.close = AsyncMock()
    return websocket


@pytest.fixture
def mock_audio_buffer():
    """Create a mock audio buffer for testing."""
    buffer = MagicMock()
    buffer.put = AsyncMock()
    buffer.get = AsyncMock()
    buffer.get_sync = MagicMock()
    buffer.clear = AsyncMock()
    buffer.size.return_value = 0
    buffer.is_empty.return_value = True
    buffer.is_full.return_value = False
    return buffer


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "e2e: mark test as an end-to-end test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
