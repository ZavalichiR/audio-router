#!/usr/bin/env python3
"""
Run the subscription management API server.

This script starts the FastAPI server for managing Discord Audio Router subscriptions.
"""

import sys
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from discord_audio_router.api.server import main

if __name__ == "__main__":
    main()
