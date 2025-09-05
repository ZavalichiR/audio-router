#!/usr/bin/env python3
"""
Standalone Speaker Bot Process for Discord Audio Router.

This process runs a Discord bot that captures audio from a speaker channel
and forwards it to listener bots via WebSocket.
"""

import asyncio
import logging
import os
import sys
import json
import websockets
import websockets.exceptions
from typing import Optional
import discord
from discord.ext import commands, voice_recv

# Add the bots directory to the Python path
from pathlib import Path
bots_dir = Path(__file__).parent
sys.path.insert(0, str(bots_dir))

from audio_handler import setup_audio_receiver
from logging_config import setup_logging

# Configure logging
logger = setup_logging(
    component_name="speaker_bot",
    log_level="INFO",
    log_file="logs/speaker_bot.log"
)


class SpeakerBot:
    """Standalone speaker bot that captures audio and forwards it."""
    
    def __init__(self):
        """Initialize the speaker bot."""
        # Get configuration from environment
        self.bot_token = os.getenv("BOT_TOKEN")
        self.bot_id = os.getenv("BOT_ID", "speaker_bot")
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
            command_prefix='!',
            intents=intents,
            help_command=None
        )
        
        # Audio handling
        self.voice_client: Optional[voice_recv.VoiceRecvClient] = None
        self.audio_sink: Optional[object] = None
        self.websocket_server: Optional[websockets.WebSocketServer] = None
        self.connected_listeners = set()
        
        # Setup bot events
        self._setup_events()
    
    def _setup_events(self):
        """Setup bot event handlers."""
        
        @self.bot.event
        async def on_ready():
            logger.info(f"Speaker bot {self.bot_id} ready: {self.bot.user}")
            logger.info(f"Target channel: {self.channel_id}, Guild: {self.guild_id}")
            
            # Start WebSocket server for audio forwarding
            await self._start_websocket_server()
            
            # Connect to the speaker channel
            await self.connect_to_channel()
        
        @self.bot.event
        async def on_connect():
            logger.info(f"Speaker bot {self.bot_id} connected to Discord")
        
        @self.bot.event
        async def on_disconnect():
            logger.warning(f"Speaker bot {self.bot_id} disconnected from Discord")
        
        @self.bot.event
        async def on_voice_state_update(member, before, after):
            """Handle voice state updates to prevent bot from leaving when users mute/unmute."""
            # Only care about voice state changes in our target channel
            if before.channel and before.channel.id == self.channel_id:
                logger.info(f"Voice state update in speaker channel: {member.display_name}")
                logger.info(f"Before: muted={before.self_mute}, deafened={before.self_deaf}")
                logger.info(f"After: muted={after.self_mute}, deafened={after.self_deaf}")
                
                # If the bot itself is being moved or disconnected, handle it
                if member.id == self.bot.user.id:
                    if after.channel is None:
                        logger.warning("Bot was disconnected from voice channel!")
                        # Try to reconnect
                        await asyncio.sleep(1)
                        await self.connect_to_channel()
                    elif after.channel.id != self.channel_id:
                        logger.warning(f"Bot was moved to different channel: {after.channel.name}")
                        # Try to reconnect to our target channel
                        await asyncio.sleep(1)
                        await self.connect_to_channel()
    
    async def _start_websocket_server(self):
        """Start WebSocket server for audio forwarding."""
        try:
            # Use a unique port for this speaker bot
            # Extract channel ID from bot_id (format: "speaker_{channel_id}")
            channel_id_str = self.bot_id.replace("speaker_", "")
            port = 8000 + (int(channel_id_str) % 1000)
            
            # Start WebSocket server with better error handling
            self.websocket_server = await websockets.serve(
                self._handle_listener_connection,
                "localhost",
                port,
                ping_interval=20,  # Send ping every 20 seconds (less frequent)
                ping_timeout=10,   # Wait 10 seconds for pong (more lenient)
                close_timeout=10,  # Wait 10 seconds for close (more lenient)
                max_size=2**20,    # 1MB max message size
                compression=None   # Disable compression for lower latency
            )
            
            logger.info(f"Started WebSocket server on port {port} for speaker bot {self.bot_id}")
            
            # Start connection health monitoring
            asyncio.create_task(self._monitor_connections())
            
            # Start voice connection monitoring
            asyncio.create_task(self._monitor_voice_connection())
            
        except Exception as e:
            logger.error(f"Failed to start WebSocket server: {e}")
    
    async def _handle_listener_connection(self, websocket, path):
        """Handle connection from listener bots."""
        try:
            logger.info(f"Listener bot connected: {websocket.remote_address}")
            self.connected_listeners.add(websocket)
            
            # Send welcome message
            await websocket.send(json.dumps({
                "type": "welcome",
                "speaker_id": self.bot_id,
                "channel_id": self.channel_id
            }))
            
            # Keep connection alive
            await websocket.wait_closed()
            
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Listener bot disconnected: {websocket.remote_address}")
        except Exception as e:
            logger.error(f"Error handling listener connection: {e}")
        finally:
            self.connected_listeners.discard(websocket)
    
    async def _forward_audio(self, audio_data: bytes):
        """Forward audio data to all connected listener bots."""
        logger.debug(f"🎵 Audio captured: {len(audio_data)} bytes")
        
        if not self.connected_listeners:
            logger.debug("No connected listeners to forward audio to")
            return
        
        logger.debug(f"Forwarding audio to {len(self.connected_listeners)} listeners")
        
        # Create audio message
        message = json.dumps({
            "type": "audio",
            "speaker_id": self.bot_id,
            "channel_id": self.channel_id,
            "audio_data": audio_data.hex()  # Convert bytes to hex string
        })
        
        # Send to all connected listeners
        disconnected = set()
        for websocket in self.connected_listeners:
            try:
                await websocket.send(message)
                logger.debug("Audio sent to listener successfully")
            except websockets.exceptions.ConnectionClosed:
                logger.warning("Listener disconnected while sending audio")
                disconnected.add(websocket)
            except Exception as e:
                logger.error(f"Error sending audio to listener: {e}")
                disconnected.add(websocket)
        
        # Remove disconnected listeners
        self.connected_listeners -= disconnected
    
    async def _monitor_connections(self):
        """Monitor WebSocket connections for health."""
        while True:
            try:
                await asyncio.sleep(15)  # Check every 15 seconds (more frequent)
                
                if not self.connected_listeners:
                    continue
                
                # Send ping to all connected listeners
                disconnected = set()
                for websocket in list(self.connected_listeners):
                    try:
                        await websocket.ping()
                    except websockets.exceptions.ConnectionClosed:
                        disconnected.add(websocket)
                    except Exception as e:
                        logger.warning(f"Error pinging listener: {e}")
                        disconnected.add(websocket)
                
                # Remove disconnected listeners
                self.connected_listeners -= disconnected
                
                if disconnected:
                    logger.info(f"Removed {len(disconnected)} disconnected listeners")
                    
            except Exception as e:
                logger.error(f"Error in connection monitoring: {e}")
                await asyncio.sleep(5)  # Wait before retrying
    
    async def _monitor_voice_connection(self):
        """Monitor voice connection and reconnect if needed."""
        status_counter = 0
        while True:
            try:
                await asyncio.sleep(5)  # Check every 5 seconds (more frequent)
                status_counter += 1
                
                if not self.voice_client or not self.voice_client.is_connected():
                    logger.warning("Voice client disconnected, attempting to reconnect...")
                    await self.connect_to_channel()
                else:
                    # Log status every 60 seconds (12 * 5 seconds)
                    if status_counter % 12 == 0:
                        logger.info(f"Voice connection healthy, {len(self.connected_listeners)} listeners connected")
                    else:
                        logger.debug("Voice connection is healthy")
                    
            except Exception as e:
                logger.error(f"Error in voice connection monitoring: {e}")
                await asyncio.sleep(5)  # Wait before retrying
    
    async def connect_to_channel(self) -> bool:
        """Connect to the speaker channel and start audio capture."""
        try:
            # Check if already connected
            if self.voice_client and self.voice_client.is_connected():
                logger.info("Already connected to voice channel")
                return True
            
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
            logger.info(f"Voice client connected: {self.voice_client}")
            logger.info(f"Voice client type: {type(self.voice_client)}")
            logger.info(f"Voice client connected: {self.voice_client.is_connected()}")
            
            # Self-deafen to prevent hearing our own audio (prevents feedback)
            await self.voice_client.guild.change_voice_state(
                channel=channel,
                self_deaf=True,
                self_mute=False  # We want to capture audio, so don't mute
            )
            logger.info("Voice state updated: self-deafened")
            
            # Setup audio capture
            self.audio_sink = await setup_audio_receiver(
                self.voice_client,
                self._forward_audio
            )
            
            logger.info(f"Connected to speaker channel: {channel.name} (self-deafened)")
            logger.info(f"Audio sink setup complete: {self.audio_sink is not None}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to speaker channel: {e}")
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
            
            logger.info("Speaker bot disconnected and cleaned up")
            
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
    
    async def start(self):
        """Start the speaker bot."""
        try:
            logger.info(f"Starting speaker bot {self.bot_id}...")
            
            # Start the bot
            await self.bot.start(self.bot_token)
            
        except Exception as e:
            logger.error(f"Failed to start speaker bot: {e}")
            raise
    
    async def stop(self):
        """Stop the speaker bot."""
        try:
            logger.info(f"Stopping speaker bot {self.bot_id}...")
            
            # Disconnect and cleanup
            await self.disconnect()
            
            # Close the bot
            if not self.bot.is_closed():
                await self.bot.close()
            
            logger.info("Speaker bot stopped")
            
        except Exception as e:
            logger.error(f"Error stopping speaker bot: {e}")


async def main():
    """Main function to run the speaker bot."""
    try:
        # Create and start the speaker bot
        speaker_bot = SpeakerBot()
        
        # Start the bot (connection to voice channel happens in on_ready)
        await speaker_bot.start()
        
    except KeyboardInterrupt:
        logger.info("Speaker bot shutdown requested")
    except Exception as e:
        logger.critical(f"Fatal error in speaker bot: {e}")
        raise
    finally:
        if 'speaker_bot' in locals():
            await speaker_bot.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Speaker bot interrupted")
    except Exception as e:
        logger.critical(f"Speaker bot crashed: {e}")
        sys.exit(1)
