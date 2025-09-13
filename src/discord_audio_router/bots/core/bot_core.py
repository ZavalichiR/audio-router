"""
Core bot management class for the Discord audio router.

This module provides a centralized way to manage the Discord bot instance,
command registration, and event handling.
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import discord
from discord.ext import commands

from discord_audio_router.bots.commands.base import BaseCommandHandler
from discord_audio_router.config.settings import config_manager
from discord_audio_router.core.audio_router import AudioRouter
from discord_audio_router.infrastructure import setup_logging
from discord_audio_router.bots.commands import (
    BroadcastCommands,
    SetupCommands,
    InfoCommands,
)
from discord_audio_router.bots.handlers import EventHandlers
from discord_audio_router.bots.utils import PermissionUtils
from discord_audio_router.subscription.subscription_manager import SubscriptionManager


class AudioRouterBot:
    """Main bot class that manages the Discord bot and all its components."""

    def __init__(self):
        """Initialize the bot with all necessary components."""
        # Setup logging
        self.logger = setup_logging(
            component_name="main_bot",
            log_file="logs/main_bot.log",
        )

        # Load configuration
        try:
            self.config = config_manager.get_config()
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}", exc_info=True)
            sys.exit(1)

        # Setup Discord bot
        intents = discord.Intents.default()
        intents.voice_states = True
        intents.guilds = True
        intents.members = True
        intents.message_content = True

        self.bot = commands.Bot(
            command_prefix=self.config.command_prefix,
            intents=intents,
            help_command=None,
        )

        # Initialize components
        self.audio_router: Optional[AudioRouter] = None
        self.subscription_manager: Optional[SubscriptionManager] = None
        self.event_handlers: Optional[EventHandlers] = None
        self.command_handlers: dict[str, BaseCommandHandler] = {}

        # Setup event handlers
        self._setup_event_handlers()

        # Setup command handlers
        self._setup_command_handlers()

    def _setup_event_handlers(self) -> None:
        """Setup event handlers for the bot."""
        self.event_handlers = EventHandlers(
            bot=self,
            audio_router=self.audio_router,
            subscription_manager=self.subscription_manager,
            logger=self.logger,
        )

        # Register event handlers
        self.bot.event(self.event_handlers.on_ready)
        self.bot.event(self.event_handlers.on_message)
        self.bot.event(self.event_handlers.on_command_error)

    def _setup_command_handlers(self) -> None:
        """Setup command handlers for the bot."""
        # Initialize command handlers
        self.command_handlers: dict[str, BaseCommandHandler] = {
            "broadcast": BroadcastCommands(
                audio_router=self.audio_router,
                subscription_manager=self.subscription_manager,
                logger=self.logger,
                config=self.config,
            ),
            "setup": SetupCommands(
                audio_router=self.audio_router,
                subscription_manager=self.subscription_manager,
                logger=self.logger,
                config=self.config,
            ),
            "info": InfoCommands(
                audio_router=self.audio_router,
                subscription_manager=self.subscription_manager,
                logger=self.logger,
                config=self.config,
            ),
        }

        # Register commands
        self._register_commands()

    def _register_commands(self) -> None:
        """Register all bot commands."""

        # Create wrapper functions for commands with decorators
        @self.bot.command(name="start_broadcast")
        @PermissionUtils.get_broadcast_admin_decorator(self.audio_router)
        async def start_broadcast_wrapper(ctx, *, args: str):
            broadcast_handler: BroadcastCommands = self.command_handlers["broadcast"]
            await broadcast_handler.start_broadcast_command(ctx, args=args)

        @self.bot.command(name="stop_broadcast")
        @PermissionUtils.get_broadcast_admin_decorator(self.audio_router)
        async def stop_broadcast_wrapper(ctx):
            broadcast_handler: BroadcastCommands = self.command_handlers["broadcast"]
            await broadcast_handler.stop_broadcast_command(ctx)

        @self.bot.command(name="broadcast_status")
        @PermissionUtils.get_broadcast_admin_decorator(self.audio_router)
        async def broadcast_status_wrapper(ctx):
            broadcast_handler: BroadcastCommands = self.command_handlers["broadcast"]
            await broadcast_handler.broadcast_status_command(ctx)

        @self.bot.command(name="setup_roles")
        @PermissionUtils.is_admin()
        async def setup_roles_wrapper(ctx):
            setup_handler: SetupCommands = self.command_handlers["setup"]
            await setup_handler.setup_roles_command(ctx)

        @self.bot.command(name="check_setup")
        async def check_setup_wrapper(ctx):
            setup_handler: SetupCommands = self.command_handlers["setup"]
            await setup_handler.check_setup_command(ctx)

        @self.bot.command(name="check_permissions")
        @PermissionUtils.is_admin()
        async def check_permissions_wrapper(ctx):
            setup_handler: SetupCommands = self.command_handlers["setup"]
            await setup_handler.check_permissions_command(ctx)

        @self.bot.command(name="role_info")
        async def role_info_wrapper(ctx):
            setup_handler: SetupCommands = self.command_handlers["setup"]
            await setup_handler.role_info_command(ctx)

        @self.bot.command(name="help")
        async def help_wrapper(ctx):
            info_handler: InfoCommands = self.command_handlers["info"]
            await info_handler.help_command(ctx)

        @self.bot.command(name="how_it_works")
        async def how_it_works_wrapper(ctx):
            info_handler: InfoCommands = self.command_handlers["info"]
            await info_handler.how_it_works_command(ctx)

        @self.bot.command(name="subscription_status")
        async def subscription_status_wrapper(ctx):
            info_handler: InfoCommands = self.command_handlers["info"]
            await info_handler.subscription_status_command(ctx)

        @self.bot.command(name="bot_status")
        async def bot_status_wrapper(ctx):
            info_handler: InfoCommands = self.command_handlers["info"]
            await info_handler.bot_status_command(ctx)

    def update_components(self, audio_router=None, subscription_manager=None) -> None:
        """Update the audio router and subscription manager instances."""
        if audio_router is not None:
            self.audio_router = audio_router
            # Update all command handlers
            for handler in self.command_handlers.values():
                handler.audio_router = audio_router
            # Update event handlers
            self.event_handlers.audio_router = audio_router

        if subscription_manager is not None:
            self.subscription_manager = subscription_manager
            # Update all command handlers
            for handler in self.command_handlers.values():
                handler.subscription_manager = subscription_manager
            # Update event handlers
            self.event_handlers.subscription_manager = subscription_manager

        # Update config in all command handlers
        for handler in self.command_handlers.values():
            handler.config = self.config

    async def start(self) -> None:
        """Start the bot."""
        try:
            self.logger.info("Starting AudioBroadcast Bot...")
            await self.bot.start(self.config.audio_broadcast_token)
        except Exception as e:
            self.logger.critical(f"Failed to start AudioBroadcast Bot: {e}")
            raise

    async def close(self) -> None:
        """Close the bot and clean up resources."""
        if self.bot:
            await self.bot.close()

    def get_audio_router(self):
        """Get the current audio router instance."""
        return self.audio_router

    def get_subscription_manager(self):
        """Get the current subscription manager instance."""
        return self.subscription_manager


# Global bot instance
_bot_instance: Optional[AudioRouterBot] = None


def get_bot_instance() -> AudioRouterBot:
    """Get the global bot instance."""
    global _bot_instance
    if _bot_instance is None:
        _bot_instance = AudioRouterBot()
    return _bot_instance


async def main():
    """Main function to initialize and run the bot."""
    # Ensure src directory is in Python path for direct execution
    if __name__ == "__main__":
        src_path = Path(__file__).resolve().parents[4] / "src"
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))

    bot = get_bot_instance()

    try:
        await bot.start()
    except KeyboardInterrupt:
        bot.logger.info("Bot shutdown requested")
    except Exception as e:
        bot.logger.critical(f"Fatal error: {e}")
        raise
    finally:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
