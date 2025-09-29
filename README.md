# 🎵 Discord Audio Router

**A personal project that was really interesting and had as goal an MVP that is working**

A multi-bot audio routing system for Discord that broadcasts audio from one speaker channel to multiple listener channels simultaneously. Perfect for presentations, meetings, events, and any scenario where you need to broadcast audio to multiple groups.

## 🏗️ System Architecture

### Multi-Bot Architecture
The system uses specialized Discord bots working together:

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Speaker       │    │  WebSocket       │    │   Listener      │
│   Channel       │◄───┤  Relay Server    ├───►│   Channels      │
│                 │    │                  │    │                 │
│ [AudioForwarder]│    │  Audio Router    │    │ [AudioReceiver] │
│      Bot        │    │   System         │    │      Bots       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Bot Types & Roles

1. **🎛️ AudioBroadcast Bot (Main Control)**
   - Handles user commands and system management
   - Creates and manages broadcast sections
   - Coordinates all other bots

2. **🎤 AudioForwarder Bot (Speaker Bot)**
   - Joins the speaker channel
   - Captures audio from presenters
   - Sends audio data to the WebSocket relay server

3. **📢 AudioReceiver Bots (Listener Bots)**
   - Join individual listener channels
   - Receive audio data from the relay server
   - Play audio to audience members
   - Multiple instances (one per listener channel)

### Database & File Communication

- **SQLite Database**: `data/subscriptions.db` - Stores subscription tiers and limits
- **WebSocket Relay Server**: Centralized audio routing between bots
- **JSON Configuration Files**: `data/broadcast_sections.json`, `data/control_panel_*.json`
- **Logging**: Structured logging to `logs/` directory

## 🚀 Quick Start

### 1. Create Discord Bots

Create multiple bot users in [Discord Developer Portal](https://discord.com/developers/applications):

1. **AudioBroadcast Bot** (Main Control)
2. **AudioForwarder Bot** (Speaker Bot)
3. **AudioReceiver-1, AudioReceiver-2, etc.** (Listener Bots)

For each bot, enable these **Privileged Gateway Intents**:
- ✅ Server Members Intent
- ✅ Message Content Intent

### 2. Install and Configure

```bash
# Clone the repository
git clone <repository-url>
cd discord-audio-router

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp env.example .env
# Edit .env with your bot tokens
```

### 3. Run the System

```bash
python launcher.py
```

## 🎛️ How to Use

### Creating a Broadcast Section

1. **Open the control panel**:
   ```
   !control_panel
   ```

2. **Create a broadcast section**:
   - Use the interactive control panel to create sections
   - Set up speaker channels and listener channels
   - Configure access control and roles

3. **Start audio broadcasting**:
   - Presenter joins the speaker channel
   - Audience joins listener channels (Channel-1, Channel-2, etc.)
   - Audio is automatically routed from speaker to all listeners

### Commands

| Command | Description |
|---------|-------------|
| `!control_panel` | Open interactive control panel for broadcast management |
| `!help` | Show help information and usage guide |
| `!bot_status` | Check status of all bots and system health |

## ⚙️ Configuration

### Required Environment Variables

```env
# Bot Tokens (Required)
AUDIO_BROADCAST_TOKEN=your_audiobroadcast_bot_token_here
AUDIO_FORWARDER_TOKEN=your_audioforwarder_bot_token_here

# AudioReceiver Bot Tokens (Required)
AUDIO_RECEIVER_TOKENS=[
    your_audioreceiver_1_bot_token,
    your_audioreceiver_2_bot_token,
    your_audioreceiver_3_bot_token
]
```

### Optional Configuration

```env
# Bot Configuration
BOT_PREFIX=!
AUTO_CLEANUP_TIMEOUT=10

# Logging
ENVIRONMENT=development
```

## 🎯 Subscription System

The system includes a subscription management system with different tiers:

| Tier | Max Listeners |
|------|---------------|
| Free | 1 |
| Basic | 2 |
| Standard | 6 |
| Advanced | 12 |
| Premium | 24 |
| Custom | Unlimited |

### Managing Subscriptions

```bash
# Create a subscription
python manage_subscriptions.py create <invite_code> <tier>

# Check subscription status
!subscription_status
```

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

## 🔧 Troubleshooting

### Common Issues

#### ❌ "No available tokens for AudioReceiver bot"
**Solution**: Create more AudioReceiver bots and add their tokens to `AUDIO_RECEIVER_TOKENS`

#### ❌ "You need administrator permissions"
**Solution**: Make sure you have Administrator permission on the server

#### ❌ Audio not working
**Solution**: Check that FFmpeg is installed and bots are connected to voice channels

### Getting Help

1. **Check bot status**: Use `!bot_status`
2. **View logs**: Check the `logs/` directory
3. **Restart system**: Stop and restart `python launcher.py`

## 📄 License

This project is licensed under the MIT License.

## 🎉 Ready to Get Started?

1. **Create your Discord bots** in the Developer Portal
2. **Configure your `.env` file** with bot tokens
3. **Run the system**: `python launcher.py`
4. **Create your first broadcast** with `!control_panel`

**Happy Broadcasting! 🎵**

---

*This is a personal project that was really interesting and had as goal an MVP that is working. The system provides a robust foundation for multi-channel audio broadcasting in Discord.*