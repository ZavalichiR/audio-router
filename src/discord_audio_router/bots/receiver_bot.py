# receiver_bot.py
#!/usr/bin/env python3
"""
AudioReceiver Bot Process for Discord Audio Router.

This implementation provides significant latency and performance improvements
through binary WebSocket protocol and buffering.
"""

import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Optional

# Add src directory to Python path for direct execution
if __name__ == "__main__":
    src_path = Path(__file__).parent.parent.parent.parent / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

import discord
import websockets
import websockets.exceptions
from discord.ext import commands, voice_recv

from discord_audio_router.audio import AudioBuffer, OpusAudioSource
from discord_audio_router.audio.handlers import BinaryAudioMessage
from discord_audio_router.infrastructure import setup_logging

# Configure logging
logger = setup_logging(
    component_name="audioreceiver_bot",
    log_file="logs/audioreceiver_bot.log",
)


class AudioReceiverBot:
    """Audio receiver bot with binary protocol and performance improvements."""

    def __init__(self):
        """Initialize the audio receiver bot."""
        # Get configuration from environment
        self.bot_token = os.getenv("BOT_TOKEN")
        self.bot_id = os.getenv("BOT_ID", "audioreceiver_bot")
        self.bot_type = os.getenv("BOT_TYPE", "listener")
        self.channel_id = int(os.getenv("CHANNEL_ID", "0"))
        self.guild_id = int(os.getenv("GUILD_ID", "0"))
        self.speaker_channel_id = int(os.getenv("SPEAKER_CHANNEL_ID", "0"))

        # Log configuration for debugging
        logger.info("AudioReceiver bot configuration:")
        logger.info(f"  Bot ID: {self.bot_id}")
        logger.info(f"  Channel ID: {self.channel_id}")
        logger.info(f"  Guild ID: {self.guild_id}")
        logger.info(f"  Speaker Channel ID: {self.speaker_channel_id}")

        if not self.bot_token:
            raise ValueError("BOT_TOKEN environment variable is required")

        if not self.channel_id:
            raise ValueError("CHANNEL_ID environment variable is required")

        if not self.speaker_channel_id:
            raise ValueError(
                "SPEAKER_CHANNEL_ID environment variable is required"
            )

        # Bot setup
        intents = discord.Intents.default()
        intents.voice_states = True
        intents.guilds = True

        self.bot = commands.Bot(
            command_prefix="!", intents=intents, help_command=None
        )

        # Audio handling
        self.voice_client: Optional[voice_recv.VoiceRecvClient] = None
        self.audio_buffer: Optional[AudioBuffer] = None
        self.audio_source: Optional[OpusAudioSource] = None
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.speaker_websocket_url: Optional[str] = None
        self._reconnecting = False

        # Performance tracking
        self._audio_packets_received = 0
        self._bytes_received = 0
        self._start_time = time.time()
        self._last_stats_time = time.time()
        self._binary_protocol_enabled = False

        # Setup bot events
        self._setup_events()

    def _setup_events(self):
        """Setup bot event handlers."""

        @self.bot.event
        async def on_ready():
            logger.info(
                f"AudioReceiver bot {self.bot_id} ready: {self.bot.user}"
            )
            logger.info(
                f"Target channel: {self.channel_id}, Guild: {self.guild_id}"
            )

            # Connect to the listener channel with retry
            await self._connect_to_channel_with_retry()

            # Connect to AudioForwarder bot WebSocket
            await self._connect_to_speaker()

        @self.bot.event
        async def on_connect():
            logger.info(
                f"AudioReceiver bot {self.bot_id} connected to Discord"
            )

        @self.bot.event
        async def on_disconnect():
            logger.warning(
                f"AudioReceiver bot {self.bot_id} disconnected from Discord"
            )

    async def _connect_to_speaker(self):
        """Connect to the AudioForwarder bot's WebSocket server with binary protocol support."""
        try:
            if not self.speaker_channel_id:
                logger.error(
                    "No speaker channel ID provided - cannot connect to AudioForwarder bot"
                )
                return

            logger.info(
                f"Attempting to connect to AudioForwarder bot for channel {self.speaker_channel_id}"
            )

            # Calculate the same port that the AudioForwarder bot uses
            speaker_port = 8000 + (self.speaker_channel_id % 1000)
            self.speaker_websocket_url = f"ws://localhost:{speaker_port}"

            logger.info(
                f"Connecting to AudioForwarder WebSocket: {self.speaker_websocket_url} (speaker_channel_id: {self.speaker_channel_id})"
            )

            # Add retry logic with exponential backoff
            max_retries = 5
            retry_delay = 1.0

            for attempt in range(max_retries):
                try:
                    # Connect to AudioForwarder bot with connection settings
                    self.websocket = await websockets.connect(
                        self.speaker_websocket_url,
                        ping_interval=None,  # Disable automatic pings
                        ping_timeout=None,  # Disable ping timeout
                        close_timeout=10,  # Shorter close timeout
                        max_size=2**20,  # 1MB max message size
                        compression=None,  # Disable compression for lower latency
                    )

                    # Start listening for audio data
                    asyncio.create_task(self._listen_for_audio())

                    # Start ping task to keep connection alive
                    asyncio.create_task(self._ping_speaker())

                    # Start performance monitoring
                    asyncio.create_task(self._monitor_performance())

                    logger.info(
                        f"Connected to AudioForwarder bot WebSocket on attempt {attempt + 1}"
                    )
                    return  # Success, exit the retry loop

                except ConnectionRefusedError as e:
                    logger.warning(
                        f"Connection refused on attempt {attempt + 1}/{max_retries}: {e}"
                    )
                    if attempt < max_retries - 1:
                        logger.info(f"Retrying in {retry_delay} seconds...")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        logger.error("Max retries reached, giving up")
                        raise
                except Exception as e:
                    logger.error(
                        f"Unexpected error on attempt {attempt + 1}: {e}"
                    )
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2
                    else:
                        raise

        except Exception as e:
            logger.error(
                f"Failed to connect to AudioForwarder WebSocket after all retries: {e}"
            )
            # Retry connection after a delay
            asyncio.create_task(self._retry_speaker_connection())

    async def _retry_speaker_connection(self):
        """Retry connection to AudioForwarder bot."""
        retry_delay = 5.0
        max_retries = 10
        retry_count = 0

        while retry_count < max_retries:
            try:
                await asyncio.sleep(retry_delay)
                await self._connect_to_speaker()
                return
            except Exception as e:
                retry_count += 1
                logger.warning(
                    f"Retry {retry_count}/{max_retries} failed: {e}"
                )
                retry_delay = min(
                    retry_delay * 1.5, 30.0
                )  # Exponential backoff

        logger.error(
            "Failed to connect to AudioForwarder bot after maximum retries"
        )

    async def _ping_speaker(self):
        """Send periodic pings to keep the WebSocket connection alive."""
        while True:
            try:
                await asyncio.sleep(15)  # Ping every 15 seconds

                if self.websocket and not getattr(self.websocket, 'closed', True):
                    try:
                        await self.websocket.send('{"type": "ping"}')
                        logger.debug("Sent ping to AudioForwarder")
                    except websockets.exceptions.ConnectionClosed:
                        logger.debug("Connection closed while sending ping")
                        break
                    except Exception as e:
                        logger.error(f"Error sending ping: {e}", exc_info=True)
                        break
                else:
                    logger.debug("WebSocket not available for ping")
                    break

            except Exception as e:
                logger.error(f"Error in ping task: {e}", exc_info=True)
                break

    async def _connect_to_channel_with_retry(self):
        """Connect to voice channel with retry logic."""
        max_retries = 5
        retry_delay = 2.0

        for attempt in range(max_retries):
            try:
                success = await self.connect_to_channel()
                if success:
                    logger.info(
                        f"Successfully connected to voice channel on attempt {attempt + 1}"
                    )
                    return
                else:
                    logger.warning(
                        f"Failed to connect to voice channel on attempt {attempt + 1}"
                    )
            except Exception as e:
                logger.warning(
                    f"Exception connecting to voice channel on attempt {attempt + 1}: {e}"
                )

            if attempt < max_retries - 1:
                logger.info(
                    f"Retrying voice channel connection in {retry_delay} seconds..."
                )
                await asyncio.sleep(retry_delay)
                retry_delay *= 1.5  # Exponential backoff

        logger.error("Failed to connect to voice channel after all retries")

    async def _listen_for_audio(self):
        """Listen for audio data from the AudioForwarder bot with binary protocol support."""
        while True:
            try:
                async for message in self.websocket:
                    try:
                        # Check if message is binary (audio data) or text (control)
                        if isinstance(message, bytes):
                            # Binary audio message
                            if self._binary_protocol_enabled:
                                try:
                                    audio_msg = BinaryAudioMessage.from_bytes(message)
                                    if self.audio_buffer:
                                        # Direct audio data processing (no Base64 decoding)
                                        await self.audio_buffer.put(audio_msg.audio_data)
                                        self._audio_packets_received += 1
                                        self._bytes_received += len(audio_msg.audio_data)
                                        
                                        # Debug logging for first few packets only
                                        if self._audio_packets_received <= 3:
                                            buffer_stats = self.audio_buffer.get_stats()
                                            logger.debug(f"🎵 Received audio packet #{self._audio_packets_received}: {len(audio_msg.audio_data)} bytes. Buffer stats: {buffer_stats}")
                                    else:
                                        logger.warning("Received binary audio but no buffer available")
                                except Exception as e:
                                    logger.error(f"Failed to parse binary audio message: {e}")
                            else:
                                logger.warning("Received binary message but binary protocol not enabled")
                        else:
                            # Text control message
                            try:
                                # Simple parsing for control messages
                                data = eval(message)
                                
                                if data.get("type") == "welcome":
                                    logger.info(
                                        f"Received welcome from AudioForwarder: {data.get('speaker_id')}"
                                    )
                                    # Check if binary protocol is supported
                                    if data.get("supports_binary", False):
                                        self._binary_protocol_enabled = True
                                        logger.info("Binary protocol enabled for audio transmission")
                                    else:
                                        logger.warning("AudioForwarder does not support binary protocol")

                                elif data.get("type") == "pong":
                                    # Handle pong responses
                                    pass

                            except Exception as e:
                                logger.error(f"Failed to parse control message: {e}")

                    except Exception as e:
                        logger.error(f"Error processing message: {e}", exc_info=True)

                # If we exit the async for loop, the connection was closed
                logger.warning(
                    "WebSocket connection closed, attempting to reconnect..."
                )
                break

            except websockets.exceptions.ConnectionClosed:
                logger.warning(
                    "AudioForwarder WebSocket connection closed, attempting to reconnect..."
                )
                break
            except Exception as e:
                logger.error(f"Error listening for audio: {e}", exc_info=True)
                break

    async def _monitor_performance(self):
        """Monitor and log performance statistics."""
        while True:
            try:
                await asyncio.sleep(30)  # Log stats every 30 seconds
                
                current_time = time.time()
                uptime = current_time - self._start_time
                time_since_last = current_time - self._last_stats_time
                
                if time_since_last > 0:
                    packets_per_second = self._audio_packets_received / time_since_last
                    bytes_per_second = self._bytes_received / time_since_last
                    
                    buffer_stats = self.audio_buffer.get_stats() if self.audio_buffer else {}
                    
                    logger.info(
                        f"Performance stats - Uptime: {uptime:.1f}s, "
                        f"Packets/sec: {packets_per_second:.1f}, "
                        f"Bytes/sec: {bytes_per_second:.1f}, "
                        f"Total packets: {self._audio_packets_received}, "
                        f"Buffer size: {buffer_stats.get('current_size', 0)}, "
                        f"Jitter delay: {buffer_stats.get('jitter_delay', 0):.3f}s, "
                        f"Binary protocol: {self._binary_protocol_enabled}"
                    )
                    
                    # Reset counters
                    self._audio_packets_received = 0
                    self._bytes_received = 0
                    self._last_stats_time = current_time

            except Exception as e:
                logger.error(f"Error in performance monitoring: {e}", exc_info=True)
                await asyncio.sleep(30)

    async def connect_to_channel(self) -> bool:
        """Connect to the listener channel and start audio playback."""
        try:
            logger.info(
                f"Attempting to connect to voice channel {self.channel_id}"
            )

            guild = self.bot.get_guild(self.guild_id)
            if not guild:
                logger.error(f"Guild {self.guild_id} not found")
                return False

            logger.info(f"Found guild: {guild.name}")

            channel = guild.get_channel(self.channel_id)
            if not channel:
                logger.error(
                    f"Channel {self.channel_id} not found in guild {guild.name}"
                )
                # List available channels for debugging
                available_channels = [
                    f"{ch.name} (ID: {ch.id})" for ch in guild.voice_channels
                ]
                logger.info(f"Available voice channels: {available_channels}")
                return False

            logger.info(
                f"Found channel: {channel.name} (type: {type(channel).__name__})"
            )

            # Connect to voice channel
            logger.info("Attempting to connect to voice channel...")
            self.voice_client = await channel.connect(
                cls=voice_recv.VoiceRecvClient
            )
            logger.info("Voice client connected successfully")

            # Self-deafen to prevent hearing other audio, but don't self-mute (we need to play audio)
            await self.voice_client.guild.change_voice_state(
                channel=channel,
                self_deaf=True,  # Don't hear other audio in the channel
                self_mute=False,  # We need to play audio, so don't mute
            )

            # Create audio buffer and source
            self.audio_buffer = AudioBuffer()
            self.audio_source = OpusAudioSource(self.audio_buffer)

            # Start playing audio
            logger.info("Starting audio playback...")
            logger.info(f"Voice client state: {self.voice_client.is_connected()}")
            logger.info(f"Audio source type: {type(self.audio_source)}")
            logger.info(f"Audio source is_opus: {self.audio_source.is_opus()}")
            
            # Start the audio source first
            self.audio_source.start()
            logger.info("Audio source started successfully")
            
            # Then start playing
            self.voice_client.play(self.audio_source)
            logger.info("Voice client play() called")
            
            # Check if the voice client is actually playing
            logger.info(f"Voice client is_playing: {self.voice_client.is_playing()}")
            
            # Wait a moment and check again
            await asyncio.sleep(0.1)
            logger.info(f"Voice client is_playing after delay: {self.voice_client.is_playing()}")

            logger.info(
                f"Connected to listener channel: {channel.name} (ready to play audio)"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to connect to listener channel: {e}", exc_info=True)
            return False

    async def disconnect(self):
        """Disconnect from voice channel and cleanup."""
        try:
            if self.voice_client:
                await self.voice_client.disconnect()
                self.voice_client = None

            if self.audio_source:
                self.audio_source.stop()
                self.audio_source = None

            if self.audio_buffer:
                self.audio_buffer.clear()
                self.audio_buffer = None

            if self.websocket:
                await self.websocket.close()
                self.websocket = None

            logger.info("AudioReceiver bot disconnected and cleaned up")

        except Exception as e:
            logger.error(f"Error during disconnect: {e}", exc_info=True)

    async def start(self):
        """Start the audio receiver bot."""
        try:
            logger.info(f"Starting AudioReceiver bot {self.bot_id}...")

            # Start the bot
            await self.bot.start(self.bot_token)

        except Exception as e:
            logger.error(f"Failed to start AudioReceiver bot: {e}", exc_info=True)
            raise

    async def stop(self):
        """Stop the audio receiver bot."""
        try:
            logger.info(f"Stopping AudioReceiver bot {self.bot_id}...")

            # Disconnect and cleanup
            await self.disconnect()

            # Close the bot
            if not self.bot.is_closed():
                await self.bot.close()

            logger.info("AudioReceiver bot stopped")

        except Exception as e:
            logger.error(f"Error stopping AudioReceiver bot: {e}", exc_info=True)


async def main():
    """Main function to run the audio receiver bot."""
    try:
        # Create and start the audio receiver bot
        audioreceiver_bot = AudioReceiverBot()

        # Start the bot (connection to voice channel happens in on_ready)
        await audioreceiver_bot.start()

    except KeyboardInterrupt:
        logger.info("AudioReceiver bot shutdown requested")
    except Exception as e:
        logger.critical(f"Fatal error in AudioReceiver bot: {e}")
        raise
    finally:
        if "audioreceiver_bot" in locals():
            await audioreceiver_bot.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("AudioReceiver bot interrupted")
    except Exception as e:
        logger.critical(f"AudioReceiver bot crashed: {e}")
        sys.exit(1)
