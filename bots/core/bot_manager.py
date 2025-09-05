"""
Multi-Bot Manager for Discord Audio Router.

This module manages multiple Discord bot instances using separate tokens
for each listener channel, allowing true multi-channel audio.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Set
import discord
from discord.ext import commands, voice_recv

from audio_handler import setup_audio_receiver, OpusAudioSource, AudioBuffer

logger = logging.getLogger(__name__)


class ListenerBotInstance:
    """Represents a listener bot instance."""
    
    def __init__(self, token: str, channel_id: int, bot_id: str):
        """
        Initialize a listener bot instance.
        
        Args:
            token: Discord bot token
            channel_id: Target listener channel ID
            bot_id: Unique bot identifier
        """
        self.token = token
        self.channel_id = channel_id
        self.bot_id = bot_id
        self.bot: Optional[commands.Bot] = None
        self.voice_client: Optional[voice_recv.VoiceRecvClient] = None
        self.audio_buffer: Optional[AudioBuffer] = None
        self.is_connected = False
        self.is_playing = False
        self.start_task: Optional[asyncio.Task] = None
        
    async def start(self) -> bool:
        """Start the listener bot instance."""
        try:
            logger.info(f"Starting listener bot {self.bot_id} for channel {self.channel_id}...")
            
            intents = discord.Intents.default()
            intents.voice_states = True
            intents.guilds = True
            
            self.bot = commands.Bot(
                command_prefix='!',
                intents=intents,
                help_command=None
            )
            
            @self.bot.event
            async def on_ready():
                logger.info(f"Listener bot {self.bot_id} ready: {self.bot.user}")
                self.is_connected = True
            
            @self.bot.event
            async def on_connect():
                logger.debug(f"Listener bot {self.bot_id} connected to Discord")
            
            @self.bot.event
            async def on_disconnect():
                logger.warning(f"Listener bot {self.bot_id} disconnected from Discord")
                self.is_connected = False
            
            # Start the bot in a separate task
            self.start_task = asyncio.create_task(self.bot.start(self.token))
            
            # Wait for the bot to be ready
            timeout = 10.0
            start_time = asyncio.get_event_loop().time()
            while not self.is_connected:
                if asyncio.get_event_loop().time() - start_time > timeout:
                    logger.error(f"Listener bot {self.bot_id} startup timed out")
                    return False
                await asyncio.sleep(0.1)
            
            logger.info(f"Listener bot {self.bot_id} started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start listener bot {self.bot_id}: {e}")
            self.is_connected = False
            return False
    
    async def connect_to_channel(self, guild: discord.Guild) -> bool:
        """Connect to the assigned listener channel."""
        try:
            if not self.bot or not self.is_connected:
                logger.error(f"Listener bot {self.bot_id} not ready")
                return False
            
            channel = guild.get_channel(self.channel_id)
            if not channel:
                logger.error(f"Channel {self.channel_id} not found for bot {self.bot_id}")
                return False
            
            # Connect to voice channel
            self.voice_client = await channel.connect(cls=voice_recv.VoiceRecvClient)
            
            # Create audio buffer
            self.audio_buffer = AudioBuffer()
            
            # Start playing audio from buffer
            audio_source = OpusAudioSource(self.audio_buffer)
            self.voice_client.play(audio_source)
            self.is_playing = True
            
            logger.info(f"Listener bot {self.bot_id} connected to channel {channel.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect listener bot {self.bot_id} to channel: {e}")
            return False
    
    async def stop(self):
        """Stop the listener bot instance."""
        try:
            if self.voice_client:
                await self.voice_client.disconnect()
                self.voice_client = None
            
            if self.bot:
                await self.bot.close()
                self.bot = None
            
            if self.start_task and not self.start_task.done():
                self.start_task.cancel()
                try:
                    await self.start_task
                except asyncio.CancelledError:
                    pass
            
            self.is_connected = False
            self.is_playing = False
            
            logger.info(f"Listener bot {self.bot_id} stopped")
            
        except Exception as e:
            logger.error(f"Error stopping listener bot {self.bot_id}: {e}")


class MultiBotManager:
    """
    Manages multiple Discord bot instances for true multi-channel audio.
    
    This manager uses separate bot tokens for each listener channel,
    allowing simultaneous audio in multiple channels.
    """
    
    def __init__(self, config):
        """
        Initialize the multi-bot manager.
        
        Args:
            config: Bot configuration
        """
        self.config = config
        self.main_bot: Optional[commands.Bot] = None
        self.speaker_voice_client: Optional[voice_recv.VoiceRecvClient] = None
        self.listener_bots: Dict[str, ListenerBotInstance] = {}  # bot_id -> bot_instance
        self.available_tokens: List[str] = []
        self.used_tokens: Set[str] = set()
        
    def set_main_bot(self, main_bot: commands.Bot):
        """Set the main bot reference."""
        self.main_bot = main_bot
    
    def add_available_tokens(self, tokens: List[str]):
        """Add available listener bot tokens."""
        self.available_tokens.extend(tokens)
        logger.info(f"Added {len(tokens)} available listener bot tokens")
    
    async def connect_to_speaker_channel(self, channel_id: int, guild: discord.Guild) -> bool:
        """
        Connect main bot to speaker channel and start audio capture.
        
        Args:
            channel_id: Speaker channel ID
            guild: Discord guild
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.main_bot:
                logger.error("Main bot reference not available")
                return False
            
            channel = guild.get_channel(channel_id)
            if not channel:
                logger.error(f"Speaker channel {channel_id} not found")
                return False
            
            # Connect to speaker channel
            self.speaker_voice_client = await channel.connect(cls=voice_recv.VoiceRecvClient)
            
            # Set up audio capture
            audio_sink = await setup_audio_receiver(
                self.speaker_voice_client,
                lambda audio_data: self._handle_speaker_audio(audio_data)
            )
            
            logger.info(f"Main bot connected to speaker channel: {channel.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to speaker channel: {e}")
            return False
    
    async def setup_listener_channels(self, channel_ids: List[int], guild: discord.Guild) -> Dict[int, bool]:
        """
        Set up listener channels using separate bot instances.
        
        Args:
            channel_ids: List of listener channel IDs
            guild: Discord guild
            
        Returns:
            Dict mapping channel_id to success status
        """
        results = {}
        
        # Check if we have enough tokens
        if len(self.available_tokens) < len(channel_ids):
            logger.warning(f"Not enough listener bot tokens! Need {len(channel_ids)}, have {len(self.available_tokens)}")
            logger.warning("Some listener channels will not have audio")
        
        # Assign tokens to channels
        for i, channel_id in enumerate(channel_ids):
            try:
                channel = guild.get_channel(channel_id)
                if not channel:
                    logger.error(f"Listener channel {channel_id} not found")
                    results[channel_id] = False
                    continue
                
                if i >= len(self.available_tokens):
                    logger.warning(f"No token available for listener channel {channel.name}")
                    results[channel_id] = False
                    continue
                
                # Get token for this channel
                token = self.available_tokens[i]
                bot_id = f"listener_bot_{i+1}"
                
                # Create listener bot instance
                listener_bot = ListenerBotInstance(token, channel_id, bot_id)
                
                # Start the bot
                if await listener_bot.start():
                    # Connect to channel
                    if await listener_bot.connect_to_channel(guild):
                        self.listener_bots[bot_id] = listener_bot
                        self.used_tokens.add(token)
                        results[channel_id] = True
                        logger.info(f"Successfully set up listener bot for channel: {channel.name}")
                    else:
                        await listener_bot.stop()
                        results[channel_id] = False
                else:
                    results[channel_id] = False
                
            except Exception as e:
                logger.error(f"Failed to set up listener channel {channel_id}: {e}")
                results[channel_id] = False
        
        return results
    
    async def _handle_speaker_audio(self, audio_data: bytes):
        """Handle audio data from speaker channel."""
        # Forward audio to all listener bots
        for bot_id, listener_bot in self.listener_bots.items():
            if listener_bot.audio_buffer:
                try:
                    await listener_bot.audio_buffer.put(audio_data)
                    logger.debug(f"Forwarded audio to listener bot {bot_id}")
                except Exception as e:
                    logger.error(f"Failed to forward audio to listener bot {bot_id}: {e}")
    
    async def disconnect(self):
        """Disconnect from all voice channels and stop all bots."""
        try:
            # Disconnect from speaker channel
            if self.speaker_voice_client:
                await self.speaker_voice_client.disconnect()
                self.speaker_voice_client = None
            
            # Stop all listener bots
            for bot_id, listener_bot in self.listener_bots.items():
                await listener_bot.stop()
            
            self.listener_bots.clear()
            self.used_tokens.clear()
            
            logger.info("Disconnected from all voice channels and stopped all bots")
            
        except Exception as e:
            logger.error(f"Error disconnecting: {e}")
    
    def get_status(self) -> Dict:
        """Get current status."""
        return {
            'speaker_connected': self.speaker_voice_client is not None,
            'listener_bots': len(self.listener_bots),
            'available_tokens': len(self.available_tokens),
            'used_tokens': len(self.used_tokens),
            'listener_channels': [bot.channel_id for bot in self.listener_bots.values()]
        }
