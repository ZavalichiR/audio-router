"""
Unit tests for the AudioRouter core component.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.discord_audio_router.core.audio_router import AudioRouter
from src.discord_audio_router.config.settings import SimpleConfig
from src.discord_audio_router.infrastructure.exceptions import ConfigurationError


class TestAudioRouter:
    """Test cases for AudioRouter class."""

    @pytest.mark.unit
    def test_audio_router_initialization(self, mock_config):
        """Test AudioRouter initialization."""
        router = AudioRouter(mock_config)
        
        assert router.config == mock_config
        assert router.main_bot is None
        assert router.process_manager is not None
        assert router.access_control is not None
        assert router.section_manager is not None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_audio_router_initialize_success(self, mock_config, mock_audio_router):
        """Test successful AudioRouter initialization."""
        router = AudioRouter(mock_config)
        mock_bot = MagicMock()
        
        # Mock the process manager
        router.process_manager.add_available_tokens = MagicMock()
        
        await router.initialize(mock_bot)
        
        assert router.main_bot == mock_bot
        router.process_manager.add_available_tokens.assert_called_once_with(
            mock_config.audio_receiver_tokens
        )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_audio_router_initialize_no_tokens(self, mock_config):
        """Test AudioRouter initialization with no receiver tokens."""
        # Create config without receiver tokens
        config_no_tokens = SimpleConfig(
            audio_broadcast_token="token1",
            audio_forwarder_token="token2",
            audio_receiver_tokens=[],
        )
        
        router = AudioRouter(config_no_tokens)
        mock_bot = MagicMock()
        
        with pytest.raises(ValueError, match="AudioReceiver bot tokens are required"):
            await router.initialize(mock_bot)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_create_broadcast_section(self, mock_config, mock_guild):
        """Test creating a broadcast section."""
        router = AudioRouter(mock_config)
        router.section_manager.create_broadcast_section = AsyncMock(
            return_value={"success": True, "message": "Section created"}
        )
        
        result = await router.create_broadcast_section(mock_guild, "Test Section", 3)
        
        assert result["success"] is True
        router.section_manager.create_broadcast_section.assert_called_once_with(
            mock_guild, "Test Section", 3
        )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_start_broadcast(self, mock_config, mock_guild):
        """Test starting a broadcast."""
        router = AudioRouter(mock_config)
        router.section_manager.start_broadcast = AsyncMock(
            return_value={"success": True, "message": "Broadcast started"}
        )
        
        result = await router.start_broadcast(mock_guild)
        
        assert result["success"] is True
        router.section_manager.start_broadcast.assert_called_once_with(mock_guild)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_stop_broadcast(self, mock_config, mock_guild):
        """Test stopping a broadcast."""
        router = AudioRouter(mock_config)
        router.section_manager.stop_broadcast = AsyncMock(
            return_value={"success": True, "message": "Broadcast stopped"}
        )
        
        result = await router.stop_broadcast(mock_guild)
        
        assert result["success"] is True
        router.section_manager.stop_broadcast.assert_called_once_with(mock_guild)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_system_status(self, mock_config):
        """Test getting system status."""
        router = AudioRouter(mock_config)
        router.section_manager.active_sections = {"guild1": "section1", "guild2": "section2"}
        router.process_manager.get_status = MagicMock(return_value={"total_processes": 5})
        router.process_manager.available_tokens = ["token1", "token2"]
        router.process_manager.used_tokens = {"token3", "token4"}
        
        status = await router.get_system_status()
        
        assert status["active_sections"] == 2
        assert status["process_status"]["total_processes"] == 5
        assert status["available_tokens"] == 2
        assert status["used_tokens"] == 2
