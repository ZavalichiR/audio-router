# receiver_bot.py
#!/usr/bin/env python3
"""
AudioReceiver Bot Process for Discord Audio Router.

This implementation provides significant latency and performance improvements
through binary WebSocket protocol and buffering.
"""

import asyncio
import sys
from pathlib import Path

# Add src directory to Python path for direct execution
if __name__ == "__main__":
    src_path = Path(__file__).parent.parent.parent.parent / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

from discord_audio_router.bots.receiver_bot import main


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("AudioReceiver bot interrupted")
    except Exception as e:
        print(f"AudioReceiver bot crashed: {e}")
        sys.exit(1)
