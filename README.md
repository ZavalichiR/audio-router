# Discord Audio Router

**A personal MVP project for broadcasting audio from one Discord voice channel to multiple listener channels simultaneously.**

Perfect for presentations, meetings, events, and any scenario where you need to broadcast audio to multiple groups at once.

## How It Works

The system uses multiple Discord bots working together:

```
Speaker Channel  →  AudioForwarder Bot  →  WebSocket Relay  →  AudioReceiver Bots  →  Listener Channels
   (Presenter)        (Captures audio)        (Routes audio)      (Play audio)         (Audiences)
```

- **AudioBroadcast Bot**: Main control bot that handles commands and coordination
- **AudioForwarder Bot**: Joins the speaker channel and captures audio
- **AudioReceiver Bots**: Join listener channels and play the audio (one bot per channel)
- **WebSocket Relay**: Routes audio between the forwarder and receiver bots

## Quick Start

### 1. Create Discord Bots

Create bots in the [Discord Developer Portal](https://discord.com/developers/applications):

| Bot | Display Name | Purpose |
|-----|--------------|---------|
| AudioBroadcast | AudioBroadcast | Main control bot (handles commands) |
| AudioForwarder | Fwd-Speaker | Captures audio from speaker channel |
| AudioReceiver-1 | Rcv-1 | Plays audio to listener channel 1 |
| AudioReceiver-2 | Rcv-2 | Plays audio to listener channel 2 |
| ... | ... | ... |
| AudioReceiver-N | Rcv-N | Additional listener channels as needed |

**Important Naming Requirements:**
- AudioForwarder bot **must have "forward" in its display name** (e.g., `Fwd-Speaker`, `AudioForwarder`)
- AudioReceiver bots **must have names starting with `Rcv-`** (e.g., `Rcv-1`, `Rcv-2`, `Rcv-3`)
- The system auto-detects bots by these naming patterns

### 2. Enable Privileged Intents

For the **AudioBroadcast bot only** (main control bot), go to the Discord Developer Portal → Bot section → Enable:
- ✅ **Server Members Intent** (required for bot detection)
- ✅ **Message Content Intent** (required for prefix commands)

**Note**: AudioForwarder and AudioReceiver bots do NOT need privileged intents enabled.

### 3. Set Bot Permissions

Give each bot these permissions (or use Administrator for simplicity):
- Connect, Speak (Voice)
- Manage Channels, Manage Roles
- Send Messages, Read Message History, Embed Links

**Permission Integer for AudioReceiver bots**: `3145728`

### 4. Invite Bots to Your Server

Generate OAuth2 URLs and invite all bots:

1. Go to Discord Developer Portal → OAuth2 → URL Generator
2. Select scopes: `bot`
3. Select permissions or use Administrator
4. Copy URL and open in browser to invite

**Quick invite URL format:**
```
https://discord.com/oauth2/authorize?client_id=YOUR_BOT_CLIENT_ID&permissions=3145728&integration_type=0&scope=bot
```

Replace `YOUR_BOT_CLIENT_ID` with each bot's client ID from the Developer Portal.

### 5. Install and Configure

```bash
# Clone repository
git clone <repository-url>
cd discord-audio-router

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp env.example .env
# Edit .env and paste your bot tokens
```

**Important**: Edit `.env` and add all bot tokens from the Discord Developer Portal.

### 6. Configure Bot Invite URLs (Optional but Recommended)

The system can show invite links to users who need to add more receiver bots:

```bash
# Edit data/bot_urls.json with your bot invite URLs
# Format: JSON array of invite URLs, one per receiver bot
```

Example `data/bot_urls.json`:
```json
[
  "https://discord.com/oauth2/authorize?client_id=BOT1_ID&permissions=3145728&integration_type=0&scope=bot",
  "https://discord.com/oauth2/authorize?client_id=BOT2_ID&permissions=3145728&integration_type=0&scope=bot"
]
```

You can also use the management script:
```bash
python manage_urls.py list                    # List all URLs
python manage_urls.py add <invite_url>        # Add a new URL
python manage_urls.py remove <index>          # Remove URL by index
```

### 7. Run the System

```bash
python launcher.py
```

The launcher will start:
- WebSocket relay server
- AudioBroadcast bot
- All system components

### 8. Create Your First Broadcast

In Discord, use these commands:

```bash
!help                    # View all commands
!bot_status             # Check system health and bot detection
!control_panel          # Open interactive control panel
```

**Using the Control Panel:**
1. Click "Create Broadcast"
2. Enter number of listener channels (based on your subscription tier)
3. Optionally enter a custom role name for speaker access
4. Wait for channels to be created
5. Join the Speaker channel and start talking
6. Audience joins Channel-1, Channel-2, etc. to listen

## Commands

| Command | Description |
|---------|-------------|
| `!control_panel` | Open interactive control panel (admin only) |
| `!help` | Show help and usage information |
| `!bot_status` | Check system health and bot detection |
| `!subscription_status` | View your server's subscription tier and limits |
| `!how_it_works` | Learn how the audio router works |

## Subscription System

The system uses a SQLite database (`data/subscriptions.db`) to manage per-server licenses that control how many listener channels each server can create.

### Subscription Tiers

| Tier | Max Listeners | Use Case |
|------|---------------|----------|
| Free | 1 | Testing, basic use |
| Basic | 2 | Small groups |
| Standard | 6 | Small communities |
| Advanced | 12 | Medium communities |
| Premium | 24 | Large communities |
| Custom | Unlimited | Enterprise |

### Managing Subscriptions

Use the `manage_subscriptions.py` CLI tool:

```bash
# Create subscription using Discord invite code
python manage_subscriptions.py create <invite_code> <tier>

# Example: Create a premium subscription
python manage_subscriptions.py create abc123xyz premium

# List all subscriptions
python manage_subscriptions.py list

# Update tier
python manage_subscriptions.py update <invite_code> <new_tier>

# Delete subscription
python manage_subscriptions.py delete <invite_code>

# View available tiers
python manage_subscriptions.py tiers
```

**Getting an invite code:**
1. In Discord, right-click any channel → "Invite People"
2. Click "Edit invite link" → Set "Expire After" to "Never"
3. Copy invite code (e.g., `https://discord.gg/abc123xyz` → use `abc123xyz`)

**Note**: Servers without a subscription default to the Free tier (1 listener).

## Configuration

### Required Environment Variables

```env
# Main control bot
AUDIO_BROADCAST_TOKEN=your_audiobroadcast_bot_token

# Speaker bot
AUDIO_FORWARDER_TOKEN=your_audioforwarder_bot_token

# Listener bots (one per line)
AUDIO_RECEIVER_TOKENS=[
    your_audioreceiver_1_token,
    your_audioreceiver_2_token,
    your_audioreceiver_3_token
]
```

### Optional Configuration

```env
BOT_PREFIX=!                # Command prefix (default: !)
AUTO_CLEANUP_TIMEOUT=10     # Auto-cleanup inactive broadcasts in minutes (0 to disable)
ENVIRONMENT=development     # Logging level: development, staging, production
```

## Troubleshooting

### "Privileged intents not enabled"
**Solution**: Enable **Server Members Intent** and **Message Content Intent** in Discord Developer Portal for the **AudioBroadcast bot** (main control bot only).

### "No available tokens for AudioReceiver bot"
**Solution**: Create more AudioReceiver bots and add their tokens to `AUDIO_RECEIVER_TOKENS` in `.env`.

### Speaker bot not joining channel / Connection timeout
**Solution**:
1. Verify the AudioForwarder bot has "forward" in its display name
2. Ensure the bot has Connect and Speak permissions
3. Check that the voice channel doesn't have restrictions blocking the bot

### Audio not working
**Solution**:
1. Verify FFmpeg is installed on your system
2. Check that all bots are connected to voice channels (`!bot_status`)
3. Ensure speaker channel has active speakers
4. Check logs in the `logs/` directory

### Bot can't detect receiver bots
**Solution**:
1. Verify all AudioReceiver bots have names starting with `Rcv-`
2. Check that Server Members Intent is enabled for AudioBroadcast bot
3. Ensure all bots are in the same Discord server

## System Requirements

**Minimum:**
- RAM: 2GB
- CPU: 2 cores
- Storage: 1GB
- Python 3.8+
- FFmpeg

**Recommended for Production:**
- RAM: 4GB+ (add 1GB per 5 listener channels)
- CPU: 4+ cores
- Storage: 5GB+
- Stable, high-speed internet connection

## File Structure

```
discord-audio-router/
├── launcher.py                      # Main launcher script
├── manage_subscriptions.py          # Subscription management CLI
├── manage_urls.py                   # Bot URL management CLI
├── .env                             # Configuration (create from env.example)
├── data/
│   ├── subscriptions.db            # SQLite subscription database
│   ├── bot_urls.json               # Bot invite URLs for users
│   └── control_panel_panels.json   # Control panel state
├── logs/                           # Application logs
└── src/
    └── discord_audio_router/       # Main application code
```

## License

**Copyright (c) 2024-2025 - All Rights Reserved**

This project is for **personal, educational, and non-commercial use only**.

### You MAY:
- Use for personal, non-commercial purposes
- Study and learn from the code
- Modify for personal use
- Run on your own Discord servers

### You MAY NOT:
- Sell, license, or commercialize this software
- Offer as a paid service
- Redistribute for commercial purposes
- Remove copyright notices

### Discord Policy Compliance

This software must comply with:
- [Discord Terms of Service](https://discord.com/terms)
- [Discord Developer Terms](https://discord.com/developers/docs/policies-and-agreements/developer-terms-of-service)
- [Discord Developer Policy](https://support-dev.discord.com/hc/en-us/articles/8563934450327)

**For commercial use or licensing inquiries, contact the owner for written permission.**

### Disclaimer

THIS SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND. THE AUTHOR IS NOT RESPONSIBLE FOR ANY DAMAGES ARISING FROM USE. USERS ARE SOLELY RESPONSIBLE FOR COMPLIANCE WITH ALL LAWS AND DISCORD POLICIES.

## Getting Started Checklist

- [ ] Create all Discord bots in Developer Portal
- [ ] Enable Server Members Intent and Message Content Intent for **AudioBroadcast bot only**
- [ ] Set correct display names (Fwd-Speaker, Rcv-1, Rcv-2, etc.)
- [ ] Invite all bots to your Discord server
- [ ] Copy `env.example` to `.env` and add bot tokens
- [ ] (Optional) Configure `data/bot_urls.json` with invite links
- [ ] Run `python launcher.py`
- [ ] Use `!control_panel` in Discord to create your first broadcast

**Happy Broadcasting! 🎵**

---

*A personal MVP project demonstrating multi-channel audio broadcasting in Discord.*
