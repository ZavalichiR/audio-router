#!/usr/bin/env python3
"""
Comprehensive architecture tests for the Discord Audio Router.

This test suite verifies that the new modular architecture works correctly
and all components can be imported, instantiated, and function as expected.
"""

import asyncio
import sys
import os
import logging
import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock, MagicMock

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


class TestArchitectureImports:
    """Test that all modules can be imported correctly."""
    
    def test_main_package_import(self):
        """Test that the main package can be imported."""
        import discord_audio_router
        assert hasattr(discord_audio_router, '__version__')
        assert hasattr(discord_audio_router, '__author__')
    
    def test_core_imports(self):
        """Test core module imports."""
        from discord_audio_router.core import AudioRouter, SectionManager, ProcessManager, AccessControl
        from discord_audio_router.core.audio_router import AudioRouter as AudioRouterClass
        from discord_audio_router.core.section_manager import SectionManager as SectionManagerClass
        from discord_audio_router.core.process_manager import ProcessManager as ProcessManagerClass
        from discord_audio_router.core.access_control import AccessControl as AccessControlClass
        
        assert AudioRouter == AudioRouterClass
        assert SectionManager == SectionManagerClass
        assert ProcessManager == ProcessManagerClass
        assert AccessControl == AccessControlClass
    
    def test_audio_imports(self):
        """Test audio module imports."""
        from discord_audio_router.audio import AudioBuffer, OpusAudioSink, OpusAudioSource, setup_audio_receiver, SilentSource
        from discord_audio_router.audio.buffers import AudioBuffer as AudioBufferClass
        from discord_audio_router.audio.handlers import OpusAudioSink as OpusAudioSinkClass, OpusAudioSource as OpusAudioSourceClass
        from discord_audio_router.audio.sources import SilentSource as SilentSourceClass
        
        assert AudioBuffer == AudioBufferClass
        assert OpusAudioSink == OpusAudioSinkClass
        assert OpusAudioSource == OpusAudioSourceClass
        assert SilentSource == SilentSourceClass
    
    def test_networking_imports(self):
        """Test networking module imports."""
        from discord_audio_router.networking import AudioRelayServer, AudioRoute
        from discord_audio_router.networking.websocket_server import AudioRelayServer as AudioRelayServerClass, AudioRoute as AudioRouteClass
        
        assert AudioRelayServer == AudioRelayServerClass
        assert AudioRoute == AudioRouteClass
    
    def test_config_imports(self):
        """Test configuration module imports."""
        from discord_audio_router.config import SimpleConfig, SimpleConfigManager
        from discord_audio_router.config.settings import SimpleConfig as SimpleConfigClass, SimpleConfigManager as SimpleConfigManagerClass
        
        assert SimpleConfig == SimpleConfigClass
        assert SimpleConfigManager == SimpleConfigManagerClass
    
    def test_infrastructure_imports(self):
        """Test infrastructure module imports."""
        from discord_audio_router.infrastructure import setup_logging, get_logger, AudioRouterError
        from discord_audio_router.infrastructure.logging import setup_logging as setup_logging_func, get_logger as get_logger_func
        from discord_audio_router.infrastructure.exceptions import AudioRouterError as AudioRouterErrorClass
        
        assert setup_logging == setup_logging_func
        assert get_logger == get_logger_func
        assert AudioRouterError == AudioRouterErrorClass
    
    
    def test_bots_imports(self):
        """Test bot module imports."""
        from discord_audio_router.bots import AudioForwarderBot, AudioReceiverBot
        from discord_audio_router.bots.forwarder_bot import AudioForwarderBot as AudioForwarderBotClass
        from discord_audio_router.bots.receiver_bot import AudioReceiverBot as AudioReceiverBotClass
        
        assert AudioForwarderBot == AudioForwarderBotClass
        assert AudioReceiverBot == AudioReceiverBotClass


class TestConfigurationSystem:
    """Test the configuration system."""
    
    def test_simple_config_creation(self):
        """Test SimpleConfig creation and validation."""
        from discord_audio_router.config.settings import SimpleConfig
        
        config = SimpleConfig(
            audio_broadcast_token="test_broadcast_token",
            audio_forwarder_token="test_forwarder_token",
            audio_receiver_tokens=["token1", "token2", "token3"]
        )
        
        assert config.audio_broadcast_token == "test_broadcast_token"
        assert config.audio_forwarder_token == "test_forwarder_token"
        assert config.audio_receiver_tokens == ["token1", "token2", "token3"]
        assert config.command_prefix == "!"  # default value
        assert config.log_level == "INFO"    # default value
    
    def test_simple_config_defaults(self):
        """Test SimpleConfig default values."""
        from discord_audio_router.config.settings import SimpleConfig
        
        config = SimpleConfig(
            audio_broadcast_token="test_broadcast_token",
            audio_forwarder_token="test_forwarder_token",
            audio_receiver_tokens=[]
        )
        
        assert config.command_prefix == "!"
        assert config.log_level == "INFO"
        assert config.speaker_role_name == "Speaker"
        assert config.broadcast_admin_role_name == "Broadcast Admin"
        assert config.auto_create_roles == True
    
    def test_config_manager(self):
        """Test SimpleConfigManager functionality."""
        from discord_audio_router.config.settings import SimpleConfigManager
        
        # Mock environment variables
        with pytest.MonkeyPatch().context() as m:
            m.setenv("AUDIO_BROADCAST_TOKEN", "test_broadcast_token")
            m.setenv("AUDIO_FORWARDER_TOKEN", "test_forwarder_token")
            m.setenv("AUDIO_RECEIVER_TOKENS", "token1,token2,token3")
            
            manager = SimpleConfigManager()
            config = manager.get_config()
            
            assert config.audio_broadcast_token == "test_broadcast_token"
            assert config.audio_forwarder_token == "test_forwarder_token"
            assert config.audio_receiver_tokens == ["token1", "token2", "token3"]


class TestCoreComponents:
    """Test core business logic components."""
    
    def test_audio_router_creation(self):
        """Test AudioRouter instantiation."""
        from discord_audio_router.core.audio_router import AudioRouter
        from discord_audio_router.config.settings import SimpleConfig
        
        config = SimpleConfig(
            audio_broadcast_token="test_broadcast_token",
            audio_forwarder_token="test_forwarder_token",
            audio_receiver_tokens=["token1", "token2"]
        )
        
        router = AudioRouter(config)
        
        assert router.config == config
        assert router.process_manager is not None
        assert router.access_control is not None
        assert router.section_manager is not None
        assert router.main_bot is None  # Not initialized yet
    
    @pytest.mark.asyncio
    async def test_audio_router_initialization(self):
        """Test AudioRouter initialization with mock bot."""
        from discord_audio_router.core.audio_router import AudioRouter
        from discord_audio_router.config.settings import SimpleConfig
        
        config = SimpleConfig(
            audio_broadcast_token="test_broadcast_token",
            audio_forwarder_token="test_forwarder_token",
            audio_receiver_tokens=["token1", "token2"]
        )
        
        router = AudioRouter(config)
        mock_bot = Mock()
        
        await router.initialize(mock_bot)
        
        assert router.main_bot == mock_bot
    
    @pytest.mark.asyncio
    async def test_audio_router_system_status(self):
        """Test AudioRouter system status."""
        from discord_audio_router.core.audio_router import AudioRouter
        from discord_audio_router.config.settings import SimpleConfig
        
        config = SimpleConfig(
            audio_broadcast_token="test_broadcast_token",
            audio_forwarder_token="test_forwarder_token",
            audio_receiver_tokens=["token1", "token2"]
        )
        
        router = AudioRouter(config)
        status = await router.get_system_status()
        
        assert isinstance(status, dict)
        assert 'active_sections' in status
        assert 'process_status' in status
        assert 'available_tokens' in status
        assert 'used_tokens' in status
    
    def test_process_manager_creation(self):
        """Test ProcessManager instantiation."""
        from discord_audio_router.core.process_manager import ProcessManager, BotProcess
        from discord_audio_router.config.settings import SimpleConfig
        
        config = SimpleConfig(
            audio_broadcast_token="test_broadcast_token",
            audio_forwarder_token="test_forwarder_token",
            audio_receiver_tokens=["token1", "token2"]
        )
        
        manager = ProcessManager(config)
        
        assert manager.config == config
        assert manager.available_tokens == []
        assert manager.used_tokens == set()
        assert manager.bot_processes == {}
    
    def test_bot_process_creation(self):
        """Test BotProcess instantiation."""
        from discord_audio_router.core.process_manager import BotProcess
        
        bot_process = BotProcess(
            bot_id="test_bot",
            bot_type="listener",
            token="test_token",
            channel_id=123456,
            guild_id=789012
        )
        
        assert bot_process.bot_id == "test_bot"
        assert bot_process.bot_type == "listener"
        assert bot_process.token == "test_token"
        assert bot_process.channel_id == 123456
        assert bot_process.guild_id == 789012
        assert bot_process.process is None
        assert not bot_process.is_running
    
    def test_section_manager_creation(self):
        """Test SectionManager instantiation."""
        from discord_audio_router.core.section_manager import SectionManager, BroadcastSection
        from discord_audio_router.core.process_manager import ProcessManager
        from discord_audio_router.config.settings import SimpleConfig
        
        config = SimpleConfig(
            audio_broadcast_token="test_broadcast_token",
            audio_forwarder_token="test_forwarder_token",
            audio_receiver_tokens=["token1", "token2"]
        )
        
        process_manager = ProcessManager(config)
        section_manager = SectionManager(process_manager)
        
        assert section_manager.process_manager == process_manager
        assert section_manager.active_sections == {}
    
    def test_broadcast_section_creation(self):
        """Test BroadcastSection instantiation."""
        from discord_audio_router.core.section_manager import BroadcastSection
        
        section = BroadcastSection(
            guild_id=123456789,
            section_name="Test Room",
            speaker_channel_id=987654321,
            listener_channel_ids=[111111111, 222222222]
        )
        
        assert section.guild_id == 123456789
        assert section.section_name == "Test Room"
        assert section.speaker_channel_id == 987654321
        assert section.listener_channel_ids == [111111111, 222222222]
        assert not section.is_active
    
    def test_access_control_creation(self):
        """Test AccessControl instantiation."""
        from discord_audio_router.core.access_control import AccessControl
        from discord_audio_router.config.settings import SimpleConfig
        
        config = SimpleConfig(
            audio_broadcast_token="test_broadcast_token",
            audio_forwarder_token="test_forwarder_token",
            audio_receiver_tokens=["token1", "token2"]
        )
        
        access_control = AccessControl(config)
        
        assert access_control.config == config
        assert access_control.speaker_role_name == "Speaker"
        assert access_control.broadcast_admin_role_name == "Broadcast Admin"
        assert access_control.auto_create_roles == True


class TestAudioComponents:
    """Test audio processing components."""
    
    def test_audio_buffer_creation(self):
        """Test AudioBuffer instantiation."""
        from discord_audio_router.audio.buffers import AudioBuffer
        
        buffer = AudioBuffer(max_size=100)
        
        assert buffer.max_size == 100
        assert hasattr(buffer, '_async_buffer')
        assert hasattr(buffer, '_sync_queue')
    
    @pytest.mark.asyncio
    async def test_audio_buffer_operations(self):
        """Test AudioBuffer operations."""
        from discord_audio_router.audio.buffers import AudioBuffer
        
        buffer = AudioBuffer(max_size=3)
        
        # Test async operations
        await buffer.put(b"packet1")
        await buffer.put(b"packet2")
        await buffer.put(b"packet3")
        
        assert len(buffer._async_buffer) == 3
        
        # Test getting packets
        packet1 = await buffer.get()
        packet2 = await buffer.get()
        assert packet1 == b"packet1"
        assert packet2 == b"packet2"
    
    @pytest.mark.asyncio
    async def test_opus_audio_sink_creation(self):
        """Test OpusAudioSink instantiation."""
        from discord_audio_router.audio.handlers import OpusAudioSink
        
        async def dummy_callback(data):
            pass
        
        sink = OpusAudioSink(dummy_callback)
        
        assert sink.audio_callback_func == dummy_callback
        assert sink.wants_opus() == True
        assert not sink._is_active
    
    def test_opus_audio_source_creation(self):
        """Test OpusAudioSource instantiation."""
        from discord_audio_router.audio.handlers import OpusAudioSource
        from discord_audio_router.audio.buffers import AudioBuffer
        
        buffer = AudioBuffer()
        source = OpusAudioSource(buffer)
        
        assert hasattr(source, 'audio_buffer')
        assert source.is_opus() == True
    
    def test_silent_source_creation(self):
        """Test SilentSource instantiation."""
        from discord_audio_router.audio.sources import SilentSource
        
        source = SilentSource()
        
        assert source.is_opus() == True
        assert source.frame_count == 0


class TestNetworkingComponents:
    """Test networking components."""
    
    def test_audio_relay_server_creation(self):
        """Test AudioRelayServer instantiation."""
        from discord_audio_router.networking.websocket_server import AudioRelayServer
        
        server = AudioRelayServer()
        
        assert hasattr(server, 'audio_routes')
        assert server.server is None
    
    def test_audio_route_creation(self):
        """Test AudioRoute instantiation."""
        from discord_audio_router.networking.websocket_server import AudioRoute
        
        route = AudioRoute(
            speaker_id="test_speaker",
            speaker_channel_id=123456,
            listener_ids={111111, 222222}
        )
        
        assert route.speaker_id == "test_speaker"
        assert route.speaker_channel_id == 123456
        assert route.listener_ids == {111111, 222222}
        assert route.is_active


class TestInfrastructureComponents:
    """Test infrastructure components."""
    
    def test_logging_setup(self):
        """Test logging setup function."""
        from discord_audio_router.infrastructure.logging import setup_logging
        
        logger = setup_logging("test_component", "test.log")
        
        assert logger.name == "test_component"
        assert logger.level <= logging.INFO
    
    def test_custom_exceptions(self):
        """Test custom exception classes."""
        from discord_audio_router.infrastructure.exceptions import (
            AudioRouterError,
            ConfigurationError,
            BotProcessError,
            AudioProcessingError,
            NetworkError
        )
        
        # Test that exceptions can be raised and caught
        try:
            raise ConfigurationError("Test error")
        except AudioRouterError as e:
            assert str(e) == "Test error"
        
        try:
            raise BotProcessError("Bot error")
        except AudioRouterError as e:
            assert str(e) == "Bot error"
        
        try:
            raise AudioProcessingError("Audio error")
        except AudioRouterError as e:
            assert str(e) == "Audio error"
        
        try:
            raise NetworkError("Network error")
        except AudioRouterError as e:
            assert str(e) == "Network error"


class TestBotComponents:
    """Test bot implementation components."""
    
    def test_audio_forwarder_bot_creation(self):
        """Test AudioForwarderBot instantiation."""
        from discord_audio_router.bots.forwarder_bot import AudioForwarderBot
        
        # Mock environment variables
        with pytest.MonkeyPatch().context() as m:
            m.setenv("BOT_TOKEN", "test_token")
            m.setenv("CHANNEL_ID", "123456")
            m.setenv("GUILD_ID", "789012")
            
            bot = AudioForwarderBot()
            
            assert bot.bot_token == "test_token"
            assert bot.channel_id == 123456
            assert bot.guild_id == 789012
    
    def test_audio_receiver_bot_creation(self):
        """Test AudioReceiverBot instantiation."""
        from discord_audio_router.bots.receiver_bot import AudioReceiverBot
        
        # Mock environment variables
        with pytest.MonkeyPatch().context() as m:
            m.setenv("BOT_TOKEN", "test_token")
            m.setenv("CHANNEL_ID", "123456")
            m.setenv("GUILD_ID", "789012")
            m.setenv("SPEAKER_CHANNEL_ID", "111111")
            
            bot = AudioReceiverBot()
            
            assert bot.bot_token == "test_token"
            assert bot.channel_id == 123456
            assert bot.guild_id == 789012




class TestIntegration:
    """Test integration between components."""
    
    def test_full_system_initialization(self):
        """Test that all components can be initialized together."""
        from discord_audio_router.config.settings import SimpleConfig
        from discord_audio_router.core.audio_router import AudioRouter
        from discord_audio_router.audio.buffers import AudioBuffer
        from discord_audio_router.networking.websocket_server import AudioRelayServer
        
        # Create configuration
        config = SimpleConfig(
            audio_broadcast_token="test_broadcast_token",
            audio_forwarder_token="test_forwarder_token",
            audio_receiver_tokens=["token1", "token2"]
        )
        
        # Initialize core components
        audio_router = AudioRouter(config)
        audio_buffer = AudioBuffer()
        relay_server = AudioRelayServer()
        
        # Verify all components are properly initialized
        assert audio_router.config == config
        assert audio_buffer.max_size == 100  # default
        assert hasattr(relay_server, 'audio_routes')
    
    @pytest.mark.asyncio
    async def test_audio_flow_simulation(self):
        """Test simulated audio flow between components."""
        from discord_audio_router.audio.buffers import AudioBuffer
        from discord_audio_router.audio.handlers import OpusAudioSource
        
        # Create components
        buffer = AudioBuffer(max_size=10)
        source = OpusAudioSource(buffer)
        
        # Simulate audio data flow
        test_data = b"test_audio_data"
        await buffer.put(test_data)
        
        # Verify data is in buffer
        assert len(buffer._async_buffer) == 1
        assert buffer._async_buffer[0] == test_data
        
        # Test getting data from buffer
        packet = await buffer.get()
        assert packet == test_data


def run_architecture_tests():
    """Run all architecture tests and return results."""
    logger.info("🚀 Starting comprehensive architecture tests...")
    
    # Run pytest tests
    test_classes = [
        TestArchitectureImports,
        TestConfigurationSystem,
        TestCoreComponents,
        TestAudioComponents,
        TestNetworkingComponents,
        TestInfrastructureComponents,
        TestBotComponents,
        TestIntegration
    ]
    
    results = []
    
    for test_class in test_classes:
        class_name = test_class.__name__
        logger.info(f"\n📋 Running {class_name}...")
        
        try:
            # Create test instance and run all test methods
            test_instance = test_class()
            test_methods = [method for method in dir(test_instance) if method.startswith('test_')]
            
            class_passed = 0
            class_total = len(test_methods)
            
            for method_name in test_methods:
                try:
                    method = getattr(test_instance, method_name)
                    if asyncio.iscoroutinefunction(method):
                        asyncio.run(method())
                    else:
                        method()
                    class_passed += 1
                    logger.info(f"  ✅ {method_name}")
                except Exception as e:
                    logger.error(f"  ❌ {method_name}: {e}")
            
            results.append((class_name, class_passed, class_total))
            
        except Exception as e:
            logger.error(f"❌ {class_name} failed: {e}")
            results.append((class_name, 0, 1))
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("📊 ARCHITECTURE TEST SUMMARY")
    logger.info("="*60)
    
    total_passed = 0
    total_tests = 0
    
    for class_name, passed, total in results:
        status = "✅ PASSED" if passed == total else "❌ FAILED"
        logger.info(f"{class_name:30} {passed:2}/{total:2} {status}")
        total_passed += passed
        total_tests += total
    
    logger.info("="*60)
    logger.info(f"Total tests: {total_passed}/{total_tests}")
    
    if total_passed == total_tests:
        logger.info("🎉 All architecture tests passed!")
        logger.info("✨ The new modular architecture is working perfectly!")
        return True
    else:
        logger.error(f"⚠️ {total_tests - total_passed} test(s) failed.")
        return False


if __name__ == "__main__":
    try:
        success = run_architecture_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n⏹️ Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"\n💥 Test suite crashed: {e}")
        sys.exit(1)