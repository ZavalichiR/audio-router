# Discord Audio Router - Developer Documentation

A professional-grade Discord bot system for real-time audio routing between voice channels with multi-bot architecture support.

## 🏗️ Architecture Overview

The Discord Audio Router uses a sophisticated multi-bot architecture to enable true multi-channel audio routing:

### Core Components

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Main Bot      │    │  Speaker Bot     │    │ Listener Bots   │
│                 │    │                  │    │                 │
│ • Commands      │    │ • Audio Capture  │    │ • Audio Playback│
│ • Section Mgmt  │    │ • WebSocket Svr  │    │ • WebSocket Cli │
│ • Process Mgmt  │    │ • Audio Forward  │    │ • Multi-channel │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                        ┌──────────────────┐
                        │  Process Manager │
                        │                  │
                        │ • Bot Lifecycle  │
                        │ • Token Mgmt     │
                        │ • Health Monitor │
                        └──────────────────┘
```

### Key Features

- **Multi-Bot Architecture**: Each listener channel runs in its own process with a separate bot token
- **Real-time Audio Routing**: Low-latency audio forwarding using WebSocket communication
- **Process Isolation**: Speaker and listener bots run in separate processes for stability
- **Access Control**: Role-based permissions for broadcast management
- **Auto-scaling**: Dynamic bot deployment based on listener channel count

## 🚀 Development Setup

### Prerequisites

- Python 3.11+ (recommended)
- Discord Bot Tokens (main + listener tokens)
- FFmpeg (for audio processing)
- Git

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd discord-audio-router
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install development dependencies (optional)**
   ```bash
   pip install pytest pytest-asyncio black isort flake8 mypy
   ```

5. **Configure environment**
   ```bash
   cp env.example .env
   # Edit .env with your Discord bot tokens
   ```

### Environment Configuration

Create a `.env` file with the following variables:

```env
# Required
MAIN_BOT_TOKEN=your_main_bot_token_here
LISTENER_BOT_TOKEN=your_listener_bot_token_here

# Optional
BOT_PREFIX=!
LOG_LEVEL=INFO
AUTHORIZED_ROLES=Broadcast Controller,Moderator
AUTHORIZED_USERS=123456789012345678
```

## 🏛️ Project Structure

```
discord-audio-router/
├── bots/                          # Bot implementations
│   ├── __init__.py
│   ├── main_bot.py               # Main Discord bot with commands
│   ├── speaker_bot.py            # Standalone speaker bot process
│   ├── listener_bot.py           # Standalone listener bot process
│   ├── audio_handler.py          # Audio processing utilities
│   ├── logging_config.py         # Centralized logging setup
│   ├── config/                   # Configuration management
│   │   ├── __init__.py
│   │   └── simple_config.py      # Configuration loader
│   └── core/                     # Core system components
│       ├── __init__.py
│       ├── audio_router.py       # Main audio routing coordinator
│       ├── process_manager.py    # Bot process lifecycle management
│       ├── section_manager.py    # Broadcast section management
│       ├── access_control.py     # Role-based access control
│       └── audio_relay_server.py # Centralized WebSocket relay
├── logs/                         # Log files
├── start_bot.py                  # Main entry point
├── websocket_relay.py           # Standalone relay server
├── test_architecture.py         # Architecture validation tests
├── requirements.txt             # Python dependencies
├── Dockerfile                   # Container configuration
├── env.example                  # Environment template
└── README-DEV.md               # This file
```

## 🔧 Core Components

### AudioRouter (`bots/core/audio_router.py`)

The main coordinator that manages the entire audio routing system:

- Initializes and manages all subsystems
- Coordinates between section management and process management
- Provides the main API for Discord commands

### ProcessManager (`bots/core/process_manager.py`)

Manages the lifecycle of bot processes:

- Spawns and monitors speaker/listener bot processes
- Handles token allocation and management
- Provides process health monitoring
- Manages graceful shutdown of bot processes

### SectionManager (`bots/core/section_manager.py`)

Handles broadcast section creation and management:

- Creates Discord channels and categories
- Manages section state and metadata
- Coordinates bot deployment for sections
- Handles section cleanup and deletion

### AccessControl (`bots/core/access_control.py`)

Implements role-based access control:

- Manages authorized roles and users
- Handles private channel permissions
- Provides decorators for command authorization
- Supports both role-based and user-based permissions

## 🎵 Audio Processing

### Audio Flow

1. **Capture**: Speaker bot captures Opus audio from Discord voice channel
2. **Forward**: Audio is forwarded via WebSocket to listener bots
3. **Playback**: Listener bots play audio in their respective channels

### AudioHandler (`bots/audio_handler.py`)

Provides audio processing utilities:

- `OpusAudioSink`: Captures audio from Discord voice channels
- `OpusAudioSource`: Plays audio to Discord voice channels
- `AudioBuffer`: Thread-safe buffer for audio packets
- `SilentSource`: Generates silence frames to keep connections alive

## 🧪 Testing

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest test_architecture.py

# Run with coverage
pytest --cov=bots

# Run integration tests
pytest -m integration
```

### Test Architecture

```bash
# Validate system architecture
python test_architecture.py
```

## 🐳 Docker Development

### Building the Image

```bash
docker build -t discord-audio-router .
```

### Running Components

```bash
# Main bot
docker run -d --name main-bot \
  -e MAIN_BOT_TOKEN=your_token \
  -e LISTENER_BOT_TOKEN=your_token \
  discord-audio-router

# Speaker bot (standalone)
docker run -d --name speaker-bot \
  -e BOT_TOKEN=your_token \
  -e BOT_TYPE=speaker \
  -e CHANNEL_ID=123456789 \
  -e GUILD_ID=987654321 \
  discord-audio-router python bots/speaker_bot.py

# Listener bot (standalone)
docker run -d --name listener-bot \
  -e BOT_TOKEN=your_token \
  -e BOT_TYPE=listener \
  -e CHANNEL_ID=123456789 \
  -e GUILD_ID=987654321 \
  -e SPEAKER_CHANNEL_ID=111111111 \
  discord-audio-router python bots/listener_bot.py
```

### Docker Compose (Development)

```yaml
version: '3.8'
services:
  main-bot:
    build: .
    environment:
      - MAIN_BOT_TOKEN=${MAIN_BOT_TOKEN}
      - LISTENER_BOT_TOKEN=${LISTENER_BOT_TOKEN}
    volumes:
      - ./logs:/app/logs
    ports:
      - "8000-8100:8000-8100"
```

## 🔍 Debugging

### Logging

The system uses structured logging with different levels:

```python
import logging
logger = logging.getLogger(__name__)

# Different log levels
logger.debug("Detailed debugging information")
logger.info("General information")
logger.warning("Warning messages")
logger.error("Error messages")
logger.critical("Critical errors")
```

### Log Files

- `logs/main_bot.log`: Main bot operations
- `logs/speaker_bot.log`: Speaker bot operations
- `logs/listener_bot.log`: Listener bot operations
- `logs/websocket_relay.log`: WebSocket relay operations
- `logs/bot_startup.log`: System startup logs

### Common Issues

1. **Bot Permission Errors**
   - Ensure bot has Administrator permission or specific permissions
   - Check role hierarchy (bot role must be higher than managed roles)

2. **Audio Not Working**
   - Verify FFmpeg installation
   - Check WebSocket connectivity between bots
   - Ensure proper token configuration

3. **Process Management Issues**
   - Check available listener bot tokens
   - Verify process startup logs
   - Monitor system resources

## 🚀 Deployment

### Production Considerations

1. **Resource Requirements**
   - Minimum 2GB RAM for basic setup
   - 1GB RAM per additional listener bot
   - Stable internet connection for Discord API

2. **Security**
   - Use environment variables for tokens
   - Implement proper access controls
   - Regular security updates

3. **Monitoring**
   - Set up log monitoring
   - Monitor bot process health
   - Track WebSocket connection status

### Scaling

The system supports horizontal scaling:

- Multiple main bot instances (with different tokens)
- Distributed listener bots across servers
- Load balancing for high-traffic scenarios

## 🤝 Contributing

### Development Workflow

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

### Code Style

We use Black for code formatting and isort for import sorting:

```bash
# Format code
black .

# Sort imports
isort .

# Lint code
flake8 .
```

### Commit Messages

Use conventional commit format:

```
feat: add new audio routing feature
fix: resolve WebSocket connection issue
docs: update API documentation
test: add integration tests for process manager
```

## 📚 API Reference

### Main Bot Commands

- `!setup_broadcast 'Section Name' N`: Create broadcast section
- `!start_broadcast`: Start audio broadcasting
- `!stop_broadcast`: Stop audio broadcasting
- `!broadcast_status`: Get section status
- `!cleanup_setup`: Remove entire section
- `!system_status`: Get system status

### Configuration API

```python
from bots.config.simple_config import config_manager

config = config_manager.get_config()
print(config.main_bot_token)
print(config.listener_bot_tokens)
```

### Process Management API

```python
from bots.core.process_manager import ProcessManager

pm = ProcessManager(config)
bot_id = await pm.start_speaker_bot(channel_id, guild_id)
await pm.stop_bot(bot_id)
```

## 🔗 External Dependencies

- **discord.py**: Discord API wrapper
- **discord-ext-voice-recv**: Voice receiving extension
- **websockets**: WebSocket communication
- **aiohttp**: HTTP client/server
- **python-dotenv**: Environment variable management
- **numpy**: Numerical computing
- **ffmpeg-python**: Audio processing

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For development support:

1. Check the logs for error messages
2. Review the architecture documentation
3. Test with minimal configuration
4. Open an issue with detailed information

---

**Happy Coding! 🎵**
