# Discord Audio Router - REST API

This module provides a REST API for managing Discord Audio Router subscriptions using FastAPI.

## Overview

The REST API provides endpoints for:
- Creating and managing server subscriptions
- Validating listener channel limits
- Retrieving subscription information
- Managing subscription tiers

## Features

- **FastAPI-based** REST API with automatic documentation
- **JSON-based** request/response format
- **CORS support** for web applications
- **Error handling** with detailed error messages
- **Auto-generated documentation** at `/docs`

## Quick Start

### 1. Install Dependencies

```bash
pip install fastapi uvicorn pydantic
```

### 2. Start the API Server

```bash
python run_api.py
```

The API will be available at `http://localhost:8000`

### 3. View API Documentation

Visit `http://localhost:8000/docs` for interactive API documentation.

## Python Usage

### Starting the API Server

```python
from discord_audio_router.api.server import run_api_server
import asyncio

async def main():
    await run_api_server(
        host="0.0.0.0",
        port=8000,
        bot_token="your_bot_token",
        db_path="data/subscriptions.db",
        reload=False
    )

asyncio.run(main())
```

### Creating the FastAPI App

```python
from discord_audio_router.api.app import create_app

app = create_app(
    bot_token="your_bot_token",
    db_path="data/subscriptions.db"
)
```

## API Endpoints

### Health Check

#### GET /
Get API information.

**Response:**
```json
{
  "message": "Discord Audio Router API",
  "version": "1.0.0"
}
```

#### GET /health
Health check endpoint.

**Response:**
```json
{
  "status": "healthy"
}
```

### Subscription Management

#### POST /subscriptions
Create a new subscription from an invite code.

**Request:**
```json
{
  "invite_code": "Br7yBkyH",
  "tier": "premium"
}
```

**Response:**
```json
{
  "invite_code": "Br7yBkyH",
  "server_id": "123456789012345678",
  "tier": "premium",
  "max_listeners": 7,
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T12:00:00Z"
}
```

#### GET /subscriptions/{server_id}
Get subscription by server ID.

**Response:**
```json
{
  "invite_code": "Br7yBkyH",
  "server_id": "123456789012345678",
  "tier": "premium",
  "max_listeners": 7,
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T12:00:00Z"
}
```

#### PUT /subscriptions/{server_id}
Update subscription tier.

**Request:**
```json
{
  "invite_code": "Br7yBkyH",
  "tier": "enterprise"
}
```

**Response:**
```json
{
  "invite_code": "Br7yBkyH",
  "server_id": "123456789012345678",
  "tier": "enterprise",
  "max_listeners": 10,
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T12:30:00Z"
}
```

#### DELETE /subscriptions/{server_id}
Delete subscription.

**Response:**
```json
{
  "message": "Subscription deleted successfully"
}
```

#### GET /subscriptions
List all subscriptions.

**Response:**
```json
[
  {
    "invite_code": "Br7yBkyH",
    "server_id": "123456789012345678",
    "tier": "premium",
    "max_listeners": 7,
    "created_at": "2024-01-01T12:00:00Z",
    "updated_at": "2024-01-01T12:00:00Z"
  }
]
```

### Validation

#### POST /validate-listeners
Validate if a server can create the requested number of listener channels.

**Request:**
```json
{
  "server_id": "123456789012345678",
  "requested_count": 5
}
```

**Response:**
```json
{
  "is_valid": true,
  "max_allowed": 7,
  "message": ""
}
```

**Error Response:**
```json
{
  "is_valid": false,
  "max_allowed": 3,
  "message": "❌ Listener Limit Exceeded\n\nYou requested 5 listener channels, but your Basic subscription only allows 3 listener channels.\n\nTo increase your limit:\n• Contact the bot owner zavalichir for assistance\n• Upgrade your subscription via our website (URL TBD)\n• Current tier: Basic (max 3 listeners)"
}
```

### Tier Information

#### GET /tiers
Get available subscription tiers.

**Response:**
```json
[
  {
    "tier": "free",
    "name": "Free",
    "max_listeners": 1,
    "description": "Basic functionality with 1 listener channel"
  },
  {
    "tier": "basic",
    "name": "Basic",
    "max_listeners": 3,
    "description": "Small communities with up to 3 listener channels"
  },
  {
    "tier": "premium",
    "name": "Premium",
    "max_listeners": 7,
    "description": "Medium communities with up to 7 listener channels"
  },
  {
    "tier": "enterprise",
    "name": "Enterprise",
    "max_listeners": 10,
    "description": "Large communities with up to 10 listener channels"
  }
]
```

## cURL Examples

### Create Subscription
```bash
curl -X POST "http://localhost:8000/subscriptions" \
  -H "Content-Type: application/json" \
  -d '{"invite_code": "Br7yBkyH", "tier": "premium"}'
```

### Get Subscription
```bash
curl -X GET "http://localhost:8000/subscriptions/123456789012345678"
```

### Update Subscription
```bash
curl -X PUT "http://localhost:8000/subscriptions/123456789012345678" \
  -H "Content-Type: application/json" \
  -d '{"invite_code": "Br7yBkyH", "tier": "enterprise"}'
```

### Delete Subscription
```bash
curl -X DELETE "http://localhost:8000/subscriptions/123456789012345678"
```

### List All Subscriptions
```bash
curl -X GET "http://localhost:8000/subscriptions"
```

### Validate Listener Count
```bash
curl -X POST "http://localhost:8000/validate-listeners" \
  -H "Content-Type: application/json" \
  -d '{"server_id": "123456789012345678", "requested_count": 5}'
```

### Get Available Tiers
```bash
curl -X GET "http://localhost:8000/tiers"
```

## Python Client Examples

### Using requests

```python
import requests

# Create subscription
response = requests.post("http://localhost:8000/subscriptions", json={
    "invite_code": "Br7yBkyH",
    "tier": "premium"
})
subscription = response.json()

# Get subscription
response = requests.get(f"http://localhost:8000/subscriptions/{subscription['server_id']}")
subscription_data = response.json()

# Validate listener count
response = requests.post("http://localhost:8000/validate-listeners", json={
    "server_id": "123456789012345678",
    "requested_count": 5
})
validation = response.json()

if not validation["is_valid"]:
    print(f"Validation failed: {validation['message']}")
```

### Using httpx (async)

```python
import httpx

async def manage_subscriptions():
    async with httpx.AsyncClient() as client:
        # Create subscription
        response = await client.post("http://localhost:8000/subscriptions", json={
            "invite_code": "Br7yBkyH",
            "tier": "premium"
        })
        subscription = response.json()
        
        # List all subscriptions
        response = await client.get("http://localhost:8000/subscriptions")
        subscriptions = response.json()
        
        for sub in subscriptions:
            print(f"Server {sub['server_id']}: {sub['tier']} tier")
```

## Error Handling

### HTTP Status Codes

- `200 OK`: Request successful
- `400 Bad Request`: Invalid request data
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error

### Error Response Format

```json
{
  "detail": "Error message describing what went wrong"
}
```

### Common Errors

#### Invalid Tier
```json
{
  "detail": "Invalid tier 'invalid'. Valid tiers: ['free', 'basic', 'premium', 'enterprise']"
}
```

#### Subscription Not Found
```json
{
  "detail": "Subscription not found"
}
```

#### Invalid Invite Code
```json
{
  "detail": "Failed to create subscription. The invite code might be invalid or already exists."
}
```

## Configuration

### Environment Variables

- `API_HOST`: Host to bind to (default: 0.0.0.0)
- `API_PORT`: Port to bind to (default: 8000)
- `DISCORD_BOT_TOKEN`: Discord bot token for API calls
- `SUBSCRIPTION_DB_PATH`: Path to subscription database (default: data/subscriptions.db)
- `API_RELOAD`: Enable auto-reload for development (default: false)

### CORS Configuration

The API includes CORS middleware configured for development. For production, update the CORS settings in `app.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # Specific domains
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
```

## Security Considerations

1. **Authentication**: Add authentication middleware for production use
2. **Rate Limiting**: Implement rate limiting to prevent abuse
3. **Input Validation**: All inputs are validated using Pydantic models
4. **CORS**: Configure CORS properly for your domain
5. **HTTPS**: Use HTTPS in production environments

## Development

### Running in Development Mode

```bash
# Enable auto-reload
export API_RELOAD=true
python run_api.py
```

### Testing the API

```bash
# Install test dependencies
pip install pytest httpx

# Run tests (if available)
pytest tests/
```

## Module Structure

```
api/
├── __init__.py      # Module exports
├── app.py          # FastAPI application
├── server.py       # API server runner
└── README.md       # This documentation
```

## Integration with Bot

The API is designed to work alongside the Discord bot. The bot uses the same subscription manager that the API provides, ensuring consistency between the bot's subscription enforcement and the API's management capabilities.

## Support

For API issues:
1. Check the server logs for error details
2. Verify your environment configuration
3. Test endpoints using the interactive docs at `/docs`
4. Contact the bot owner (zavalichir) for assistance
