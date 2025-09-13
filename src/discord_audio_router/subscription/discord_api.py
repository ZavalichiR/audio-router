"""
Discord API utilities for subscription management.
"""

import aiohttp
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class DiscordAPI:
    """Discord API client for subscription management."""

    def __init__(self, bot_token: Optional[str] = None):
        """
        Initialize Discord API client.

        Args:
            bot_token: Optional bot token for authenticated requests
        """
        self.bot_token = bot_token
        self.base_url = "https://discord.com/api/v10"

    async def get_invite_info(self, invite_code: str) -> Optional[Dict[str, Any]]:
        """
        Get invite information from Discord API.

        Args:
            invite_code: Discord invite code (e.g., 'Br7yBkyH')

        Returns:
            Dict with invite information or None if failed
        """
        try:
            url = f"{self.base_url}/invites/{invite_code}"
            headers = {}

            # Add authorization header if bot token is available
            if self.bot_token:
                headers["Authorization"] = f"Bot {self.bot_token}"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Retrieved invite info for {invite_code}")
                        return data
                    elif response.status == 404:
                        logger.warning(f"Invite code {invite_code} not found")
                        return None
                    else:
                        logger.error(
                            f"Failed to get invite info: {response.status} - {await response.text()}"
                        )
                        return None

        except Exception as e:
            logger.error(f"Error getting invite info for {invite_code}: {e}")
            return None

    async def get_server_id_from_invite(self, invite_code: str) -> Optional[str]:
        """
        Get Discord server ID from invite code.

        Args:
            invite_code: Discord invite code

        Returns:
            Server ID as string or None if failed
        """
        invite_info = await self.get_invite_info(invite_code)
        if invite_info and "guild" in invite_info:
            server_id = invite_info["guild"]["id"]
            logger.info(f"Resolved invite {invite_code} to server ID {server_id}")
            return server_id

        return None

    async def get_server_info(self, server_id: str) -> Optional[Dict[str, Any]]:
        """
        Get server information from Discord API.

        Args:
            server_id: Discord server ID

        Returns:
            Dict with server information or None if failed
        """
        if not self.bot_token:
            logger.warning("Bot token required for server info requests")
            return None

        try:
            url = f"{self.base_url}/guilds/{server_id}"
            headers = {"Authorization": f"Bot {self.bot_token}"}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Retrieved server info for {server_id}")
                        return data
                    elif response.status == 404:
                        logger.warning(f"Server {server_id} not found")
                        return None
                    else:
                        logger.error(
                            f"Failed to get server info: {response.status} - {await response.text()}"
                        )
                        return None

        except Exception as e:
            logger.error(f"Error getting server info for {server_id}: {e}")
            return None
