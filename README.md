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

**Before You Begin**: This software is for **personal, educational, and non-commercial use only**. See the [License](#-license) section for details. Commercial use requires explicit written permission from the owner.

### 1. Create Discord Bots

Create multiple bot users in [Discord Developer Portal](https://discord.com/developers/applications):

#### Bot Naming Convention

**IMPORTANT**: The system requires specific bot names to function correctly.

| Bot Number | Application Name | Username | Display Name | Purpose |
|------------|------------------|----------|--------------|---------|
| 1 | AudioBroadcast | AudioBroadcast | AudioBroadcast | Main control bot (handles commands) |
| 2 | AudioForwarder | AudioForwarder | Fwd-Speaker | Speaker bot (captures audio) |
| 3 | AudioReceiver-1 | AudioReceiver-1 | **Rcv-1** | Listener channel 1 |
| 4 | AudioReceiver-2 | AudioReceiver-2 | **Rcv-2** | Listener channel 2 |
| 5 | AudioReceiver-3 | AudioReceiver-3 | **Rcv-3** | Listener channel 3 |
| ... | ... | ... | ... | ... |
| 14 | AudioReceiver-12 | AudioReceiver-12 | **Rcv-12** | Listener channel 12 |

**Critical Naming Requirements**:

- ⚠️ **AudioForwarder bot MUST have "forward" in its display name** (case-insensitive, e.g., `Fwd-Speaker`, `AudioForwarder`, `Forward-Bot`)
- ⚠️ **AudioReceiver bots MUST have display names starting with `Rcv-`** (e.g., `Rcv-1`, `Rcv-2`, `Rcv-3`)
- The system automatically detects bots by these naming patterns
- The number after `Rcv-` should match the bot number for organization

#### Required Permissions

For each bot, enable these **Privileged Gateway Intents**:
- ✅ Server Members Intent
- ✅ Message Content Intent

Grant each bot these **Bot Permissions**:
- ✅ Manage Channels
- ✅ Manage Roles
- ✅ Connect (Voice)
- ✅ Speak (Voice)
- ✅ Send Messages
- ✅ Read Message History
- ✅ Embed Links

**Tip**: You can grant Administrator permission for simplicity during setup.

### 2. Invite Bots to Your Discord Server

After creating all bots in the Developer Portal, you need to invite them to your Discord server:

1. **Generate OAuth2 URLs** for each bot:
   - Go to your bot in the [Discord Developer Portal](https://discord.com/developers/applications)
   - Navigate to **OAuth2** → **URL Generator**
   - Select **Scopes**: `bot`, `applications.commands`
   - Select **Bot Permissions**: Check `Administrator` (or the specific permissions listed above)
   - Copy the generated URL

2. **Invite each bot** to your server:
   - Open the generated URL in your browser
   - Select your Discord server
   - Click **Authorize**
   - Complete the CAPTCHA if prompted
   - Repeat for all bots (AudioBroadcast, AudioForwarder, and all AudioReceiver bots)

3. **Verify bot names**:
   - Go to your Discord server
   - Check that the AudioForwarder bot has "forward" in its display name
   - Check that all AudioReceiver bots have names starting with `Rcv-` (e.g., `Rcv-1`, `Rcv-2`)
   - You can change bot nicknames in Discord: Right-click bot → Change Nickname

### 3. Install and Configure

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

**Important**: Edit the `.env` file and paste the bot tokens you copied from the Discord Developer Portal.

### 4. Run the System

```bash
python launcher.py
```

The launcher will:

- Start the WebSocket relay server
- Start the AudioBroadcast bot
- Validate all configuration

### 5. Create Your First Broadcast

In your Discord server, use these commands:

```bash
!help                    # View all available commands
!bot_status             # Check that all bots are detected
!control_panel          # Open the interactive control panel to create a broadcast section
```

**Using the Control Panel**:

1. Click the "Create Broadcast" button
2. Enter the number of listener channels you want (based on your subscription tier)
3. Optionally enter a custom role name for access control
4. Wait for the system to create channels and deploy bots
5. Join the Speaker channel and start talking
6. Audience members join the Channel-1, Channel-2, etc. to listen

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

## 🎯 Subscription & Licensing System

The system uses a **SQLite database** (`data/subscriptions.db`) to manage per-server licenses that control how many listener channels each Discord server can create.

### How It Works

1. **Per-Server Licensing**: Each Discord server has its own subscription tier
2. **Database Storage**: Subscriptions are stored in `data/subscriptions.db`
3. **Invite Code Based**: Subscriptions are created using Discord invite codes
4. **Automatic Enforcement**: The system automatically checks the database before creating broadcast sections
5. **Default Tier**: Servers without a subscription default to the **Free** tier (1 listener)

### Subscription Tiers

| Tier | Max Listeners | Use Case |
|------|---------------|----------|
| **Free** | 1 | Basic functionality, testing |
| **Basic** | 2 | Small groups, trial tier |
| **Standard** | 6 | Small communities |
| **Advanced** | 12 | Medium communities |
| **Premium** | 24 | Large communities |
| **Custom** | Unlimited | Custom features, enterprise |

### Managing Subscriptions (Server Owner/Admin)

You can manage subscriptions using the `manage_subscriptions.py` CLI tool:

#### Create a Subscription

```bash
# Syntax: python manage_subscriptions.py create <invite_code> <tier>
python manage_subscriptions.py create abc123xyz free
python manage_subscriptions.py create abc123xyz premium
```

**How to get an invite code**:

1. Go to your Discord server
2. Right-click on any channel → "Invite People"
3. Click "Edit invite link" → Set "Expire After" to "Never"
4. Copy the invite code (e.g., `https://discord.gg/abc123xyz` → use `abc123xyz`)

#### List All Subscriptions

```bash
python manage_subscriptions.py list
```

#### Get Subscription Details

```bash
python manage_subscriptions.py get <invite_code>
```

#### Update Subscription Tier

```bash
python manage_subscriptions.py update <invite_code> <new_tier>
# Example: Upgrade a server to premium
python manage_subscriptions.py update abc123xyz premium
```

#### Delete a Subscription

```bash
python manage_subscriptions.py delete <invite_code>
```

#### View Available Tiers

```bash
python manage_subscriptions.py tiers
```

### Checking Subscription Status (Discord Users)

Users can check their server's subscription status in Discord:

```bash
!subscription_status
```

This command displays:

- Current subscription tier
- Maximum allowed listeners
- Number of installed AudioReceiver bots
- Upgrade information

### Database Location

The subscription database is stored at:

```text
data/subscriptions.db
```

**Important**:

- Back up this database regularly if you're managing subscriptions
- The database is created automatically on first use
- Subscriptions persist across bot restarts

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

#### ❌ Speaker bot not joining channel / Voice connection timeout
**Problem**: The AudioForwarder (speaker) bot fails to join the voice channel or experiences connection timeouts.

**Solution**:
1. **Assign the Speaker role to the AudioForwarder bot** (the bot with "forward" in its name, e.g., `Fwd-Speaker`):
   - In your Discord server, right-click the **AudioForwarder bot** (NOT the AudioBroadcast bot)
   - Go to Roles
   - Assign the role that matches your `SPEAKER_NAME` in `.env` (default: "Speaker")
2. **Verify bot permissions**: Ensure the AudioForwarder bot has `Connect`, `Speak`, and `View Channel` permissions
3. **Check channel permissions**: Make sure the voice channel doesn't have role restrictions that block the bot
4. **Configure permission role** (optional): In the control panel, you can set a specific role name for access control when creating a broadcast section

**Important**: The `permission_role` setting in the control panel determines which role is required to be a speaker. The **AudioForwarder bot** (speaker bot) must have this role assigned in Discord, not the AudioBroadcast bot.

#### ❌ Audio not working
**Solution**: Check that FFmpeg is installed and bots are connected to voice channels

### Getting Help

1. **Check bot status**: Use `!bot_status`
2. **View logs**: Check the `logs/` directory
3. **Restart system**: Stop and restart `python launcher.py`

## 📄 License

### Copyright

Copyright (c) 2024-2025 - All Rights Reserved

This project is provided for **personal, educational, and non-commercial use only**.

### Terms of Use

#### ✅ You MAY

- Use this software for personal, non-commercial purposes
- Study and learn from the code
- Modify the code for your own personal use
- Run the software on your own Discord servers

#### ❌ You MAY NOT

- Sell, license, or commercialize this software or derivatives without explicit written permission from the owner
- Offer this as a paid service or product
- Redistribute this software (modified or unmodified) for commercial purposes
- Remove or modify copyright notices

### Discord Policy Compliance

This software must be used in compliance with:

- [Discord Terms of Service](https://discord.com/terms)
- [Discord Developer Terms of Service](https://discord.com/developers/docs/policies-and-agreements/developer-terms-of-service)
- [Discord Developer Policy](https://support-dev.discord.com/hc/en-us/articles/8563934450327-Discord-Developer-Policy)
- [Discord Community Guidelines](https://discord.com/guidelines)

#### Key Requirements

- You must comply with all Discord policies when using this software
- You cannot use this software to violate Discord's Terms of Service
- You are responsible for ensuring your use complies with Discord's Developer Policy
- This software cannot be used to scrape data, spam, or abuse Discord's services

### Commercial Use

For commercial use, licensing inquiries, or partnerships, please contact the owner for explicit written permission.

### Disclaimer

THIS SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED. THE AUTHOR IS NOT RESPONSIBLE FOR ANY DAMAGES OR LEGAL ISSUES ARISING FROM THE USE OF THIS SOFTWARE. USERS ARE SOLELY RESPONSIBLE FOR ENSURING THEIR USE COMPLIES WITH ALL APPLICABLE LAWS AND DISCORD'S POLICIES.

## 🎉 Ready to Get Started?

1. **Create your Discord bots** in the Developer Portal
2. **Configure your `.env` file** with bot tokens
3. **Run the system**: `python launcher.py`
4. **Create your first broadcast** with `!control_panel`

**Happy Broadcasting! 🎵**

---

*This is a personal project that was really interesting and had as goal an MVP that is working. The system provides a robust foundation for multi-channel audio broadcasting in Discord.*