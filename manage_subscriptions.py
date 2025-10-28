#!/usr/bin/env python3
"""
CLI tool for managing Discord Audio Router subscriptions.

This script provides a command-line interface for managing server subscriptions.
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from discord_audio_router.subscription import SubscriptionManager, SubscriptionTier

async def create_subscription(
    manager: SubscriptionManager, invite_code: str, tier: str
):
    """Create a new subscription."""
    try:
        tier_enum = SubscriptionTier(tier.lower())
        success = await manager.create_subscription_from_invite(invite_code, tier_enum)
        if success:
            print(f"✅ Created {tier} subscription for invite code {invite_code}")
        else:
            print(f"❌ Failed to create subscription for invite code {invite_code}")
    except ValueError:
        print(
            f"❌ Invalid tier '{tier}'. Valid tiers: {[t.value for t in SubscriptionTier]}"
        )


def list_subscriptions(manager: SubscriptionManager):
    """List all subscriptions."""
    subscriptions = manager.list_all_subscriptions()
    if not subscriptions:
        print("No subscriptions found.")
        return

    print(f"Found {len(subscriptions)} subscription(s):")
    print("-" * 80)
    for sub in subscriptions:
        print(f"Server ID: {sub.server_id}")
        print(f"Invite Code: {sub.invite_code}")
        print(f"Tier: {sub.tier.value.title()}")
        print(f"Max Listeners: {sub.max_listeners}")
        print(f"Created: {sub.created_at or 'Unknown'}")
        print("-" * 80)


def get_subscription(manager: SubscriptionManager, invite_code: str):
    """Get subscription by invite code."""
    subscription = manager.get_subscription_by_invite(invite_code)
    if subscription:
        print(f"Server ID: {subscription.server_id}")
        print(f"Invite Code: {subscription.invite_code}")
        print(f"Tier: {subscription.tier.value.title()}")
        print(f"Max Listeners: {subscription.max_listeners}")
        print(f"Created: {subscription.created_at or 'Unknown'}")
        print(f"Updated: {subscription.updated_at or 'Unknown'}")
    else:
        print(f"No subscription found for invite code {invite_code}")


def update_subscription(manager: SubscriptionManager, invite_code: str, tier: str):
    """Update subscription tier."""
    try:
        tier_enum = SubscriptionTier(tier.lower())
        success = manager.update_subscription_by_invite(invite_code, tier_enum)
        if success:
            print(f"✅ Updated subscription for invite code {invite_code} to {tier}")
        else:
            print(f"❌ Failed to update subscription for invite code {invite_code}")
    except ValueError:
        print(
            f"❌ Invalid tier '{tier}'. Valid tiers: {[t.value for t in SubscriptionTier]}"
        )


def delete_subscription(manager: SubscriptionManager, invite_code: str):
    """Delete subscription."""
    success = manager.delete_subscription_by_invite(invite_code)
    if success:
        print(f"✅ Deleted subscription for invite code {invite_code}")
    else:
        print(f"❌ Failed to delete subscription for invite code {invite_code}")


def show_tiers():
    """Show available subscription tiers."""
    from discord_audio_router.subscription.models import SUBSCRIPTION_TIERS

    print("Available subscription tiers:")
    print("-" * 80)
    for tier, info in SUBSCRIPTION_TIERS.items():
        listeners_text = (
            "unlimited"
            if info["max_listeners"] == 0
            else f"{info['max_listeners']} listeners"
        )
        print(f"{tier.value.title()}: {listeners_text}")
        print("-" * 80)


async def main():
    """Main CLI function."""
    parser = argparse.ArgumentParser(
        description="Manage Discord Audio Router subscriptions"
    )
    parser.add_argument(
        "--db-path",
        default="data/subscriptions.db",
        help="Path to subscription database",
    )
    parser.add_argument("--bot-token", help="Discord bot token for API calls")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Create subscription
    create_parser = subparsers.add_parser("create", help="Create a new subscription")
    create_parser.add_argument("invite_code", help="Discord invite code")
    create_parser.add_argument(
        "tier",
        help="Subscription tier (free, basic, standard, advanced, premium, custom)",
    )

    # List subscriptions
    subparsers.add_parser("list", help="List all subscriptions")

    # Get subscription
    get_parser = subparsers.add_parser("get", help="Get subscription by invite code")
    get_parser.add_argument("invite_code", help="Discord invite code")

    # Update subscription
    update_parser = subparsers.add_parser("update", help="Update subscription tier")
    update_parser.add_argument("invite_code", help="Discord invite code")
    update_parser.add_argument(
        "tier",
        help="New subscription tier (free, basic, standard, advanced, premium, custom)",
    )

    # Delete subscription
    delete_parser = subparsers.add_parser("delete", help="Delete subscription")
    delete_parser.add_argument("invite_code", help="Discord invite code")

    # Show tiers
    subparsers.add_parser("tiers", help="Show available subscription tiers")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == "tiers":
        show_tiers()
        return

    # Initialize subscription manager
    manager = SubscriptionManager(db_path=args.db_path, bot_token=args.bot_token)

    if args.command == "create":
        await create_subscription(manager, args.invite_code, args.tier)
    elif args.command == "list":
        list_subscriptions(manager)
    elif args.command == "get":
        get_subscription(manager, args.invite_code)
    elif args.command == "update":
        update_subscription(manager, args.invite_code, args.tier)
    elif args.command == "delete":
        delete_subscription(manager, args.invite_code)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nOperation cancelled")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
