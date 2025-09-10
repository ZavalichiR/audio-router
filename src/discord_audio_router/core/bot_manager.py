"""
Bot Manager for Discord Audio Router Bot.

This module manages separate processes for each Discord bot instance,
enabling true multi-channel audio with process isolation.
"""

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from discord_audio_router.infrastructure import setup_logging
# Configure logging
logger = setup_logging(
    component_name="bot_manager",
    log_file="logs/section_manager.log",
)

class BotProcess:
    """Represents a bot process instance."""

    def __init__(
        self,
        bot_id: str,
        bot_type: str,
        token: str,
        channel_id: int,
        guild_id: int,
        process: subprocess.Popen = None,
    ):
        """
        Initialize a bot process.

        Args:
            bot_id: Unique identifier for the bot
            bot_type: Type of bot ('speaker' or 'listener')
            token: Discord bot token
            channel_id: Target channel ID
            guild_id: Guild ID
            process: Subprocess instance
        """
        self.bot_id = bot_id
        self.bot_type = bot_type
        self.token = token
        self.channel_id = channel_id
        self.guild_id = guild_id
        self.process: Optional[subprocess.Popen] = process
        self.is_running = False
        self.start_time: Optional[float] = None
        self.pid: Optional[int] = None

    def start(self) -> bool:
        """Start the bot process."""
        try:
            if self.process and self.process.poll() is None:
                logger.warning(f"Bot process {self.bot_id} is already running")
                return True

            # Determine which script to run
            if self.bot_type == "speaker":
                script_path = (
                    Path(__file__).parent.parent / "bots" / "forwarder_bot.py"
                )
            elif self.bot_type == "listener":
                script_path = (
                    Path(__file__).parent.parent / "bots" / "receiver_bot.py"
                )
            else:
                logger.error(f"Unknown bot type: {self.bot_type}")
                return False

            # Prepare environment variables
            env = os.environ.copy()
            env.update(
                {
                    "BOT_TOKEN": self.token,
                    "BOT_ID": self.bot_id,
                    "BOT_TYPE": self.bot_type,
                    "CHANNEL_ID": str(self.channel_id),
                    "GUILD_ID": str(self.guild_id),
                    "PYTHONPATH": str(Path(__file__).parent.parent.parent),
                }
            )

            # For listener bots, add speaker channel ID if available
            if self.bot_type == "listener" and hasattr(
                self, "speaker_channel_id"
            ):
                env["SPEAKER_CHANNEL_ID"] = str(self.speaker_channel_id)

            # Start the process
            self.process = subprocess.Popen(
                [sys.executable, str(script_path)],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            self.pid = self.process.pid
            self.is_running = True
            self.start_time = time.time()

            logger.info(
                f"Started {self.bot_type} bot process {self.bot_id} (PID: {self.pid})"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to start bot process {self.bot_id}: {e}", exc_info=True)
            self.is_running = False
            return False

    def stop(self) -> bool:
        """Stop the bot process."""
        try:
            if not self.process:
                logger.warning(f"Bot process {self.bot_id} is not running")
                return True

            if self.process.poll() is None:
                # Process is still running, terminate it
                self.process.terminate()

                # Wait for graceful shutdown
                try:
                    self.process.wait(timeout=10.0)  # Increased timeout for graceful shutdown
                except subprocess.TimeoutExpired:
                    # Force kill if graceful shutdown fails
                    logger.warning(f"Force killing bot process {self.bot_id}")
                    self.process.kill()
                    self.process.wait()

            self.is_running = False
            self.pid = None

            logger.info(f"Stopped bot process: {self.bot_id}")
            return True

        except Exception as e:
            logger.error(f"Error stopping bot process {self.bot_id}: {e}", exc_info=True)
            return False

    def is_alive(self) -> bool:
        """Check if the bot process is alive."""
        if not self.process:
            return False

        return self.process.poll() is None

    def get_status(self) -> Dict[str, Any]:
        """Get the status of the bot process."""
        return {
            "bot_id": self.bot_id,
            "bot_type": self.bot_type,
            "channel_id": self.channel_id,
            "guild_id": self.guild_id,
            "is_running": self.is_running,
            "is_alive": self.is_alive(),
            "pid": self.pid,
            "start_time": self.start_time,
            "uptime": time.time() - self.start_time if self.start_time else 0,
        }


class BotManager:
    """
    Manages multiple Discord bot processes.

    This manager spawns and manages separate processes for each bot,
    enabling true multi-channel audio with process isolation.
    """

    def __init__(self, config):
        """
        Initialize the bot manager.

        Args:
            config: Bot configuration
        """
        self.config = config
        self.bot_processes: Dict[str, BotProcess] = {}
        self.available_tokens: List[str] = []
        self.used_tokens: set = set()
        
        # Simple token list - Channel-1 gets Token-1, Channel-2 gets Token-2, etc.

    def add_available_tokens(self, tokens: List[str]):
        """Add available bot tokens."""
        self.available_tokens.extend(tokens)
        logger.info(f"Added {len(tokens)} available bot tokens")
        
        # Log token order for debugging
        for i, token in enumerate(tokens):
            # Show first few and last few characters of token for identification
            token_preview = f"{token[:8]}...{token[-8:]}" if len(token) > 16 else token
            logger.info(f"Token #{i+1}: {token_preview}")


    async def start_speaker_bot(
        self, channel_id: int, guild_id: int
    ) -> Optional[str]:
        """
        Start a speaker bot process.

        Args:
            channel_id: Speaker channel ID
            guild_id: Guild ID

        Returns:
            Bot ID if successful, None otherwise
        """
        try:
            bot_id = f"audioforwarder_{channel_id}"

            # Check if already running
            if (
                bot_id in self.bot_processes
                and self.bot_processes[bot_id].is_alive()
            ):
                logger.info(f"AudioForwarder bot {bot_id} is already running")
                return bot_id

            # Use AudioForwarder token for speaker
            token = self.config.audio_forwarder_token

            # Create bot process
            bot_process = BotProcess(
                bot_id=bot_id,
                bot_type="speaker",
                token=token,
                channel_id=channel_id,
                guild_id=guild_id,
            )

            # Start the process
            if bot_process.start():
                self.bot_processes[bot_id] = bot_process
                logger.info(f"Started AudioForwarder bot process: {bot_id}")
                return bot_id
            else:
                logger.error(
                    f"Failed to start AudioForwarder bot process: {bot_id}"
                )
                return None

        except Exception as e:
            logger.error(f"Error starting AudioForwarder bot: {e}", exc_info=True)
            return None

    async def start_listener_bot(
        self, channel_id: int, guild_id: int, speaker_channel_id: int, channel_number: int
    ) -> Optional[str]:
        """
        Start a listener bot process.

        Args:
            channel_id: Listener channel ID
            guild_id: Guild ID
            speaker_channel_id: Speaker channel ID (for WebSocket connection)
            channel_number: Channel number (1, 2, 3, etc.) for token assignment

        Returns:
            Bot ID if successful, None otherwise
        """
        try:
            bot_id = f"audioreceiver_{channel_id}"

            # Check if already running
            if (
                bot_id in self.bot_processes
                and self.bot_processes[bot_id].is_alive()
            ):
                logger.info(f"AudioReceiver bot {bot_id} is already running")
                return bot_id

            # Get token based on channel number (Channel-1 gets Token-1, Channel-2 gets Token-2, etc.)
            if channel_number > len(self.available_tokens):
                logger.error(f"Channel number {channel_number} exceeds available tokens ({len(self.available_tokens)})")
                return None
                
            token = self.available_tokens[channel_number - 1]  # Channel-1 = index 0
            logger.info(f"Assigned token #{channel_number} to Channel-{channel_number} (bot_id: {bot_id}) in guild {guild_id}")

            # Create bot process
            bot_process = BotProcess(
                bot_id=bot_id,
                bot_type="listener",
                token=token,
                channel_id=channel_id,
                guild_id=guild_id,
            )

            # Add speaker channel ID if provided
            if speaker_channel_id:
                bot_process.speaker_channel_id = speaker_channel_id

            # Start the process
            if bot_process.start():
                self.bot_processes[bot_id] = bot_process
                logger.info(f"Started AudioReceiver bot process: {bot_id}")
                
                # Give the bot a moment to initialize before considering it ready
                await asyncio.sleep(0.5)
                
                # Verify the process is still running
                if not bot_process.is_alive():
                    logger.error(f"AudioReceiver bot process {bot_id} died immediately after startup")
                    del self.bot_processes[bot_id]
                    return None
                
                return bot_id
            else:
                logger.error(f"Failed to start AudioReceiver bot process: {bot_id}")
                return None

        except Exception as e:
            logger.error(f"Error starting AudioReceiver bot: {e}", exc_info=True)
            return None

    async def stop_bot(self, bot_id: str) -> bool:
        """
        Stop a specific bot process and wait for it to fully terminate.

        Args:
            bot_id: Bot ID to stop

        Returns:
            True if successful, False otherwise
        """
        try:
            if bot_id not in self.bot_processes:
                logger.warning(f"Bot process {bot_id} not found")
                return False

            bot_process = self.bot_processes[bot_id]

            # Run the sync stop method in a thread pool to avoid blocking
            logger.info(f"Stopping bot process: {bot_id}")
            success = await asyncio.get_event_loop().run_in_executor(
                None, bot_process.stop
            )
            
            if success:
                # Remove from processes
                del self.bot_processes[bot_id]
                logger.info(f"Successfully stopped and removed bot process: {bot_id}")
                return True
            else:
                logger.error(f"Failed to stop bot process: {bot_id}")
                return False

        except Exception as e:
            logger.error(f"Error stopping bot {bot_id}: {e}", exc_info=True)
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get the status of all bot processes."""
        alive_processes = sum(1 for bp in self.bot_processes.values() if bp.is_alive())
        return {
            "total_processes": len(self.bot_processes),
            "alive_processes": alive_processes,
            "available_tokens": len(self.available_tokens),
            "used_tokens": len(self.used_tokens),
            "processes": {
                bot_id: bot_process.get_status()
                for bot_id, bot_process in self.bot_processes.items()
            },
        }

    def get_bot_status(self, bot_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a specific bot process."""
        if bot_id in self.bot_processes:
            return self.bot_processes[bot_id].get_status()
        return None
