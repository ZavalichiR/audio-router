"""
AudioBroadcast Discord Bot - Main Control Bot for Audio Router System.

This is the main control bot that implements the audio routing system with
a robust multi-bot architecture for handling multiple listener channels.

This file has been refactored to use a modular architecture for better
maintainability and code organization.
"""

import asyncio
import sys
from pathlib import Path

# Ensure src directory is in Python path for direct execution
if __name__ == "__main__":
    src_path = Path(__file__).resolve().parents[3] / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

from discord_audio_router.bots.core import main

if __name__ == "__main__":
    asyncio.run(main())
