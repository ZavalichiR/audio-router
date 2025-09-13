"""
Database operations for subscription management.
"""

import sqlite3
from pathlib import Path
from typing import List, Optional

from .models import ServerSubscription, SubscriptionTier
from discord_audio_router.infrastructure import setup_logging

logger = setup_logging("subscription.database")


class SubscriptionDatabase:
    """Database manager for subscription data."""

    def __init__(self, db_path: str = "data/subscriptions.db"):
        """
        Initialize the subscription database.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _init_database(self):
        """Initialize the database schema."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Create subscriptions table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS subscriptions (
                        invite_code TEXT PRIMARY KEY,
                        server_id TEXT NOT NULL UNIQUE,
                        tier TEXT NOT NULL,
                        max_listeners INTEGER NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Create index on server_id for faster lookups
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_server_id 
                    ON subscriptions(server_id)
                """)

                conn.commit()
                logger.info("Subscription database initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize subscription database: {e}")
            raise

    def get_subscription_by_server_id(
        self, server_id: str
    ) -> Optional[ServerSubscription]:
        """
        Get subscription by Discord server ID.

        Args:
            server_id: Discord server ID

        Returns:
            ServerSubscription or None if not found
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT invite_code, server_id, tier, max_listeners, created_at, updated_at
                    FROM subscriptions 
                    WHERE server_id = ?
                """,
                    (server_id,),
                )

                row = cursor.fetchone()
                if row:
                    return ServerSubscription(
                        invite_code=row[0],
                        server_id=row[1],
                        tier=SubscriptionTier(row[2]),
                        max_listeners=row[3],
                        created_at=row[4],
                        updated_at=row[5],
                    )
                return None

        except Exception as e:
            logger.error(f"Failed to get subscription by server ID {server_id}: {e}")
            return None

    def get_subscription_by_invite_code(
        self, invite_code: str
    ) -> Optional[ServerSubscription]:
        """
        Get subscription by invite code.

        Args:
            invite_code: Discord invite code

        Returns:
            ServerSubscription or None if not found
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT invite_code, server_id, tier, max_listeners, created_at, updated_at
                    FROM subscriptions 
                    WHERE invite_code = ?
                """,
                    (invite_code,),
                )

                row = cursor.fetchone()
                if row:
                    return ServerSubscription(
                        invite_code=row[0],
                        server_id=row[1],
                        tier=SubscriptionTier(row[2]),
                        max_listeners=row[3],
                        created_at=row[4],
                        updated_at=row[5],
                    )
                return None

        except Exception as e:
            logger.error(
                f"Failed to get subscription by invite code {invite_code}: {e}"
            )
            return None

    def create_subscription(self, subscription: ServerSubscription) -> bool:
        """
        Create a new subscription.

        Args:
            subscription: ServerSubscription object

        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO subscriptions (invite_code, server_id, tier, max_listeners)
                    VALUES (?, ?, ?, ?)
                """,
                    (
                        subscription.invite_code,
                        subscription.server_id,
                        subscription.tier.value,
                        subscription.max_listeners,
                    ),
                )
                conn.commit()
                logger.info(f"Created subscription for server {subscription.server_id}")
                return True

        except sqlite3.IntegrityError as e:
            logger.warning(
                f"Subscription already exists for server {subscription.server_id}: {e}"
            )
            return False
        except Exception as e:
            logger.error(f"Failed to create subscription: {e}")
            return False

    def update_subscription(self, subscription: ServerSubscription) -> bool:
        """
        Update an existing subscription.

        Args:
            subscription: ServerSubscription object

        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE subscriptions 
                    SET tier = ?, max_listeners = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE server_id = ?
                """,
                    (
                        subscription.tier.value,
                        subscription.max_listeners,
                        subscription.server_id,
                    ),
                )

                if cursor.rowcount > 0:
                    conn.commit()
                    logger.info(
                        f"Updated subscription for server {subscription.server_id}"
                    )
                    return True
                else:
                    logger.warning(
                        f"No subscription found for server {subscription.server_id}"
                    )
                    return False

        except Exception as e:
            logger.error(f"Failed to update subscription: {e}")
            return False

    def delete_subscription(self, server_id: str) -> bool:
        """
        Delete a subscription.

        Args:
            server_id: Discord server ID

        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM subscriptions WHERE server_id = ?", (server_id,)
                )

                if cursor.rowcount > 0:
                    conn.commit()
                    logger.info(f"Deleted subscription for server {server_id}")
                    return True
                else:
                    logger.warning(f"No subscription found for server {server_id}")
                    return False

        except Exception as e:
            logger.error(f"Failed to delete subscription: {e}")
            return False

    def list_all_subscriptions(self) -> List[ServerSubscription]:
        """
        List all subscriptions.

        Returns:
            List of ServerSubscription objects
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT invite_code, server_id, tier, max_listeners, created_at, updated_at
                    FROM subscriptions 
                    ORDER BY created_at DESC
                """)

                subscriptions = []
                for row in cursor.fetchall():
                    subscriptions.append(
                        ServerSubscription(
                            invite_code=row[0],
                            server_id=row[1],
                            tier=SubscriptionTier(row[2]),
                            max_listeners=row[3],
                            created_at=row[4],
                            updated_at=row[5],
                        )
                    )

                return subscriptions

        except Exception as e:
            logger.error(f"Failed to list subscriptions: {e}")
            return []
