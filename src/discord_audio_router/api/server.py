"""
API server runner for subscription management.
"""

import asyncio
import logging
import os
from typing import Optional

import uvicorn

from .app import create_app

logger = logging.getLogger(__name__)


async def run_api_server(
    host: str = "0.0.0.0",
    port: int = 8000,
    bot_token: Optional[str] = None,
    db_path: str = "data/subscriptions.db",
    reload: bool = False,
):
    """
    Run the subscription management API server.

    Args:
        host: Host to bind to
        port: Port to bind to
        bot_token: Discord bot token for API calls
        db_path: Path to the subscription database
        reload: Enable auto-reload for development
    """
    app = create_app(bot_token=bot_token, db_path=db_path)

    config = uvicorn.Config(
        app=app, host=host, port=port, reload=reload, log_level="info"
    )

    server = uvicorn.Server(config)

    logger.info(f"Starting subscription API server on {host}:{port}")
    await server.serve()


def main():
    """Main function to run the API server."""
    # Get configuration from environment variables
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    bot_token = os.getenv("DISCORD_BOT_TOKEN")  # Use main bot token
    db_path = os.getenv("SUBSCRIPTION_DB_PATH", "data/subscriptions.db")
    reload = os.getenv("API_RELOAD", "false").lower() == "true"

    try:
        asyncio.run(
            run_api_server(
                host=host,
                port=port,
                bot_token=bot_token,
                db_path=db_path,
                reload=reload,
            )
        )
    except KeyboardInterrupt:
        logger.info("API server shutdown requested")
    except Exception as e:
        logger.critical(f"Failed to start API server: {e}")
        raise


if __name__ == "__main__":
    main()
