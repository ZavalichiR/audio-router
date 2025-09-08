# Discord Audio Router - Subscription System

This module provides subscription management for the Discord Audio Router bot, allowing you to monetize the bot by offering different tiers with varying listener channel limits.

## Overview

The subscription system provides:
- **Free Tier**: 1 listener channel (default for all servers)
- **Basic Tier**: 2 listener channels (trial tier)
- **Standard Tier**: 6 listener channels
- **Advanced Tier**: 12 listener channels
- **Premium Tier**: 24 listener channels
- **Custom Tier**: Unlimited listeners (uses all available receiver bots)

## Features

### 1. Subscription Management
- Database-backed subscription storage using SQLite
- Discord invite code to server ID resolution
- REST API for subscription management
- CLI tool for manual subscription management

### 2. Bot Integration
- Automatic listener limit enforcement
- Improved error messages with upgrade prompts
- Subscription status checking command
- Fallback to free tier for unregistered servers

### 3. API Endpoints
- Create/update subscriptions via invite code
- List all subscriptions
- Validate listener counts
- Get subscription tiers information

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up Environment

Add to your `.env` file:
```env
# Optional: Start the subscription API server
START_SUBSCRIPTION_API=true
API_HOST=0.0.0.0
API_PORT=8000
SUBSCRIPTION_DB_PATH=data/subscriptions.db
```

### 3. Run the Bot

The bot will automatically initialize the subscription system:
```bash
python launcher.py
```

### 4. Create a Subscription

Using the CLI tool:
```bash
python manage_subscriptions.py create Br7yBkyH premium
```

Or using the REST API:
```bash
curl -X POST "http://localhost:8000/subscriptions" \
  -H "Content-Type: application/json" \
  -d '{"invite_code": "Br7yBkyH", "tier": "premium"}'
```

## Python Usage

### Basic Usage

```python
from discord_audio_router.subscription import SubscriptionManager, SubscriptionTier

# Initialize the subscription manager
manager = SubscriptionManager(
    db_path="data/subscriptions.db",
    bot_token="your_bot_token_here"
)

# Create a subscription from invite code
await manager.create_subscription_from_invite("Br7yBkyH", SubscriptionTier.PREMIUM)

# Get server subscription
subscription = manager.get_server_subscription("123456789012345678")
if subscription:
    print(f"Server has {subscription.tier.value} tier with {subscription.max_listeners} listeners")

# Check listener limits
is_valid, max_allowed, message = manager.validate_listener_count("123456789012345678", 5)
if not is_valid:
    print(f"Limit exceeded: {message}")

# Update subscription tier
manager.update_server_subscription("123456789012345678", SubscriptionTier.ENTERPRISE)

# Delete subscription
manager.delete_server_subscription("123456789012345678")
```

### Advanced Usage

```python
# List all subscriptions
subscriptions = manager.list_all_subscriptions()
for sub in subscriptions:
    print(f"Server {sub.server_id}: {sub.tier.value} ({sub.max_listeners} listeners)")

# Get tier information
tier_info = manager.get_tier_info(SubscriptionTier.PREMIUM)
print(f"Premium tier allows {tier_info['max_listeners']} listeners")

# Get max listeners for a tier
max_listeners = manager.get_max_listeners_for_tier(SubscriptionTier.BASIC)
print(f"Basic tier allows {max_listeners} listeners")
```

## CLI Commands

### List All Subscriptions
```bash
python manage_subscriptions.py list
```

### Get Subscription by Invite Code
```bash
python manage_subscriptions.py get Br7yBkyH
```

### Create Subscription
```bash
python manage_subscriptions.py create Br7yBkyH premium
```

### Update Subscription Tier
```bash
python manage_subscriptions.py update Br7yBkyH custom
```

### Delete Subscription
```bash
python manage_subscriptions.py delete Br7yBkyH
```

### Show Available Tiers
```bash
python manage_subscriptions.py tiers
```

### CLI with Custom Database Path
```bash
python manage_subscriptions.py --db-path /custom/path/subscriptions.db list
```

### CLI with Bot Token
```bash
python manage_subscriptions.py --bot-token YOUR_BOT_TOKEN create Br7yBkyH basic
```

### CLI Examples with Invite Codes
```bash
# Create a premium subscription
python manage_subscriptions.py create Br7yBkyH premium

# Get subscription details
python manage_subscriptions.py get Br7yBkyH

# Update to custom tier (unlimited)
python manage_subscriptions.py update Br7yBkyH custom

# Delete subscription
python manage_subscriptions.py delete Br7yBkyH
```

## Bot Commands

### Check Subscription Status
```
!subscription_status
```
Shows the current subscription tier, listener limits, and available upgrade options.

### Start Broadcast with Limits
```
!start_broadcast 'My Event' 5
```
- If the server has a subscription allowing 5+ listeners: Creates 5 listener channels
- If the server has a lower tier (e.g., Basic with 3 listeners): Creates 3 channels and shows an info message
- If the server exceeds limits: Shows upgrade prompt with contact information

## Database Schema

The subscription system uses SQLite with the following schema:

```sql
CREATE TABLE subscriptions (
    invite_code TEXT PRIMARY KEY,
    server_id TEXT NOT NULL UNIQUE,
    tier TEXT NOT NULL,
    max_listeners INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Subscription Tiers

| Tier | Max Listeners |
|------|---------------|
| Free | 1 |
| Basic | 2 |
| Standard | 6 |
| Advanced | 12 |
| Premium | 24 |
| Custom | 0 (unlimited) |

## Error Messages

When users exceed their subscription limits, they see a professional error message:

```
❌ Listener Limit Exceeded

You requested 5 listener channels, but your Free subscription only allows 1 listener channel.

To increase your limit:
• Contact the bot owner zavalichir for assistance
• Upgrade your subscription via our website (URL TBD)
• Current tier: Free (max 1 listener)
```

## Module Structure

```
subscription/
├── __init__.py              # Module exports
├── models.py                # Data models and tier definitions
├── database.py              # SQLite database operations
├── discord_api.py           # Discord API integration
├── subscription_manager.py  # Main subscription logic
└── README.md               # This documentation
```

## Configuration

### Environment Variables

- `START_SUBSCRIPTION_API`: Enable/disable the REST API server
- `API_HOST`: API server host (default: 0.0.0.0)
- `API_PORT`: API server port (default: 8000)
- `SUBSCRIPTION_DB_PATH`: Path to SQLite database (default: data/subscriptions.db)
- `API_RELOAD`: Enable auto-reload for development (default: false)

### Bot Token

The subscription system uses the main bot token (`AUDIO_BROADCAST_TOKEN`) for Discord API calls to resolve invite codes to server IDs.

## Security Considerations

1. **API Security**: The REST API currently has no authentication. Add authentication for production use.
2. **CORS**: Configure CORS properly for production environments.
3. **Database**: The SQLite database is stored locally. Consider using a more robust database for production.
4. **Rate Limiting**: Add rate limiting to prevent abuse of the Discord API.

## Troubleshooting

### Common Issues

1. **"Subscription manager not initialized"**
   - Ensure the bot token is valid
   - Check that the database directory exists and is writable

2. **"Could not resolve invite code to server ID"**
   - Verify the invite code is valid and not expired
   - Ensure the bot has access to the server

3. **"Failed to create subscription"**
   - Check if a subscription already exists for the server
   - Verify the invite code is correct

### Debug Mode

Enable debug logging to see detailed subscription system logs:
```env
LOG_LEVEL=DEBUG
```

## Future Enhancements

1. **Web Dashboard**: Create a web interface for subscription management
2. **Payment Integration**: Add payment processing for automatic upgrades
3. **Usage Analytics**: Track usage patterns and listener channel utilization
4. **Trial Periods**: Implement trial periods for new subscriptions
5. **Bulk Management**: Add bulk subscription management features

## Support

For issues with the subscription system:
1. Check the logs in `logs/main_bot.log`
2. Verify your environment configuration
3. Test with the CLI tool: `python manage_subscriptions.py list`
4. Contact the bot owner (zavalichir) for assistance
