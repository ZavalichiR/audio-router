"""
Process Manager for Discord Audio Router Bot.

This module manages separate processes for each Discord bot instance,
enabling true multi-channel audio with process isolation.
"""

import asyncio
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


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
                    self.process.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    # Force kill if graceful shutdown fails
                    logger.warning(f"Force killing bot process {self.bot_id}")
                    self.process.kill()
                    self.process.wait()

            self.is_running = False
            self.pid = None

            logger.info(f"Stopped bot process {self.bot_id}")
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


class ProcessManager:
    """
    Manages multiple Discord bot processes.

    This manager spawns and manages separate processes for each bot,
    enabling true multi-channel audio with process isolation.
    """

    def __init__(self, config):
        """
        Initialize the process manager.

        Args:
            config: Bot configuration
        """
        self.config = config
        self.bot_processes: Dict[str, BotProcess] = {}
        self.available_tokens: List[str] = []
        self.used_tokens: set = set()

    def add_available_tokens(self, tokens: List[str]):
        """Add available bot tokens."""
        self.available_tokens.extend(tokens)
        logger.info(f"Added {len(tokens)} available bot tokens")

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
        self, channel_id: int, guild_id: int, speaker_channel_id: int = None
    ) -> Optional[str]:
        """
        Start a listener bot process.

        Args:
            channel_id: Listener channel ID
            guild_id: Guild ID
            speaker_channel_id: Speaker channel ID (for WebSocket connection)

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

            # Get available token
            if not self.available_tokens:
                logger.error("No available tokens for AudioReceiver bot")
                return None

            # Use the first available token (this ensures consistent assignment order)
            # The tokens should be assigned in the order they appear in the configuration
            token = self.available_tokens.pop(0)
            self.used_tokens.add(token)
            
            logger.info(f"Assigned token to channel {channel_id} (bot_id: {bot_id})")

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
                return bot_id
            else:
                # Return token to available list if startup failed
                self.available_tokens.insert(0, token)
                self.used_tokens.discard(token)
                logger.error(
                    f"Failed to start AudioReceiver bot process: {bot_id}"
                )
                return None

        except Exception as e:
            logger.error(f"Error starting AudioReceiver bot: {e}", exc_info=True)
            return None

    async def stop_bot(self, bot_id: str) -> bool:
        """
        Stop a specific bot process.

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

            # Stop the process
            if bot_process.stop():
                # Return token to available list if it's a listener bot
                if bot_process.bot_type == "listener":
                    self.available_tokens.append(bot_process.token)
                    self.used_tokens.discard(bot_process.token)

                # Remove from processes
                del self.bot_processes[bot_id]
                logger.info(f"Stopped bot process: {bot_id}")
                return True
            else:
                logger.error(f"Failed to stop bot process: {bot_id}")
                return False

        except Exception as e:
            logger.error(f"Error stopping bot {bot_id}: {e}", exc_info=True)
            return False

    async def stop_all_bots(self) -> bool:
        """Stop all bot processes."""
        try:
            success = True
            bot_ids = list(self.bot_processes.keys())

            for bot_id in bot_ids:
                if not await self.stop_bot(bot_id):
                    success = False

            logger.info("Stopped all bot processes")
            return success

        except Exception as e:
            logger.error(f"Error stopping all bots: {e}", exc_info=True)
            return False

    async def stop_bots_by_guild(self, guild_id: int) -> bool:
        """
        Stop all bot processes for a specific guild.

        Args:
            guild_id: Guild ID

        Returns:
            True if successful, False otherwise
        """
        try:
            success = True
            bot_ids = [
                bot_id
                for bot_id, bot_process in self.bot_processes.items()
                if bot_process.guild_id == guild_id
            ]

            for bot_id in bot_ids:
                if not await self.stop_bot(bot_id):
                    success = False

            logger.info(f"Stopped all bot processes for guild {guild_id}")
            return success

        except Exception as e:
            logger.error(f"Error stopping bots for guild {guild_id}: {e}", exc_info=True)
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get the status of all bot processes."""
        return {
            "total_processes": len(self.bot_processes),
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

    def cleanup(self):
        """Clean up all resources."""
        try:
            # Stop all processes
            asyncio.create_task(self.stop_all_bots())
            logger.info("Process manager cleaned up")
        except Exception as e:
            logger.error(f"Error during process manager cleanup: {e}", exc_info=True)
