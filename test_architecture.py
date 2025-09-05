#!/usr/bin/env python3
"""
Simple test script for the new Discord Audio Router Bot architecture.

This script verifies that the new architecture components work correctly.
"""

import asyncio
import sys
import os
import logging
from pathlib import Path

# Add the bots directory to the Python path
bots_dir = Path(__file__).parent / "bots"
sys.path.insert(0, str(bots_dir))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


async def test_imports():
    """Test that all modules can be imported."""
    try:
        logger.info("Testing module imports...")
        
        # Test core imports
        from core.process_manager import ProcessManager, BotProcess
        from core.section_manager import SectionManager, BroadcastSection
        from core.audio_router import AudioRouter
        
        # Test config imports
        from config.simple_config import SimpleConfig, SimpleConfigManager
        
        # Test audio handler imports
        from audio_handler import AudioBuffer, OpusAudioSink, OpusAudioSource
        
        logger.info("✅ All imports successful")
        return True
        
    except ImportError as e:
        logger.error(f"❌ Import failed: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        return False


async def test_configuration():
    """Test configuration system."""
    try:
        logger.info("Testing configuration system...")
        
        from config.simple_config import SimpleConfig, SimpleConfigManager
        
        # Test SimpleConfig creation
        config = SimpleConfig(
            main_bot_token="test_token",
            command_prefix="!",
            log_level="INFO",
            listener_bot_tokens=["token1", "token2"]
        )
        
        assert config.main_bot_token == "test_token"
        assert config.command_prefix == "!"
        assert config.log_level == "INFO"
        assert len(config.listener_bot_tokens) == 2
        
        logger.info("✅ Configuration system working")
        return True
        
    except Exception as e:
        logger.error(f"❌ Configuration test failed: {e}")
        return False


async def test_core_components():
    """Test core components."""
    try:
        logger.info("Testing core components...")
        
        from core.process_manager import ProcessManager, BotProcess
        from core.section_manager import SectionManager, BroadcastSection
        from core.audio_router import AudioRouter
        from config.simple_config import SimpleConfig
        
        # Create test config
        config = SimpleConfig(
            main_bot_token="test_token",
            command_prefix="!",
            log_level="INFO",
            listener_bot_tokens=["token1", "token2", "token3"]
        )
        
        # Test ProcessManager
        process_manager = ProcessManager(config)
        process_manager.add_available_tokens(config.listener_bot_tokens)
        
        # Test BotProcess
        speaker_bot = BotProcess("test_speaker", "speaker", "test_token", 123456, 789012)
        listener_bot = BotProcess("test_listener", "listener", "test_token", 111111, 789012)
        
        assert speaker_bot.bot_type == "speaker"
        assert listener_bot.bot_type == "listener"
        
        # Test SectionManager
        section_manager = SectionManager(process_manager)
        
        # Test BroadcastSection
        section = BroadcastSection(
            guild_id=123456789,
            section_name="Test Room",
            speaker_channel_id=987654321,
            listener_channel_ids=[111111111, 222222222]
        )
        
        assert section.guild_id == 123456789
        assert section.section_name == "Test Room"
        assert not section.is_active
        
        # Test AudioRouter
        audio_router = AudioRouter(config)
        
        # Test system status
        status = await audio_router.get_system_status()
        assert 'active_sections' in status
        assert 'process_status' in status
        
        logger.info("✅ Core components working")
        return True
        
    except Exception as e:
        logger.error(f"❌ Core components test failed: {e}")
        return False


async def test_audio_handler():
    """Test audio handler components."""
    try:
        logger.info("Testing audio handler...")
        
        from audio_handler import AudioBuffer, OpusAudioSink, OpusAudioSource
        
        # Test AudioBuffer
        buffer = AudioBuffer(max_size=10)
        assert buffer.max_size == 10
        
        # Test OpusAudioSink
        async def dummy_callback(data):
            pass
        
        sink = OpusAudioSink(dummy_callback)
        assert sink.wants_opus() == True
        
        # Test OpusAudioSource
        source = OpusAudioSource(buffer)
        assert source.is_opus() == True
        
        logger.info("✅ Audio handler working")
        return True
        
    except Exception as e:
        logger.error(f"❌ Audio handler test failed: {e}")
        return False


async def main():
    """Run all tests."""
    logger.info("🚀 Starting architecture tests...")
    
    tests = [
        ("Module Imports", test_imports),
        ("Configuration", test_configuration),
        ("Core Components", test_core_components),
        ("Audio Handler", test_audio_handler),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        logger.info(f"\n📋 Running {test_name} test...")
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"❌ {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info("\n" + "="*50)
    logger.info("📊 TEST SUMMARY")
    logger.info("="*50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{test_name:20} {status}")
        if result:
            passed += 1
    
    logger.info("="*50)
    logger.info(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        logger.info("🎉 All tests passed! The architecture is ready to use.")
        logger.info("\n🚀 Next steps:")
        logger.info("   1. Copy .env.example to .env")
        logger.info("   2. Add your bot token to .env")
        logger.info("   3. Run: python start_bot.py")
        logger.info("   4. In Discord: !start_broadcast 'War Room' 5")
        return True
    else:
        logger.error(f"⚠️ {total - passed} test(s) failed. Please check the issues above.")
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n⏹️ Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"\n💥 Test suite crashed: {e}")
        sys.exit(1)
