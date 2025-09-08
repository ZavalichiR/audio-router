# 🎵 Discord Audio Router

**Professional multi-bot audio routing system for Discord voice channels**

Transform your Discord server into a professional broadcasting platform! The Discord Audio Router is a sophisticated system that routes audio from one speaker channel to multiple listener channels simultaneously using a multi-bot architecture. Perfect for presentations, meetings, events, training sessions, and any scenario where you need to broadcast audio to multiple groups.

## 🎯 What This Bot Does

The Discord Audio Router creates a **one-to-many audio broadcasting system** that allows:

- **🎤 One Speaker Channel**: Presenters, instructors, or speakers join a dedicated speaker channel
- **📢 Multiple Listener Channels**: Audience members join separate listener channels (Channel-1, Channel-2, etc.)
- **🔄 Real-time Audio Routing**: Audio from the speaker is instantly forwarded to all listener channels
- **🏗️ Automatic Setup**: Creates organized channel categories with proper permissions
- **🎛️ Easy Management**: Simple commands to start, stop, and monitor broadcasts
- **👥 Access Control**: Role-based permissions for broadcast management

## 🏗️ How It's Structured

The system uses a **multi-bot architecture** with specialized bots for different functions:

### Bot Types & Roles

1. **🎛️ AudioBroadcast Bot (Main Control)**
   - Handles user commands and system management
   - Creates and manages broadcast sections
   - Coordinates all other bots
   - Provides status monitoring and access control

2. **🎤 AudioForwarder Bot (Speaker Bot)**
   - Joins the speaker channel
   - Captures audio from presenters
   - Sends audio data to the WebSocket relay server
   - One instance per broadcast section

3. **📢 AudioReceiver Bots (Listener Bots)**
   - Join individual listener channels
   - Receive audio data from the relay server
   - Play audio to audience members
   - Multiple instances (one per listener channel)

### System Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Speaker       │    │  WebSocket       │    │   Listener      │
│   Channel       │◄───┤  Relay Server    ├───►│   Channels      │
│                 │    │                  │    │                 │
│ [AudioForwarder]│    │  Audio Router    │    │ [AudioReceiver] │
│      Bot        │    │   System         │    │      Bots       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Core Components

- **Core Logic** (`src/discord_audio_router/core/`): Business logic and orchestration
- **Audio Processing** (`src/discord_audio_router/audio/`): Audio capture, buffering, and playback
- **Networking** (`src/discord_audio_router/networking/`): WebSocket communication and relay servers
- **Bot Implementations** (`src/discord_audio_router/bots/`): Specialized Discord bot instances
- **Configuration** (`src/discord_audio_router/config/`): Settings and environment management
- **Infrastructure** (`src/discord_audio_router/infrastructure/`): Logging, exceptions, and utilities

## ⚙️ How It Works

### 1. **Broadcast Section Creation**
When you run `!start_broadcast 'Meeting Room' 5`:

1. **Channel Setup**: Creates a "Meeting Room" category with:
   - 🎤 **Speaker** channel (for presenters)
   - 📢 **Channel-1** through **Channel-5** channels (for audience)
   - 🎛️ **broadcast-control** channel (for commands)

2. **Bot Deployment**: 
   - Starts one AudioForwarder bot in the speaker channel
   - Starts five AudioReceiver bots (one in each listener channel)
   - Establishes WebSocket connections for audio routing

3. **Audio Routing**: 
   - Audio from the speaker channel is captured by the AudioForwarder bot
   - Audio data is sent to the WebSocket relay server
   - The relay server distributes audio to all AudioReceiver bots
   - Each AudioReceiver bot plays the audio in its respective listener channel

### 2. **Real-time Audio Flow**
```
Presenter speaks → AudioForwarder captures → WebSocket relay → AudioReceiver bots → Audience hears
```

### 3. **Process Management**
- Each bot runs as a separate process for stability
- Automatic health monitoring and restart capabilities
- Graceful shutdown and cleanup procedures
- Resource management and token allocation

### 4. **Access Control**
- Role-based permissions (Broadcast Admin, Speaker roles)
- User authorization system
- Automatic role creation and management
- Permission validation and error handling


## ✨ Features

- 🎤 **One-to-Many Audio Routing**: Broadcast from one speaker channel to multiple listener channels
- 🏗️ **Automatic Setup**: Creates organized channel categories with speaker and listener channels
- 🎛️ **Easy Control**: Simple commands to start, stop, and manage broadcasts
- 👥 **Access Control**: Role-based permissions for broadcast management
- 🔄 **Real-time**: Low-latency audio forwarding for seamless experience
- 📊 **Status Monitoring**: Check broadcast status and system health
- 🛡️ **Reliable**: Multi-bot architecture ensures stable performance

## 🚀 Quick Start

### 1. Create Discord Bots

You need to create **multiple bot users** for the audio routing system:

#### 1.1 AudioBroadcast Bot (Main Control Bot)
1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name: `Audio Router System`
3. Go to the "Bot" section
4. Click "Add Bot"
5. Set bot name: `AudioBroadcast`
6. Copy the bot token (you'll need this for `AUDIO_BROADCAST_TOKEN`)
7. Enable these **Privileged Gateway Intents**:
   - ✅ Server Members Intent
   - ✅ Message Content Intent

#### 1.2 AudioForwarder Bot (Speaker Bot)
1. In the same application, go to "Bot" section
2. Click "Add Bot" (creates a second bot)
3. Set bot name: `AudioForwarder`
4. Copy the bot token (you'll need this for `AUDIO_FORWARDER_TOKEN`)
5. Enable these **Privileged Gateway Intents**:
   - ✅ Server Members Intent
   - ✅ Message Content Intent

#### 1.3 AudioReceiver Bots (Listener Bots)
For each listener channel you want to support, create additional bots:

1. In the same application, go to "Bot" section
2. Click "Add Bot" (creates additional bots)
3. Set bot names: `AudioReceiver-1`, `AudioReceiver-2`, `AudioReceiver-3`, etc.
4. Copy each bot token (you'll need these for `AUDIO_RECEIVER_TOKENS`)
5. Enable these **Privileged Gateway Intents** for each:
   - ✅ Server Members Intent
   - ✅ Message Content Intent

### 2. Invite Bots to Server

For each bot, create an invite link:

1. Go to "OAuth2" → "URL Generator"
2. Select scopes: **bot**
3. Select bot permissions:
   - ✅ Administrator (recommended for easy setup)
   - OR select specific permissions:
     - ✅ Manage Channels
     - ✅ Manage Roles
     - ✅ Connect
     - ✅ Speak
     - ✅ Send Messages
     - ✅ Read Message History
     - ✅ Embed Links
4. Copy the generated URL and use it to invite each bot to your server

**Note**: You'll need to create separate invite links for each bot (AudioBroadcast, AudioForwarder, AudioReceiver-1, AudioReceiver-2, etc.)

### 3. Install and Configure

#### Option A: Docker (Recommended)

1. **Download the bot files**
   ```bash
   git clone <repository-url>
   cd discord-audio-router
   ```

2. **Configure environment**
   ```bash
   cp env.example .env
   # Edit .env with your bot tokens
   ```

3. **Run with Docker**
   ```bash
   docker build -t discord-audio-router .
   docker run -d --name audio-router \
     --env-file .env \
     -p 8000-8100:8000-8100 \
     discord-audio-router
   ```

#### Option B: Python Installation

1. **Install Python 3.11+** and FFmpeg
2. **Install the package**
   ```bash
   pip install -e .
   ```

3. **Configure and run**
   ```bash
   cp env.example .env
   # Edit .env with your bot tokens
   python launcher.py
   ```

## 🎛️ How to Use

### Creating a Broadcast Section

1. **Start a broadcast section** (creates organized channels and starts broadcasting):
   ```
   !start_broadcast 'War Room' 5
   ```
   This creates and immediately starts:
   - 📁 **War Room** category
   - 🎤 **Speaker** channel (for presenters)
   - 📢 **Channel-1** through **Channel-5** channels (for audience)
   - 🎛️ **broadcast-control** channel (for commands)
   - 🎵 **Audio forwarding** from speaker to all listener channels

2. **Stop broadcasting and clean up**:
   ```
   !stop_broadcast
   ```
   - Stops all audio broadcasting
   - Deletes all broadcast channels
   - Removes the broadcast category
   - Cleans up all resources

3. **Check status**:
   ```
   !broadcast_status
   ```

### Complete Example

```
!start_broadcast 'Company Meeting' 10
# Creates a meeting setup with 10 listener channels and starts broadcasting

# Presenter joins "Speaker" channel
# Audience joins "Channel-1", "Channel-2", etc.

!stop_broadcast
# Stops audio routing and removes all channels
```

## 📋 Commands Reference

### Main Commands

| Command | Description | Example |
|---------|-------------|---------|
| `!start_broadcast 'Name' N` | Create and start broadcast section with N listener channels | `!start_broadcast 'War Room' 5` |
| `!stop_broadcast` | Stop broadcasting and remove entire section | `!stop_broadcast` |
| `!broadcast_status` | Check current broadcast status | `!broadcast_status` |

### Setup Commands

| Command | Description |
|---------|-------------|
| `!check_setup` | Check if your server is properly configured |
| `!setup_roles` | Create and configure required roles (Admin only) |
| `!check_permissions` | Check bot permissions and role hierarchy (Admin only) |
| `!role_info` | Show information about audio router roles |

### Help Commands

| Command | Description |
|---------|-------------|
| `!help` | Show all available commands and their descriptions |
| `!how_it_works` | Explain how the audio routing system works |

## ⚙️ Configuration

### Environment Variables

Create a `.env` file with your configuration:

```env
# Required - Each bot needs its own unique token
AUDIO_BROADCAST_TOKEN=your_audiobroadcast_bot_token_here
AUDIO_FORWARDER_TOKEN=your_audioforwarder_bot_token_here

# AudioReceiver Bot Tokens (for multiple listener channels) - REQUIRED
AUDIO_RECEIVER_TOKENS=[
    your_audioreceiver_1_bot_token,
    your_audioreceiver_2_bot_token,
    your_audioreceiver_3_bot_token
]

# Optional
BOT_PREFIX=!
LOG_LEVEL=INFO
SPEAKER_ROLE_NAME=Speaker
BROADCAST_ADMIN_ROLE_NAME=Broadcast Admin
AUTO_CREATE_ROLES=true
```

### Multiple AudioReceiver Bots (Advanced)

For better performance with many listener channels, you can configure multiple AudioReceiver bot tokens:

```env
AUDIO_RECEIVER_TOKENS=[
    your_audioreceiver_1_bot_token,
    your_audioreceiver_2_bot_token,
    your_audioreceiver_3_bot_token,
    your_audioreceiver_4_bot_token,
    your_audioreceiver_5_bot_token
]
```

**Note**: The configuration parser supports both the new multi-line format (recommended) and the legacy comma-separated format for backward compatibility.

**Important**: Each AudioReceiver bot must have its own unique token. Discord does not allow multiple bot instances to use the same token simultaneously. More bots = better performance and reliability.

## 🎯 Use Cases

### 🏢 Business Meetings
- **Presenter** speaks in the speaker channel
- **Teams** join different listener channels for breakout discussions
- **Management** can monitor multiple team discussions

### 🎓 Educational Content
- **Instructor** teaches from the speaker channel
- **Students** join listener channels for group work
- **TAs** can assist in specific listener channels

### 🎮 Gaming Events
- **Game Master** coordinates from speaker channel
- **Players** join listener channels for team coordination
- **Spectators** can listen to different team strategies

### 🎪 Events and Presentations
- **Speaker** presents from the speaker channel
- **Audience** joins listener channels for Q&A sessions
- **Moderators** can manage different discussion groups

## 🔧 Troubleshooting

### Common Issues

#### ❌ "You need administrator permissions"
**Solution**: Make sure you have Administrator permission or are in the Broadcast Admin role.

#### ❌ "Bot lacks 'Manage Channels' permission"
**Solution**: 
1. Run `!check_permissions` for detailed instructions
2. Or give the bot Administrator permission in Server Settings

#### ❌ "No available tokens for AudioReceiver bot"
**Solution**: 
1. Create more AudioReceiver bots in Discord Developer Portal
2. Add their tokens to your `.env` file as `AUDIO_RECEIVER_TOKENS` (comma-separated)
3. Each AudioReceiver bot must have its own unique token

#### ❌ Audio not working
**Solution**:
1. Check that FFmpeg is installed
2. Verify bot is connected to voice channels
3. Run `!broadcast_status` to check broadcast health

### Getting Help

1. **Check bot status**: `!broadcast_status`
2. **Check permissions**: `!check_permissions`
3. **View logs**: Check the `logs/` directory for error messages
4. **Restart bot**: Stop and restart the bot process

## 🛡️ Security & Permissions

### Bot Permissions Required

- **Manage Channels**: Create and delete broadcast channels
- **Manage Roles**: Set up access control roles
- **Connect**: Join voice channels
- **Speak**: Transmit audio
- **Send Messages**: Send command responses
- **Read Message History**: Process commands
- **Embed Links**: Send rich command responses

### Access Control

The bot supports flexible access control:

- **Administrators**: Full access to all commands
- **Authorized Roles**: Custom roles with broadcast control
- **Authorized Users**: Specific users with broadcast control

## 📊 System Requirements

### Minimum Requirements
- **RAM**: 2GB
- **CPU**: 2 cores
- **Storage**: 1GB
- **Network**: Stable internet connection

### Recommended for Production
- **RAM**: 4GB+ (1GB per 5 listener channels)
- **CPU**: 4+ cores
- **Storage**: 5GB+
- **Network**: High-speed, stable connection

## 🚀 Advanced Features

### Process Management with Launcher

The launcher provides robust process management:

```bash
# Start all components
python launcher.py

# Start specific component
python launcher.py --component audiobroadcast_bot
python launcher.py --component relay_server

# Start with health monitoring
python launcher.py --monitor

# Check component status
python launcher.py --status
```

### Configuration Management

The system uses a centralized configuration approach following 12-factor app principles:

- **Environment Variables**: All configuration via environment variables
- **Validation**: Comprehensive configuration validation
- **Documentation**: Clear documentation for all settings

#### Configuration Files

- `env.example` - Complete configuration template with documentation

#### Environment Variables

All configuration is managed through environment variables:

```env
# Required Bot Tokens
AUDIO_BROADCAST_TOKEN=your_main_bot_token
AUDIO_FORWARDER_TOKEN=your_forwarder_bot_token
AUDIO_RECEIVER_TOKENS=token1,token2,token3

# Optional Configuration
BOT_PREFIX=!
LOG_LEVEL=INFO
SPEAKER_ROLE_NAME=Speaker
BROADCAST_ADMIN_ROLE_NAME=Broadcast Admin
AUTO_CREATE_ROLES=true

# WebSocket Relay Server
START_RELAY_SERVER=true
RELAY_SERVER_HOST=localhost
RELAY_SERVER_PORT=8765

# Development Settings
DEBUG=false
VERBOSE_LOGGING=false
```

### Docker Deployment

For production deployment, use Docker:

```bash
# Build image
docker build -t discord-audio-router .

# Run with environment file
docker run -d --name audio-router \
  --env-file .env \
  --restart unless-stopped \
  -p 8000-8100:8000-8100 \
  discord-audio-router
```

### Docker Compose

For easier management:

```yaml
version: '3.8'
services:
  audio-router:
    build: .
    environment:
      - AUDIO_BROADCAST_TOKEN=${AUDIO_BROADCAST_TOKEN}
      - AUDIO_FORWARDER_TOKEN=${AUDIO_FORWARDER_TOKEN}
      - AUDIO_RECEIVER_TOKENS=${AUDIO_RECEIVER_TOKENS}
    volumes:
      - ./logs:/app/logs
    ports:
      - "8000-8100:8000-8100"
    restart: unless-stopped
```

### Monitoring

Monitor your bot with:

- **Broadcast Status**: `!broadcast_status`
- **Log Files**: Check `logs/` directory
- **Health Checks**: Built-in Docker health checks

## 📈 Scaling

### Horizontal Scaling

For high-traffic scenarios:

1. **Multiple AudioBroadcast Bots**: Deploy multiple control bot instances
2. **Distributed AudioReceiver Bots**: Spread listener bots across servers
3. **Load Balancing**: Use multiple Discord applications

### Performance Optimization

- **More AudioReceiver Tokens**: Reduces per-bot load
- **Dedicated Resources**: Allocate sufficient RAM and CPU
- **Network Optimization**: Use low-latency hosting


## 🤝 Support

### Getting Help

1. **Check the logs** in the `logs/` directory
2. **Run diagnostic commands**:
   - `!check_setup`
   - `!check_permissions`
   - `!broadcast_status`
3. **Review this documentation**
4. **Check Discord bot permissions**

### Common Solutions

- **Restart the bot** if issues persist
- **Check Discord server permissions**
- **Verify bot token configuration**
- **Ensure FFmpeg is installed**

## 📄 License

This project is licensed under the MIT License.

## 🎉 Ready to Get Started?

1. **Create your Discord bot** in the Developer Portal
2. **Invite it to your server** with proper permissions
3. **Configure your `.env` file** with bot tokens
4. **Run the bot** using Docker or Python: `python launcher.py`
5. **Create and start your first broadcast section** with `!start_broadcast 'My Event' 5`
6. **Stop and clean up** with `!stop_broadcast`

**Happy Broadcasting! 🎵**

---

*Need help? Check the troubleshooting section or run `!help` in your Discord server.*