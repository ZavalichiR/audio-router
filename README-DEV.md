# 🎵 Discord Audio Router - Developer Guide

This guide provides detailed instructions for setting up the Discord Audio Router system, including creating Discord applications and configuring bot permissions.

## 📋 Table of Contents

- [Discord Application Setup](#discord-application-setup)
- [Bot Permissions](#bot-permissions)
- [Environment Configuration](#environment-configuration)
- [Development Setup](#development-setup)
- [Architecture Overview](#architecture-overview)
- [Troubleshooting](#troubleshooting)

## 🚀 Discord Application Setup

### Step 1: Create Discord Application

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **"New Application"**
3. Enter application name: `Audio Router System`
4. Click **"Create"**

### Step 2: Create Bot Users

You need to create **multiple bot users** for the audio routing system:

#### 2.1 AudioBroadcast Bot (Main Control Bot)
1. In your application, go to **"Bot"** section
2. Click **"Add Bot"**
3. Set bot name: `AudioBroadcast`
4. Copy the bot token (you'll need this for `AUDIO_BROADCAST_TOKEN`)
5. Enable these **Privileged Gateway Intents**:
   - ✅ **Server Members Intent**
   - ✅ **Message Content Intent**

#### 2.2 AudioForwarder Bot (Speaker Bot)
1. Go to **"Bot"** section
2. Click **"Add Bot"** (creates a second bot)
3. Set bot name: `AudioForwarder`
4. Copy the bot token (you'll need this for `LISTENER_BOT_TOKEN_1`)
5. Enable these **Privileged Gateway Intents**:
   - ✅ **Server Members Intent**
   - ✅ **Message Content Intent**

#### 2.3 AudioReceiver Bots (Listener Bots)
For each listener channel you want to support, create additional bots:

1. Go to **"Bot"** section
2. Click **"Add Bot"** (creates additional bots)
3. Set bot names: `AudioReceiver-1`, `AudioReceiver-2`, `AudioReceiver-3`, etc.
4. Copy each bot token (you'll need these for `LISTENER_BOT_TOKEN_2`, `LISTENER_BOT_TOKEN_3`, etc.)
5. Enable these **Privileged Gateway Intents** for each:
   - ✅ **Server Members Intent**
   - ✅ **Message Content Intent**

### Step 3: Generate Invite Links

For each bot, create an invite link:

1. Go to **"OAuth2"** → **"URL Generator"**
2. Select scopes: **bot**
3. Select bot permissions (see [Bot Permissions](#bot-permissions) section)
4. Copy the generated URL
5. Use the URL to invite each bot to your Discord server

## 🔐 Bot Permissions

### Required Permissions for All Bots

Each bot needs these permissions:

#### Essential Permissions
- ✅ **Administrator** (recommended for easy setup)
- OR specific permissions:
  - ✅ **Manage Channels** - Create and delete broadcast channels
  - ✅ **Manage Roles** - Set up access control roles
  - ✅ **Connect** - Join voice channels
  - ✅ **Speak** - Transmit audio
  - ✅ **Send Messages** - Send command responses
  - ✅ **Read Message History** - Process commands
  - ✅ **Embed Links** - Send rich command responses
  - ✅ **Use Slash Commands** - Support slash commands

#### Voice Permissions
- ✅ **Connect** - Join voice channels
- ✅ **Speak** - Transmit audio
- ✅ **Use Voice Activity** - Detect when users are speaking
- ✅ **Priority Speaker** - Ensure bot audio is heard clearly

### Permission Setup Instructions

#### Option 1: Administrator Permission (Recommended)
1. In the **"OAuth2"** → **"URL Generator"**
2. Select **"Administrator"** permission
3. This gives the bot all necessary permissions

#### Option 2: Specific Permissions
1. In the **"OAuth2"** → **"URL Generator"**
2. Select these specific permissions:
   - **Text Permissions**: Send Messages, Read Message History, Embed Links, Use Slash Commands
   - **Voice Permissions**: Connect, Speak, Use Voice Activity, Priority Speaker
   - **General Permissions**: Manage Channels, Manage Roles

## ⚙️ Environment Configuration

Create a `.env` file in your project root with the following configuration:

```env
# ===========================================
# DISCORD BOT TOKENS (ALL REQUIRED)
# ===========================================

# AudioBroadcast Bot (Main Control Bot) - REQUIRED
AUDIO_BROADCAST_TOKEN=your_audiobroadcast_bot_token_here

# AudioForwarder Bot (Speaker Bot) - REQUIRED
AUDIO_FORWARDER_TOKEN=your_audioforwarder_bot_token_here

# AudioReceiver Bots (Listener Bots) - REQUIRED
# Each AudioReceiver bot needs its own unique token
AUDIO_RECEIVER_TOKENS=your_audioreceiver_1_bot_token,your_audioreceiver_2_bot_token,your_audioreceiver_3_bot_token

# ===========================================
# BOT CONFIGURATION
# ===========================================

# Command prefix for bot commands
BOT_PREFIX=!

# Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL=INFO

# ===========================================
# ACCESS CONTROL
# ===========================================

# Role names for access control
SPEAKER_ROLE_NAME=Speaker
BROADCAST_ADMIN_ROLE_NAME=Broadcast Admin

# Auto-create roles if they don't exist
AUTO_CREATE_ROLES=true
```

### Token Assignment Strategy

The system uses a clear token assignment strategy:

1. **AudioBroadcast Bot**: Uses `AUDIO_BROADCAST_TOKEN` for command handling and management
2. **AudioForwarder Bot**: Uses `AUDIO_FORWARDER_TOKEN` for speaker channel audio capture
3. **AudioReceiver Bots**: Use tokens from `AUDIO_RECEIVER_TOKENS` for listener channels

**Important**: Each bot must have its own unique token. Discord does not allow multiple bot instances to use the same token simultaneously.

This design allows:
- **Scalability**: Each AudioReceiver bot can handle one listener channel
- **Performance**: Multiple AudioReceiver bots reduce per-bot load
- **Reliability**: If one AudioReceiver bot fails, others continue working
- **Clarity**: Each bot type has its own dedicated token
- **Compliance**: Follows Discord's token usage requirements

## 🛠️ Development Setup

### Prerequisites

- **Python 3.11+**
- **FFmpeg** (for audio processing)
- **Git** (for version control)

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

4. **Configure environment**
   ```bash
   cp env.example .env
   # Edit .env with your bot tokens
   ```

5. **Create logs directory**
   ```bash
   mkdir -p logs
   ```

### Running the System

#### Option 1: Using Launcher (Recommended)
```bash
# Start all components
python launcher.py

# Start specific component
python launcher.py --component audiobroadcast_bot
python launcher.py --component relay_server

# Start with health monitoring
python launcher.py --monitor
```

#### Option 2: Direct Execution
```bash
# Start AudioBroadcast bot
python start_bot.py

# Start AudioForwarder bot (for testing)
python bots/audioforwarder_bot.py

# Start AudioReceiver bot (for testing)
python bots/audioreceiver_bot.py
```

#### Option 3: Docker
```bash
# Build image
docker build -t discord-audio-router .

# Run with environment file
docker run -d --name audio-router \
  --env-file .env \
  -p 8000-8100:8000-8100 \
  discord-audio-router
```

## 🏗️ Architecture Overview

### Bot Types and Responsibilities

#### 1. AudioBroadcast Bot
- **Purpose**: Main control bot that handles user commands
- **Responsibilities**:
  - Process Discord commands (`!setup_broadcast`, `!start_broadcast`, etc.)
  - Create and manage broadcast sections
  - Handle access control and role management
  - Coordinate with other bots
- **File**: `bots/audiobroadcast_bot.py`
- **Token**: `AUDIO_BROADCAST_TOKEN`

#### 2. AudioForwarder Bot
- **Purpose**: Captures audio from speaker channels and forwards it
- **Responsibilities**:
  - Connect to speaker voice channels
  - Capture audio using discord.py voice_recv
  - Forward audio via WebSocket to AudioReceiver bots
  - Manage WebSocket server for audio distribution
- **File**: `bots/audioforwarder_bot.py`
- **Token**: `AUDIO_FORWARDER_TOKEN`

#### 3. AudioReceiver Bots
- **Purpose**: Receive audio and play it in listener channels
- **Responsibilities**:
  - Connect to listener voice channels
  - Receive audio via WebSocket from AudioForwarder bot
  - Play audio in their assigned listener channel
  - Handle audio buffering and playback
- **File**: `bots/audioreceiver_bot.py`
- **Token**: From `AUDIO_RECEIVER_TOKENS` (comma-separated)

### System Flow

```
User Command → AudioBroadcast Bot → Process Manager → AudioForwarder Bot
                                                      ↓
AudioReceiver Bot ← WebSocket ← AudioForwarder Bot ← Speaker Channel
       ↓
Listener Channel
```

### WebSocket Communication

- **AudioForwarder Bot**: Runs WebSocket server on port `8000 + (channel_id % 1000)`
- **AudioReceiver Bots**: Connect to AudioForwarder's WebSocket server
- **Protocol**: JSON messages with audio data in hex format
- **Features**: Automatic reconnection, health monitoring, error handling

## 🔧 Troubleshooting

### Common Issues

#### ❌ "No available tokens for AudioReceiver bot"
**Cause**: Not enough AudioReceiver bot tokens configured
**Solution**: 
1. Create more AudioReceiver bots in Discord Developer Portal
2. Add their tokens to `.env` file as `AUDIO_RECEIVER_TOKENS` (comma-separated)
3. Restart the system

#### ❌ "Bot lacks 'Manage Channels' permission"
**Cause**: Bot doesn't have required permissions
**Solution**:
1. Go to Discord Developer Portal
2. Update bot permissions in OAuth2 → URL Generator
3. Re-invite the bot to your server

#### ❌ "Failed to connect to AudioForwarder WebSocket"
**Cause**: AudioForwarder bot not running or WebSocket server not started
**Solution**:
1. Check if AudioForwarder bot is running
2. Verify WebSocket port is not blocked
3. Check logs for connection errors

#### ❌ "Audio not working"
**Cause**: Various audio-related issues
**Solution**:
1. Verify FFmpeg is installed
2. Check bot voice channel connections
3. Run `!system_status` to check bot health
4. Check logs for audio processing errors

### Debugging Commands

Use these commands in Discord to debug issues:

- `!system_status` - Check all bot processes and system health
- `!broadcast_status` - Check current broadcast section status
- `!check_permissions` - Verify bot permissions
- `!role_info` - Show role information and assignments

### Log Files

Check these log files for detailed error information:

- `logs/audiobroadcast_bot.log` - Main bot logs
- `logs/audioforwarder_bot.log` - AudioForwarder bot logs
- `logs/audioreceiver_bot.log` - AudioReceiver bot logs
- `logs/launcher.log` - Process manager logs

### Performance Optimization

#### For High-Traffic Scenarios

1. **More AudioReceiver Bots**: Add more `LISTENER_BOT_TOKEN_X` entries
2. **Dedicated Resources**: Allocate sufficient RAM and CPU
3. **Network Optimization**: Use low-latency hosting
4. **Load Balancing**: Distribute bots across multiple servers

#### Recommended Token Count

- **Small Setup** (1-5 listener channels): 1-2 AudioReceiver tokens
- **Medium Setup** (5-10 listener channels): 3-5 AudioReceiver tokens  
- **Large Setup** (10+ listener channels): 5-10 AudioReceiver tokens

## 📚 Additional Resources

- [Discord Developer Portal](https://discord.com/developers/applications)
- [Discord.py Documentation](https://discordpy.readthedocs.io/)
- [Voice Receive Extension](https://github.com/imayhaveborkedit/discord.py-voice-recv)
- [WebSocket Documentation](https://websockets.readthedocs.io/)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

---

**Need Help?** Check the troubleshooting section or create an issue in the repository.