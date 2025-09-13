"""
Subscription manager for Discord Audio Router.

This module provides the main interface for managing subscription tiers
and determining listener limits based on server subscriptions.
"""

import logging
from typing import Optional

from .database import SubscriptionDatabase
from .discord_api import DiscordAPI
from .models import ServerSubscription, SubscriptionTier, SUBSCRIPTION_TIERS

logger = logging.getLogger(__name__)


class SubscriptionManager:
    """Main subscription manager class."""

    def __init__(
        self, db_path: str = "data/subscriptions.db", bot_token: Optional[str] = None
    ):
        """
        Initialize the subscription manager.

        Args:
            db_path: Path to the SQLite database file
            bot_token: Optional bot token for Discord API calls
        """
        self.database = SubscriptionDatabase(db_path)
        self.discord_api = DiscordAPI(bot_token)

    def get_max_listeners_for_tier(self, tier: SubscriptionTier) -> int:
        """
        Get maximum listeners allowed for a subscription tier.

        Args:
            tier: Subscription tier

        Returns:
            Maximum number of listeners allowed
        """
        return SUBSCRIPTION_TIERS[tier]["max_listeners"]

    def get_tier_info(self, tier: SubscriptionTier) -> dict:
        """
        Get information about a subscription tier.

        Args:
            tier: Subscription tier

        Returns:
            Dict with tier information
        """
        return SUBSCRIPTION_TIERS[tier]

    def get_server_max_listeners(self, server_id: str) -> int:
        """
        Get maximum listeners allowed for a server.

        Args:
            server_id: Discord server ID

        Returns:
            Maximum number of listeners allowed (defaults to free tier if not found)
            Returns 0 for CUSTOM tier (unlimited - use all available receiver bots)
        """
        subscription = self.database.get_subscription_by_server_id(server_id)
        if subscription:
            # CUSTOM tier with 0 listeners means unlimited (use all available receiver bots)
            if (
                subscription.tier == SubscriptionTier.CUSTOM
                and subscription.max_listeners == 0
            ):
                return 0  # Special value indicating unlimited
            return subscription.max_listeners

        # Default to free tier if no subscription found
        logger.info(f"No subscription found for server {server_id}, using free tier")
        return self.get_max_listeners_for_tier(SubscriptionTier.FREE)

    def get_server_subscription(self, server_id: str) -> Optional[ServerSubscription]:
        """
        Get server subscription information.

        Args:
            server_id: Discord server ID

        Returns:
            ServerSubscription or None if not found
        """
        return self.database.get_subscription_by_server_id(server_id)

    def get_subscription_by_invite(
        self, invite_code: str
    ) -> Optional[ServerSubscription]:
        """
        Get subscription information by invite code.

        Args:
            invite_code: Discord invite code

        Returns:
            ServerSubscription or None if not found
        """
        return self.database.get_subscription_by_invite_code(invite_code)

    async def create_subscription_from_invite(
        self, invite_code: str, tier: SubscriptionTier
    ) -> bool:
        """
        Create a subscription from an invite code.

        Args:
            invite_code: Discord invite code
            tier: Subscription tier

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get server ID from invite code
            server_id = await self.discord_api.get_server_id_from_invite(invite_code)
            if not server_id:
                logger.error(
                    f"Could not resolve invite code {invite_code} to server ID"
                )
                return False

            # Create subscription
            tier_info = self.get_tier_info(tier)
            max_listeners = tier_info["max_listeners"]

            subscription = ServerSubscription(
                invite_code=invite_code,
                server_id=server_id,
                tier=tier,
                max_listeners=max_listeners,
            )

            # Check if subscription already exists
            existing = self.database.get_subscription_by_server_id(server_id)
            if existing:
                # Update existing subscription
                existing.tier = tier
                existing.max_listeners = max_listeners
                return self.database.update_subscription(existing)
            else:
                # Create new subscription
                return self.database.create_subscription(subscription)

        except Exception as e:
            logger.error(
                f"Failed to create subscription from invite {invite_code}: {e}"
            )
            return False

    def update_server_subscription(
        self, server_id: str, tier: SubscriptionTier
    ) -> bool:
        """
        Update server subscription tier.

        Args:
            server_id: Discord server ID
            tier: New subscription tier

        Returns:
            True if successful, False otherwise
        """
        try:
            subscription = self.database.get_subscription_by_server_id(server_id)
            if not subscription:
                logger.warning(f"No subscription found for server {server_id}")
                return False

            tier_info = self.get_tier_info(tier)
            subscription.tier = tier
            subscription.max_listeners = tier_info["max_listeners"]

            return self.database.update_subscription(subscription)

        except Exception as e:
            logger.error(f"Failed to update subscription for server {server_id}: {e}")
            return False

    def update_subscription_by_invite(
        self, invite_code: str, tier: SubscriptionTier
    ) -> bool:
        """
        Update subscription tier by invite code.

        Args:
            invite_code: Discord invite code
            tier: New subscription tier

        Returns:
            True if successful, False otherwise
        """
        try:
            subscription = self.database.get_subscription_by_invite_code(invite_code)
            if not subscription:
                logger.warning(f"No subscription found for invite code {invite_code}")
                return False

            tier_info = self.get_tier_info(tier)
            subscription.tier = tier
            subscription.max_listeners = tier_info["max_listeners"]

            return self.database.update_subscription(subscription)

        except Exception as e:
            logger.error(
                f"Failed to update subscription for invite code {invite_code}: {e}"
            )
            return False

    def delete_server_subscription(self, server_id: str) -> bool:
        """
        Delete server subscription.

        Args:
            server_id: Discord server ID

        Returns:
            True if successful, False otherwise
        """
        return self.database.delete_subscription(server_id)

    def delete_subscription_by_invite(self, invite_code: str) -> bool:
        """
        Delete subscription by invite code.

        Args:
            invite_code: Discord invite code

        Returns:
            True if successful, False otherwise
        """
        try:
            subscription = self.database.get_subscription_by_invite_code(invite_code)
            if not subscription:
                logger.warning(f"No subscription found for invite code {invite_code}")
                return False

            return self.database.delete_subscription(subscription.server_id)

        except Exception as e:
            logger.error(
                f"Failed to delete subscription for invite code {invite_code}: {e}"
            )
            return False

    def list_all_subscriptions(self):
        """
        List all subscriptions.

        Returns:
            List of ServerSubscription objects
        """
        return self.database.list_all_subscriptions()

    def validate_listener_count(
        self, server_id: str, requested_count: int
    ) -> tuple[bool, int, str]:
        """
        Validate if a server can create the requested number of listener channels.

        Args:
            server_id: Discord server ID
            requested_count: Number of listener channels requested

        Returns:
            Tuple of (is_valid, max_allowed, message)
        """
        max_allowed = self.get_server_max_listeners(server_id)

        # CUSTOM tier with 0 listeners means unlimited (use all available receiver bots)
        if max_allowed == 0:
            return True, 0, ""  # Unlimited - always valid

        if requested_count <= max_allowed:
            return True, max_allowed, ""

        # Get subscription info for better error message
        subscription = self.get_server_subscription(server_id)
        if subscription:
            tier_info = self.get_tier_info(subscription.tier)
            tier_name = tier_info["name"]
        else:
            tier_name = "Free"

        message = (
            f"❌ **Listener Limit Exceeded**\n\n"
            f"You requested **{requested_count}** listener channels, but your **{tier_name}** "
            f"subscription only allows **{max_allowed}** listener channel{'s' if max_allowed != 1 else ''}.\n\n"
            f"**To increase your limit:**\n"
            f"• Contact the bot owner **zavalichir** for assistance\n"
            f"• Upgrade your subscription via our website (URL TBD)\n"
            f"• Current tier: **{tier_name}** (max {max_allowed} listener{'s' if max_allowed != 1 else ''})"
        )

        return False, max_allowed, message
