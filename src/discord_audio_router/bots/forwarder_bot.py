# forwarder_bot.py
#!/usr/bin/env python3
"""
AudioForwarder Bot Process for Discord Audio Router.

This implementation provides significant latency and performance improvements
through binary WebSocket protocol and direct audio processing.
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

from discord_audio_router.audio import setup_audio_receiver
from discord_audio_router.audio.handlers import BinaryAudioMessage
from discord_audio_router.infrastructure import setup_logging

# Configure logging
logger = setup_logging(
    component_name="audioforwarder_bot",
    log_file="logs/audioforwarder_bot.log",
)


class AudioForwarderBot:
    """Audio forwarder bot with binary protocol and performance improvements."""

    def __init__(self):
        """Initialize the audio forwarder bot."""
        # Get configuration from environment
        self.bot_token = os.getenv("BOT_TOKEN")
        self.bot_id = os.getenv("BOT_ID", "audioforwarder_bot")
        self.bot_type = os.getenv("BOT_TYPE", "speaker")
        self.channel_id = int(os.getenv("CHANNEL_ID", "0"))
        self.guild_id = int(os.getenv("GUILD_ID", "0"))

        if not self.bot_token:
            raise ValueError("BOT_TOKEN environment variable is required")

        if not self.channel_id:
            raise ValueError("CHANNEL_ID environment variable is required")

        # Bot setup
        intents = discord.Intents.default()
        intents.voice_states = True
        intents.guilds = True

        self.bot = commands.Bot(
            command_prefix="!", intents=intents, help_command=None
        )

        # Audio handling
        self.voice_client: Optional[voice_recv.VoiceRecvClient] = None
        self.audio_sink: Optional[object] = None
        self.websocket_server: Optional[websockets.WebSocketServer] = None
        self.connected_listeners = set()
        self._connecting = False
        self.event_loop: Optional[asyncio.AbstractEventLoop] = None

        # Performance tracking
        self._audio_packets_sent = 0
        self._bytes_sent = 0
        self._start_time = time.time()
        self._last_stats_time = time.time()

        # Setup bot events
        self._setup_events()

    def _setup_events(self):
        """Setup bot event handlers."""

        @self.bot.event
        async def on_ready():
            logger.info(
                f"AudioForwarder bot {self.bot_id} ready: {self.bot.user}"
            )
            logger.info(
                f"Target channel: {self.channel_id}, Guild: {self.guild_id}"
            )

            # Ensure bot has Speaker role to join speaker channels
            await self._ensure_speaker_role()

            # Start WebSocket server for audio forwarding
            await self._start_websocket_server()

            # Connect to the speaker channel
            await self.connect_to_channel()

        @self.bot.event
        async def on_connect():
            logger.info(
                f"AudioForwarder bot {self.bot_id} connected to Discord"
            )

        @self.bot.event
        async def on_disconnect():
            logger.warning(
                f"AudioForwarder bot {self.bot_id} disconnected from Discord"
            )

        @self.bot.event
        async def on_voice_state_update(member, before, after):
            """Handle voice state updates to prevent bot from leaving when users mute/unmute."""
            # Only care about voice state changes for our bot
            if member.id == self.bot.user.id:
                # Check if the bot was actually disconnected (moved to no channel)
                if before.channel and after.channel is None:
                    logger.warning("Bot was disconnected from voice channel!")
                    # Only reconnect if we're not already trying to connect
                    if not self._connecting:
                        await asyncio.sleep(2)
                        await self.connect_to_channel()
                # Check if the bot was moved to a different channel
                elif (
                    before.channel
                    and after.channel
                    and before.channel.id != after.channel.id
                ):
                    logger.warning(
                        f"Bot was moved from {before.channel.name} to {after.channel.name}"
                    )
                    # If moved away from our target channel, try to reconnect
                    if (
                        after.channel.id != self.channel_id
                        and not self._connecting
                    ):
                        await asyncio.sleep(2)
                        await self.connect_to_channel()
                # If bot just connected (before.channel is None, after.channel exists)
                elif not before.channel and after.channel:
                    logger.info(
                        f"Bot connected to channel: {after.channel.name}"
                    )

    async def _start_websocket_server(self):
        """Start WebSocket server for audio forwarding."""
        try:
            # Use a unique port for this speaker bot
            port = 8000 + (self.channel_id % 1000)

            logger.info(
                f"Starting WebSocket server on port {port} for AudioForwarder bot {self.bot_id} (channel_id: {self.channel_id})"
            )

            # Start WebSocket server with optimized settings
            self.websocket_server = await websockets.serve(
                self._create_websocket_handler(),
                "localhost",
                port,
                ping_interval=None,  # Disable automatic pings
                ping_timeout=None,  # Disable ping timeout
                close_timeout=5,  # Shorter close timeout
                max_size=2**20,  # 1MB max message size
                compression=None,  # Disable compression for lower latency
            )

            # Wait a moment to ensure server is fully started
            await asyncio.sleep(0.5)

            logger.info(
                f"WebSocket server ready on port {port} for AudioForwarder bot {self.bot_id}"
            )

            # Start connection health monitoring
            asyncio.create_task(self._monitor_connections())

            # Start voice connection monitoring
            asyncio.create_task(self._monitor_voice_connection())

            # Start performance monitoring
            asyncio.create_task(self._monitor_performance())

        except Exception as e:
            logger.error(f"Failed to start WebSocket server: {e}", exc_info=True)

    def _create_websocket_handler(self):
        """Create a WebSocket handler with binary protocol support."""
        async def handler(websocket, path=None):
            """Handle connection from listener bots with binary protocol."""
            try:
                logger.info(
                    f"AudioReceiver bot connected: {websocket.remote_address}"
                )
                self.connected_listeners.add(websocket)

                # Send welcome message with protocol version
                welcome_msg = {
                    "type": "welcome",
                    "speaker_id": self.bot_id,
                    "channel_id": self.channel_id,
                    "protocol_version": "binary_v1",
                    "supports_binary": True
                }
                await websocket.send(str(welcome_msg).replace("'", '"'))

                # Keep connection alive by listening for messages
                try:
                    async for message in websocket:
                        # Handle any incoming messages from listener (like pings)
                        try:
                            if isinstance(message, str):
                                data = eval(message)  # Simple parsing for control messages
                                if data.get("type") == "ping":
                                    await websocket.send('{"type": "pong"}')
                                    logger.debug("Received ping from AudioReceiver, sent pong")
                        except Exception:
                            pass  # Ignore malformed messages
                except websockets.exceptions.ConnectionClosed:
                    logger.info(
                        f"AudioReceiver bot disconnected: {websocket.remote_address}"
                    )
                except Exception as e:
                    logger.error(f"Error in listener connection: {e}", exc_info=True)

            except Exception as e:
                logger.error(f"Error handling listener connection: {e}", exc_info=True)
            finally:
                self.connected_listeners.discard(websocket)
        
        return handler

    def _forward_audio(self, audio_data: bytes):
        """
        Audio forwarding with binary protocol and direct processing.
        
        This method is called directly from the audio sink without task creation,
        providing minimal latency for audio transmission.
        """
        if not self.connected_listeners:
            return

        # Create binary audio message (no JSON, no Base64)
        try:
            binary_message = BinaryAudioMessage(
                speaker_id=self.bot_id,
                channel_id=self.channel_id,
                audio_data=audio_data
            )
            message_bytes = binary_message.to_bytes()
            
            # Update performance counters
            self._audio_packets_sent += 1
            self._bytes_sent += len(message_bytes)
            
            # Debug logging for first few packets
            if self._audio_packets_sent <= 5:
                logger.info(f"Captured audio packet #{self._audio_packets_sent}: {len(audio_data)} bytes, sending to {len(self.connected_listeners)} listeners")
            
            # Send to all connected listeners concurrently
            # Note: This is called from the audio sink thread, so we need to schedule
            # the WebSocket sends on the event loop using run_coroutine_threadsafe
            if self.connected_listeners and self.event_loop:
                future = asyncio.run_coroutine_threadsafe(
                    self._send_binary_to_listeners(message_bytes), 
                    self.event_loop
                )
                # Don't wait for the result to avoid blocking the audio thread
                
        except Exception as e:
            logger.error(f"Error creating binary audio message: {e}", exc_info=True)

    async def _send_binary_to_listeners(self, message_bytes: bytes):
        """Send binary message to all connected listeners."""
        if not self.connected_listeners:
            return

        # Send to all connected listeners concurrently
        send_tasks = []
        for websocket in self.connected_listeners:
            send_tasks.append(self._safe_send_binary(websocket, message_bytes))

        # Wait for all sends to complete concurrently
        results = await asyncio.gather(*send_tasks, return_exceptions=True)

        # Clean up disconnected listeners
        disconnected = set()
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                websocket = list(self.connected_listeners)[idx]
                disconnected.add(websocket)
                if isinstance(result, websockets.exceptions.ConnectionClosed):
                    logger.debug(f"Listener disconnected: {websocket}")
                else:
                    logger.error(f"Failed to send binary audio to listener: {result}")

        # Remove disconnected listeners
        if disconnected:
            self.connected_listeners -= disconnected
            logger.debug(f"Removed {len(disconnected)} disconnected listeners")

    async def _safe_send_binary(self, websocket, message_bytes: bytes):
        """Safely send binary audio message to a single websocket."""
        try:
            await websocket.send(message_bytes)
        except websockets.exceptions.ConnectionClosed:
            raise  # Re-raise to be handled by caller
        except Exception as e:
            logger.error(f"Error sending binary audio: {e}")
            raise  # Re-raise to be handled by caller

    async def _monitor_connections(self):
        """Monitor WebSocket connections for health."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every 60 seconds

                if not self.connected_listeners:
                    logger.debug("No listeners connected")
                    continue

                # Log connection status periodically
                logger.info(
                    f"WebSocket connections: {len(self.connected_listeners)} listeners connected"
                )

            except Exception as e:
                logger.error(f"Error in connection monitoring: {e}", exc_info=True)
                await asyncio.sleep(30)  # Wait before retrying

    async def _monitor_voice_connection(self):
        """Monitor voice connection and reconnect if needed."""
        status_counter = 0
        while True:
            try:
                await asyncio.sleep(15)  # Check every 15 seconds
                status_counter += 1

                if (
                    not self.voice_client
                    or not self.voice_client.is_connected()
                ):
                    logger.warning(
                        "Voice client disconnected, attempting to reconnect..."
                    )
                    # Only reconnect if we're not already trying to connect
                    if not self._connecting:
                        await self.connect_to_channel()
                else:
                    # Log status every 60 seconds (4 * 15 seconds)
                    if status_counter % 4 == 0:
                        logger.info(
                            f"Voice connection healthy, {len(self.connected_listeners)} listeners connected"
                        )

            except Exception as e:
                logger.error(f"Error in voice connection monitoring: {e}", exc_info=True)
                await asyncio.sleep(15)  # Wait before retrying

    async def _monitor_performance(self):
        """Monitor and log performance statistics."""
        while True:
            try:
                await asyncio.sleep(30)  # Log stats every 30 seconds
                
                current_time = time.time()
                uptime = current_time - self._start_time
                time_since_last = current_time - self._last_stats_time
                
                if time_since_last > 0:
                    packets_per_second = self._audio_packets_sent / time_since_last
                    bytes_per_second = self._bytes_sent / time_since_last
                    
                    logger.info(
                        f"Performance stats - Uptime: {uptime:.1f}s, "
                        f"Packets/sec: {packets_per_second:.1f}, "
                        f"Bytes/sec: {bytes_per_second:.1f}, "
                        f"Total packets: {self._audio_packets_sent}, "
                        f"Listeners: {len(self.connected_listeners)}"
                    )
                    
                    # Reset counters
                    self._audio_packets_sent = 0
                    self._bytes_sent = 0
                    self._last_stats_time = current_time

            except Exception as e:
                logger.error(f"Error in performance monitoring: {e}", exc_info=True)
                await asyncio.sleep(30)

    async def _ensure_speaker_role(self):
        """Ensure the AudioForwarder bot has the Speaker role to join speaker channels."""
        try:
            guild = self.bot.get_guild(self.guild_id)
            if not guild:
                logger.error(f"Guild {self.guild_id} not found")
                return

            bot_member = guild.get_member(self.bot.user.id)
            if not bot_member:
                logger.error(f"Bot member not found in guild {guild.name}")
                return

            # Look for the Speaker role
            speaker_role = discord.utils.get(guild.roles, name="Speaker")
            if not speaker_role:
                logger.warning("Speaker role not found - AudioForwarder bot may not be able to join speaker channels")
                return

            # Check if bot already has the Speaker role
            if speaker_role in bot_member.roles:
                logger.info(f"Optimized AudioForwarder bot already has Speaker role: {speaker_role.name}")
                return

            # Try to add the Speaker role to the bot
            try:
                await bot_member.add_roles(
                    speaker_role,
                    reason="Optimized AudioForwarder bot needs Speaker role to join speaker channels"
                )
                logger.info(f"Added Speaker role to Optimized AudioForwarder bot: {speaker_role.name}")
            except discord.Forbidden:
                logger.warning("Cannot add Speaker role to Optimized AudioForwarder bot - insufficient permissions")
            except Exception as e:
                logger.error(f"Error adding Speaker role to Optimized AudioForwarder bot: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Error ensuring Speaker role for Optimized AudioForwarder bot: {e}", exc_info=True)

    async def connect_to_channel(self) -> bool:
        """Connect to the speaker channel and start optimized audio capture."""
        try:
            # Prevent multiple simultaneous connection attempts
            if self._connecting:
                logger.info("Connection already in progress, skipping...")
                return False

            self._connecting = True
            logger.info(
                f"Attempting to connect to voice channel {self.channel_id}"
            )

            try:
                # Check if already connected and working properly
                if self.voice_client and self.voice_client.is_connected():
                    # Check if we're in the right channel
                    if (
                        hasattr(self.voice_client, "channel")
                        and self.voice_client.channel
                        and self.voice_client.channel.id == self.channel_id
                    ):
                        logger.info(
                            "Already connected to correct voice channel"
                        )
                        return True
                    else:
                        logger.info(
                            "Connected to wrong channel, reconnecting..."
                        )
                        await self.voice_client.disconnect()
                        self.voice_client = None

                guild = self.bot.get_guild(self.guild_id)
                if not guild:
                    logger.error(f"Guild {self.guild_id} not found")
                    return False

                channel = guild.get_channel(self.channel_id)
                if not channel:
                    logger.error(f"Channel {self.channel_id} not found")
                    return False

                # Connect to voice channel
                try:
                    self.voice_client = await channel.connect(
                        cls=voice_recv.VoiceRecvClient
                    )
                except Exception as connect_error:
                    if "Already connected to a voice channel" in str(
                        connect_error
                    ):
                        logger.warning(
                            "Already connected to a voice channel, disconnecting first..."
                        )
                        # Try to disconnect from any existing connection
                        if hasattr(self.bot, "voice_clients"):
                            for vc in self.bot.voice_clients:
                                await vc.disconnect()
                        # Wait a moment and try again
                        await asyncio.sleep(1)
                        self.voice_client = await channel.connect(
                            cls=voice_recv.VoiceRecvClient
                        )
                    else:
                        raise connect_error

                logger.info(f"Voice client connected: {self.voice_client}")
                logger.info(f"Voice client type: {type(self.voice_client)}")
                logger.info(
                    f"Voice client connected: {self.voice_client.is_connected()}"
                )

                # Self-deafen to prevent hearing our own audio (prevents feedback)
                await self.voice_client.guild.change_voice_state(
                    channel=channel,
                    self_deaf=True,
                    self_mute=False,  # We want to capture audio, so don't mute
                )
                logger.info("Voice state updated: self-deafened")

                # Setup audio capture with direct callback
                self.audio_sink = await setup_audio_receiver(
                    self.voice_client, self._forward_audio
                )

                logger.info(
                    f"Connected to speaker channel: {channel.name} (self-deafened)"
                )
                logger.info(
                    f"Audio sink setup complete: {self.audio_sink is not None}"
                )
                return True

            finally:
                # Always reset the connecting flag
                self._connecting = False

        except Exception as e:
            logger.error(f"Failed to connect to speaker channel: {e}", exc_info=True)
            self._connecting = False
            return False

    async def disconnect(self):
        """Disconnect from voice channel and cleanup."""
        try:
            if self.voice_client:
                await self.voice_client.disconnect()
                self.voice_client = None

            if self.websocket_server:
                self.websocket_server.close()
                await self.websocket_server.wait_closed()
                self.websocket_server = None

            # Close all listener connections
            for websocket in list(self.connected_listeners):
                await websocket.close()
            self.connected_listeners.clear()

            logger.info("AudioForwarder bot disconnected and cleaned up")

        except Exception as e:
            logger.error(f"Error during disconnect: {e}", exc_info=True)

    async def start(self):
        """Start the audio forwarder bot."""
        try:
            logger.info(f"Starting AudioForwarder bot {self.bot_id}...")

            # Store the event loop for use in audio callbacks
            self.event_loop = asyncio.get_running_loop()

            # Start the bot
            await self.bot.start(self.bot_token)

        except Exception as e:
            logger.error(f"Failed to start AudioForwarder bot: {e}", exc_info=True)
            raise

    async def stop(self):
        """Stop the audio forwarder bot."""
        try:
            logger.info(f"Stopping AudioForwarder bot {self.bot_id}...")

            # Disconnect and cleanup
            await self.disconnect()

            # Close the bot
            if not self.bot.is_closed():
                await self.bot.close()

            logger.info("AudioForwarder bot stopped")

        except Exception as e:
            logger.error(f"Error stopping AudioForwarder bot: {e}", exc_info=True)


async def main():
    """Main function to run the audio forwarder bot."""
    try:
        # Create and start the audio forwarder bot
        audioforwarder_bot = AudioForwarderBot()

        # Start the bot (connection to voice channel happens in on_ready)
        await audioforwarder_bot.start()

    except KeyboardInterrupt:
        logger.info("AudioForwarder bot shutdown requested")
    except Exception as e:
        logger.critical(f"Fatal error in AudioForwarder bot: {e}")
        raise
    finally:
        if "audioforwarder_bot" in locals():
            await audioforwarder_bot.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("AudioForwarder bot interrupted")
    except Exception as e:
        logger.critical(f"AudioForwarder bot crashed: {e}")
        sys.exit(1)
