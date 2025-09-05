# 🎵 Discord Audio Router Bot

**Professional audio routing system for Discord voice channels**

Transform your Discord server into a professional broadcasting platform! The Discord Audio Router Bot allows you to route audio from one voice channel to multiple listener channels simultaneously, perfect for presentations, meetings, events, and more.

## ✨ Features

- 🎤 **One-to-Many Audio Routing**: Broadcast from one speaker channel to multiple listener channels
- 🏗️ **Automatic Setup**: Creates organized channel categories with speaker and listener channels
- 🎛️ **Easy Control**: Simple commands to start, stop, and manage broadcasts
- 👥 **Access Control**: Role-based permissions for broadcast management
- 🔄 **Real-time**: Low-latency audio forwarding for seamless experience
- 📊 **Status Monitoring**: Check broadcast status and system health
- 🛡️ **Reliable**: Multi-bot architecture ensures stable performance

## 🚀 Quick Start

### 1. Create Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name
3. Go to the "Bot" section
4. Click "Add Bot"
5. Copy the bot token (you'll need this later)
6. Enable these **Privileged Gateway Intents**:
   - ✅ Server Members Intent
   - ✅ Message Content Intent

### 2. Invite Bot to Server

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
4. Copy the generated URL and use it to invite your bot

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
   # Edit .env with your bot token
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
2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure and run**
   ```bash
   cp env.example .env
   # Edit .env with your bot token
   python launcher.py
   ```

## 🎛️ How to Use

### Creating a Broadcast Section

1. **Set up a broadcast section** (creates organized channels):
   ```
   !setup_broadcast 'War Room' 5
   ```
   This creates:
   - 📁 **War Room** category
   - 🎤 **Speaker** channel (for presenters)
   - 📢 **1-listener** through **5-listener** channels (for audience)
   - 🎛️ **broadcast-control** channel (for commands)

2. **Start broadcasting**:
   ```
   !start_broadcast
   ```
   - The bot will connect to the speaker channel
   - Audio from the speaker channel will be forwarded to all listener channels
   - Audience members can join any listener channel to hear the audio

3. **Stop broadcasting**:
   ```
   !stop_broadcast
   ```

4. **Check status**:
   ```
   !broadcast_status
   ```

### Complete Example

```
!setup_broadcast 'Company Meeting' 10
# Creates a meeting setup with 10 listener channels

!start_broadcast
# Starts audio routing from speaker to all listeners

# Presenter joins "Speaker" channel
# Audience joins "1-listener", "2-listener", etc.

!stop_broadcast
# Stops audio routing

!cleanup_setup
# Removes all channels and cleans up
```

## 📋 Commands Reference

### Setup Commands

| Command | Description | Example |
|---------|-------------|---------|
| `!setup_broadcast 'Name' N` | Create broadcast section with N listener channels | `!setup_broadcast 'War Room' 5` |
| `!check_setup 'Name'` | Check if a section already exists | `!check_setup 'War Room'` |
| `!cleanup_setup` | Remove entire broadcast section | `!cleanup_setup` |

### Control Commands

| Command | Description |
|---------|-------------|
| `!start_broadcast` | Start audio forwarding |
| `!stop_broadcast` | Stop audio forwarding |
| `!broadcast_status` | Check current broadcast status |
| `!system_status` | Check all bot processes and system health |

### Access Control Commands (Admin Only)

| Command | Description | Example |
|---------|-------------|---------|
| `!authorize @user` | Give user broadcast control permissions | `!authorize @john` |
| `!unauthorize @user` | Remove user's broadcast permissions | `!unauthorize @john` |
| `!list_authorized` | List all authorized users |
| `!check_permissions` | Check bot permissions and role hierarchy |
| `!fix_permissions` | Get step-by-step permission fix instructions |

### Help Commands

| Command | Description |
|---------|-------------|
| `!help_audio_router` | Show complete help information |

## ⚙️ Configuration

### Environment Variables

Create a `.env` file with your configuration:

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

### Multiple Listener Bots (Advanced)

For better performance with many listener channels, you can configure multiple listener bot tokens:

```env
# Multiple tokens (comma-separated)
LISTENER_BOT_TOKENS=token1,token2,token3,token4,token5

# Or numbered tokens
LISTENER_BOT_TOKEN_1=token1
LISTENER_BOT_TOKEN_2=token2
LISTENER_BOT_TOKEN_3=token3
```

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
**Solution**: Make sure you have Administrator permission or are in an authorized role.

#### ❌ "Bot lacks 'Manage Channels' permission"
**Solution**: 
1. Run `!fix_permissions` for detailed instructions
2. Or give the bot Administrator permission in Server Settings

#### ❌ "No available tokens for listener bot"
**Solution**: 
1. Add more listener bot tokens to your `.env` file
2. Or use the same token for all bots (less optimal but functional)

#### ❌ Audio not working
**Solution**:
1. Check that FFmpeg is installed
2. Verify bot is connected to voice channels
3. Run `!system_status` to check bot health

### Getting Help

1. **Check bot status**: `!system_status`
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

The new launcher provides robust process management:

```bash
# Start all components
python launcher.py

# Start specific component
python launcher.py --component main_bot
python launcher.py --component relay_server

# Start with health monitoring
python launcher.py --monitor

# Start without relay server
python launcher.py --no-relay

# Check component status
python launcher.py --status
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
      - MAIN_BOT_TOKEN=${MAIN_BOT_TOKEN}
      - LISTENER_BOT_TOKEN=${LISTENER_BOT_TOKEN}
    volumes:
      - ./logs:/app/logs
    ports:
      - "8000-8100:8000-8100"
    restart: unless-stopped
```

### Monitoring

Monitor your bot with:

- **System Status**: `!system_status`
- **Log Files**: Check `logs/` directory
- **Health Checks**: Built-in Docker health checks

## 📈 Scaling

### Horizontal Scaling

For high-traffic scenarios:

1. **Multiple Main Bots**: Deploy multiple bot instances
2. **Distributed Listeners**: Spread listener bots across servers
3. **Load Balancing**: Use multiple Discord applications

### Performance Optimization

- **More Listener Tokens**: Reduces per-bot load
- **Dedicated Resources**: Allocate sufficient RAM and CPU
- **Network Optimization**: Use low-latency hosting

## 🤝 Support

### Getting Help

1. **Check the logs** in the `logs/` directory
2. **Run diagnostic commands**:
   - `!system_status`
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
5. **Create your first broadcast section** with `!setup_broadcast 'My Event' 5`
6. **Start broadcasting** with `!start_broadcast`

**Happy Broadcasting! 🎵**

---

*Need help? Check the troubleshooting section or run `!help_audio_router` in your Discord server.*