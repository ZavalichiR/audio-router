#!/usr/bin/env python3
"""
Standalone Listener Bot Process for Discord Audio Router.

This process runs a Discord bot that receives audio from a speaker bot
via WebSocket and plays it in a listener channel.
"""

import asyncio
import json
import os
import sys

# Add the bots directory to the Python path
from pathlib import Path
from typing import Optional

import discord
import websockets
import websockets.exceptions
from discord.ext import commands, voice_recv

bots_dir = Path(__file__).parent
sys.path.insert(0, str(bots_dir))

from audio_handler import AudioBuffer, OpusAudioSource
from logging_config import setup_logging

# Configure logging
logger = setup_logging(
    component_name="listener_bot", log_level="INFO", log_file="logs/listener_bot.log"
)


class ListenerBot:
    """Standalone listener bot that receives audio and plays it."""

    def __init__(self):
        """Initialize the listener bot."""
        # Get configuration from environment
        self.bot_token = os.getenv("BOT_TOKEN")
        self.bot_id = os.getenv("BOT_ID", "listener_bot")
        self.bot_type = os.getenv("BOT_TYPE", "listener")
        self.channel_id = int(os.getenv("CHANNEL_ID", "0"))
        self.guild_id = int(os.getenv("GUILD_ID", "0"))
        self.speaker_channel_id = int(os.getenv("SPEAKER_CHANNEL_ID", "0"))

        if not self.bot_token:
            raise ValueError("BOT_TOKEN environment variable is required")

        if not self.channel_id:
            raise ValueError("CHANNEL_ID environment variable is required")

        # Bot setup
        intents = discord.Intents.default()
        intents.voice_states = True
        intents.guilds = True

        self.bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

        # Audio handling
        self.voice_client: Optional[voice_recv.VoiceRecvClient] = None
        self.audio_buffer: Optional[AudioBuffer] = None
        self.audio_source: Optional[OpusAudioSource] = None
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.speaker_websocket_url: Optional[str] = None
        self._reconnecting = False  # Flag to prevent multiple reconnection attempts

        # Setup bot events
        self._setup_events()

    def _setup_events(self):
        """Setup bot event handlers."""

        @self.bot.event
        async def on_ready():
            logger.info(f"Listener bot {self.bot_id} ready: {self.bot.user}")
            logger.info(f"Target channel: {self.channel_id}, Guild: {self.guild_id}")

            # Connect to the listener channel
            await self.connect_to_channel()

            # Connect to speaker bot WebSocket
            await self._connect_to_speaker()

        @self.bot.event
        async def on_connect():
            logger.info(f"Listener bot {self.bot_id} connected to Discord")

        @self.bot.event
        async def on_disconnect():
            logger.warning(f"Listener bot {self.bot_id} disconnected from Discord")

    async def _connect_to_speaker(self):
        """Connect to the speaker bot's WebSocket server."""
        try:
            if not self.speaker_channel_id:
                logger.error("No speaker channel ID provided")
                return

            # Calculate the same port that the speaker bot uses
            # Use the same logic as speaker bot: 8000 + (channel_id % 1000)
            speaker_port = 8000 + (self.speaker_channel_id % 1000)
            self.speaker_websocket_url = f"ws://localhost:{speaker_port}"

            logger.info(
                f"Connecting to speaker WebSocket: {self.speaker_websocket_url}"
            )

            # Connect to speaker bot with better connection settings
            self.websocket = await websockets.connect(
                self.speaker_websocket_url,
                ping_interval=20,  # Send ping every 20 seconds (less frequent)
                ping_timeout=10,  # Wait 10 seconds for pong (more lenient)
                close_timeout=10,  # Wait 10 seconds for close (more lenient)
                max_size=2**20,  # 1MB max message size
                compression=None,  # Disable compression for lower latency
            )

            # Start listening for audio data
            asyncio.create_task(self._listen_for_audio())

            # Start heartbeat to keep connection alive
            asyncio.create_task(self._heartbeat())

            logger.info("Connected to speaker bot WebSocket")

        except Exception as e:
            logger.error(f"Failed to connect to speaker WebSocket: {e}")
            # Retry connection after a delay
            asyncio.create_task(self._retry_speaker_connection())

    async def _retry_speaker_connection(self):
        """Retry connection to speaker bot."""
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
                logger.warning(f"Retry {retry_count}/{max_retries} failed: {e}")
                retry_delay = min(retry_delay * 1.5, 30.0)  # Exponential backoff

        logger.error("Failed to connect to speaker bot after maximum retries")

    async def _heartbeat(self):
        """Send periodic heartbeat to keep WebSocket connection alive."""
        while True:
            try:
                await asyncio.sleep(30)  # Send heartbeat every 30 seconds
                if self.websocket and not self.websocket.closed:
                    await self.websocket.ping()
                    logger.debug("Sent heartbeat ping to speaker WebSocket")
                else:
                    logger.warning("WebSocket is closed, stopping heartbeat")
                    break
            except Exception as e:
                logger.error(f"Error sending heartbeat: {e}")
                break

    async def _listen_for_audio(self):
        """Listen for audio data from the speaker bot."""
        while True:
            try:
                async for message in self.websocket:
                    try:
                        data = json.loads(message)

                        if data.get("type") == "welcome":
                            logger.info(
                                f"Received welcome from speaker: {data.get('speaker_id')}"
                            )

                        elif data.get("type") == "audio":
                            # Process audio data
                            audio_hex = data.get("audio_data", "")
                            if audio_hex and self.audio_buffer:
                                # Convert hex string back to bytes
                                audio_data = bytes.fromhex(audio_hex)
                                await self.audio_buffer.put(audio_data)
                                logger.debug(
                                    f"🎧 Received and buffered audio: {len(audio_data)} bytes"
                                )
                            else:
                                logger.warning(
                                    "Received audio message but no audio data or buffer"
                                )

                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse WebSocket message: {e}")
                    except Exception as e:
                        logger.error(f"Error processing audio message: {e}")

                # If we exit the async for loop, the connection was closed
                logger.warning(
                    "WebSocket connection closed, attempting to reconnect..."
                )
                break

            except websockets.exceptions.ConnectionClosed:
                logger.warning(
                    "Speaker WebSocket connection closed, attempting to reconnect..."
                )
                break
            except Exception as e:
                logger.error(f"Error listening for audio: {e}")
                break

            # Try to reconnect (prevent multiple simultaneous attempts)
            if self._reconnecting:
                logger.info("Reconnection already in progress, skipping...")
                break

            self._reconnecting = True
            try:
                logger.info("Waiting 3 seconds before attempting reconnection...")
                await asyncio.sleep(3)

                # Close existing websocket if it exists
                if hasattr(self, "websocket") and self.websocket:
                    try:
                        await self.websocket.close()
                    except:
                        pass
                    self.websocket = None

                logger.info("Attempting to reconnect to speaker WebSocket...")
                await self._connect_to_speaker()
                logger.info("Successfully reconnected to speaker WebSocket")
                self._reconnecting = False
                # Continue the while loop to start listening again
            except Exception as reconnect_error:
                logger.error(
                    f"Failed to reconnect to speaker WebSocket: {reconnect_error}"
                )
                logger.error(
                    f"Reconnection error type: {type(reconnect_error).__name__}"
                )
                self._reconnecting = False
                # Fall back to retry task
                asyncio.create_task(self._retry_speaker_connection())
                break

    async def connect_to_channel(self) -> bool:
        """Connect to the listener channel and start audio playback."""
        try:
            guild = self.bot.get_guild(self.guild_id)
            if not guild:
                logger.error(f"Guild {self.guild_id} not found")
                return False

            channel = guild.get_channel(self.channel_id)
            if not channel:
                logger.error(f"Channel {self.channel_id} not found")
                return False

            # Connect to voice channel
            self.voice_client = await channel.connect(cls=voice_recv.VoiceRecvClient)

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
            self.voice_client.play(self.audio_source)
            self.audio_source.start()

            logger.info(
                f"Connected to listener channel: {channel.name} (self-deafened)"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to connect to listener channel: {e}")
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
                await self.audio_buffer.clear()
                self.audio_buffer = None

            if self.websocket:
                await self.websocket.close()
                self.websocket = None

            logger.info("Listener bot disconnected and cleaned up")

        except Exception as e:
            logger.error(f"Error during disconnect: {e}")

    async def start(self):
        """Start the listener bot."""
        try:
            logger.info(f"Starting listener bot {self.bot_id}...")

            # Start the bot
            await self.bot.start(self.bot_token)

        except Exception as e:
            logger.error(f"Failed to start listener bot: {e}")
            raise

    async def stop(self):
        """Stop the listener bot."""
        try:
            logger.info(f"Stopping listener bot {self.bot_id}...")

            # Disconnect and cleanup
            await self.disconnect()

            # Close the bot
            if not self.bot.is_closed():
                await self.bot.close()

            logger.info("Listener bot stopped")

        except Exception as e:
            logger.error(f"Error stopping listener bot: {e}")


async def main():
    """Main function to run the listener bot."""
    try:
        # Create and start the listener bot
        listener_bot = ListenerBot()

        # Start the bot (connection to voice channel happens in on_ready)
        await listener_bot.start()

    except KeyboardInterrupt:
        logger.info("Listener bot shutdown requested")
    except Exception as e:
        logger.critical(f"Fatal error in listener bot: {e}")
        raise
    finally:
        if "listener_bot" in locals():
            await listener_bot.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Listener bot interrupted")
    except Exception as e:
        logger.critical(f"Listener bot crashed: {e}")
        sys.exit(1)
