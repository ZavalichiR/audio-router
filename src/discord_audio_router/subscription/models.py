"""
Subscription data models for Discord Audio Router.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class SubscriptionTier(Enum):
    """Subscription tier enumeration."""
    FREE = "free"
    BASIC = "basic"
    STANDARD = "standard"
    ADVANCED = "advanced"
    PREMIUM = "premium"
    CUSTOM = "custom"


@dataclass
class ServerSubscription:
    """Server subscription data model."""
    invite_code: str
    server_id: str
    tier: SubscriptionTier
    max_listeners: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# Subscription tier configurations
# Note: For website/UI - request channels: Free/Basic/Standard=discord, Advanced/Premium=email, Custom=dm
# Note: For website/UI - descriptions: Free=Basic functionality, Basic=Trial tier, Standard=Small communities, Advanced=Medium communities, Premium=Large communities, Custom=Custom features
SUBSCRIPTION_TIERS = {
    SubscriptionTier.FREE: {
        "name": "Free",
        "max_listeners": 1
    },
    SubscriptionTier.BASIC: {
        "name": "Basic",
        "max_listeners": 2
    },
    SubscriptionTier.STANDARD: {
        "name": "Standard",
        "max_listeners": 6
    },
    SubscriptionTier.ADVANCED: {
        "name": "Advanced",
        "max_listeners": 12
    },
    SubscriptionTier.PREMIUM: {
        "name": "Premium",
        "max_listeners": 24
    },
    SubscriptionTier.CUSTOM: {
        "name": "Custom",
        "max_listeners": 0  # unlimited or negotiated per-server
    },
}
