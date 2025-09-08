"""
FastAPI application for subscription management.
"""

import logging
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..subscription import SubscriptionManager, SubscriptionTier

logger = logging.getLogger(__name__)


class SubscriptionRequest(BaseModel):
    """Request model for creating/updating subscriptions."""
    invite_code: str
    tier: str


class SubscriptionResponse(BaseModel):
    """Response model for subscription data."""
    invite_code: str
    server_id: str
    tier: str
    max_listeners: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ListenerValidationRequest(BaseModel):
    """Request model for validating listener count."""
    server_id: str
    requested_count: int


class ListenerValidationResponse(BaseModel):
    """Response model for listener validation."""
    is_valid: bool
    max_allowed: int
    message: str


# Global subscription manager instance
subscription_manager: Optional[SubscriptionManager] = None


def get_subscription_manager() -> SubscriptionManager:
    """Dependency to get subscription manager instance."""
    if subscription_manager is None:
        raise HTTPException(status_code=500, detail="Subscription manager not initialized")
    return subscription_manager


def create_app(bot_token: Optional[str] = None, db_path: str = "data/subscriptions.db") -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Args:
        bot_token: Discord bot token for API calls
        db_path: Path to the subscription database
        
    Returns:
        Configured FastAPI application
    """
    global subscription_manager
    
    # Initialize subscription manager
    subscription_manager = SubscriptionManager(db_path=db_path, bot_token=bot_token)
    
    app = FastAPI(
        title="Discord Audio Router API",
        description="REST API for managing Discord Audio Router subscriptions",
        version="1.0.0"
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure this properly for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @app.get("/")
    async def root():
        """Root endpoint."""
        return {"message": "Discord Audio Router API", "version": "1.0.0"}
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy"}
    
    @app.post("/subscriptions", response_model=SubscriptionResponse)
    async def create_subscription(
        request: SubscriptionRequest,
        manager: SubscriptionManager = Depends(get_subscription_manager)
    ):
        """
        Create or update a subscription from an invite code.
        
        Args:
            request: Subscription request with invite code and tier
            manager: Subscription manager dependency
            
        Returns:
            Created subscription data
        """
        try:
            # Validate tier
            try:
                tier = SubscriptionTier(request.tier.lower())
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid tier '{request.tier}'. Valid tiers: {[t.value for t in SubscriptionTier]}"
                )
            
            # Create subscription
            success = await manager.create_subscription_from_invite(request.invite_code, tier)
            if not success:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to create subscription. The invite code might be invalid or already exists."
                )
            
            # Get the created subscription
            server_id = await manager.discord_api.get_server_id_from_invite(request.invite_code)
            if not server_id:
                raise HTTPException(status_code=500, detail="Failed to resolve server ID")
            
            subscription = manager.get_server_subscription(server_id)
            if not subscription:
                raise HTTPException(status_code=500, detail="Subscription not found after creation")
            
            return SubscriptionResponse(
                invite_code=subscription.invite_code,
                server_id=subscription.server_id,
                tier=subscription.tier.value,
                max_listeners=subscription.max_listeners,
                created_at=subscription.created_at,
                updated_at=subscription.updated_at
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating subscription: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")
    
    @app.get("/subscriptions/{server_id}", response_model=SubscriptionResponse)
    async def get_subscription(
        server_id: str,
        manager: SubscriptionManager = Depends(get_subscription_manager)
    ):
        """
        Get subscription by server ID.
        
        Args:
            server_id: Discord server ID
            manager: Subscription manager dependency
            
        Returns:
            Subscription data
        """
        subscription = manager.get_server_subscription(server_id)
        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")
        
        return SubscriptionResponse(
            invite_code=subscription.invite_code,
            server_id=subscription.server_id,
            tier=subscription.tier.value,
            max_listeners=subscription.max_listeners,
            created_at=subscription.created_at,
            updated_at=subscription.updated_at
        )
    
    @app.put("/subscriptions/{server_id}", response_model=SubscriptionResponse)
    async def update_subscription(
        server_id: str,
        request: SubscriptionRequest,
        manager: SubscriptionManager = Depends(get_subscription_manager)
    ):
        """
        Update subscription tier.
        
        Args:
            server_id: Discord server ID
            request: Subscription request with new tier
            manager: Subscription manager dependency
            
        Returns:
            Updated subscription data
        """
        try:
            # Validate tier
            try:
                tier = SubscriptionTier(request.tier.lower())
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid tier '{request.tier}'. Valid tiers: {[t.value for t in SubscriptionTier]}"
                )
            
            # Update subscription
            success = manager.update_server_subscription(server_id, tier)
            if not success:
                raise HTTPException(status_code=404, detail="Subscription not found")
            
            # Get updated subscription
            subscription = manager.get_server_subscription(server_id)
            if not subscription:
                raise HTTPException(status_code=500, detail="Subscription not found after update")
            
            return SubscriptionResponse(
                invite_code=subscription.invite_code,
                server_id=subscription.server_id,
                tier=subscription.tier.value,
                max_listeners=subscription.max_listeners,
                created_at=subscription.created_at,
                updated_at=subscription.updated_at
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating subscription: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")
    
    @app.delete("/subscriptions/{server_id}")
    async def delete_subscription(
        server_id: str,
        manager: SubscriptionManager = Depends(get_subscription_manager)
    ):
        """
        Delete subscription.
        
        Args:
            server_id: Discord server ID
            manager: Subscription manager dependency
            
        Returns:
            Success message
        """
        success = manager.delete_server_subscription(server_id)
        if not success:
            raise HTTPException(status_code=404, detail="Subscription not found")
        
        return {"message": "Subscription deleted successfully"}
    
    @app.get("/subscriptions")
    async def list_subscriptions(
        manager: SubscriptionManager = Depends(get_subscription_manager)
    ):
        """
        List all subscriptions.
        
        Args:
            manager: Subscription manager dependency
            
        Returns:
            List of all subscriptions
        """
        subscriptions = manager.list_all_subscriptions()
        return [
            SubscriptionResponse(
                invite_code=sub.invite_code,
                server_id=sub.server_id,
                tier=sub.tier.value,
                max_listeners=sub.max_listeners,
                created_at=sub.created_at,
                updated_at=sub.updated_at
            )
            for sub in subscriptions
        ]
    
    @app.post("/validate-listeners", response_model=ListenerValidationResponse)
    async def validate_listener_count(
        request: ListenerValidationRequest,
        manager: SubscriptionManager = Depends(get_subscription_manager)
    ):
        """
        Validate if a server can create the requested number of listener channels.
        
        Args:
            request: Validation request with server ID and requested count
            manager: Subscription manager dependency
            
        Returns:
            Validation result
        """
        is_valid, max_allowed, message = manager.validate_listener_count(
            request.server_id, request.requested_count
        )
        
        return ListenerValidationResponse(
            is_valid=is_valid,
            max_allowed=max_allowed,
            message=message
        )
    
    @app.get("/tiers")
    async def get_subscription_tiers():
        """
        Get available subscription tiers.
        
        Returns:
            List of available subscription tiers
        """
        from ..subscription.models import SUBSCRIPTION_TIERS
        
        return [
            {
                "tier": tier.value,
                "name": info["name"],
                "max_listeners": info["max_listeners"],
                "description": info["description"]
            }
            for tier, info in SUBSCRIPTION_TIERS.items()
        ]
    
    return app
