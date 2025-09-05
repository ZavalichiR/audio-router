# Discord Audio Router - Architecture Documentation

## Overview

The Discord Audio Router is a professional audio routing system that enables one-to-many audio broadcasting in Discord voice channels. The system is built with a clean, modular architecture that separates concerns and promotes maintainability.

## Architecture Principles

### 1. Clean Architecture
The system follows clean architecture principles with clear separation between:
- **Core Business Logic**: Audio routing, section management, process coordination
- **Infrastructure**: Logging, configuration, network communication
- **Application Layer**: Bot implementations, command handlers
- **External Interfaces**: Discord API, WebSocket communication

### 2. Modular Design
Each component has a single responsibility and well-defined interfaces:
- **Core**: Business logic and orchestration
- **Audio**: Audio processing and handling
- **Networking**: WebSocket communication
- **Bots**: Discord bot implementations
- **Commands**: Command handlers and utilities
- **Config**: Configuration management
- **Infrastructure**: Cross-cutting concerns

### 3. Dependency Inversion
High-level modules don't depend on low-level modules. Both depend on abstractions.

## System Components

### Core Components

#### AudioRouter
The main orchestrator that coordinates all audio routing operations:
- Manages broadcast sections
- Coordinates bot processes
- Handles system lifecycle

#### SectionManager
Manages broadcast sections and their associated resources:
- Creates and manages voice channels
- Handles channel permissions
- Coordinates bot deployment

#### ProcessManager
Manages Discord bot processes:
- Spawns and monitors bot processes
- Handles process lifecycle
- Manages bot tokens

#### AccessControl
Handles role-based access control:
- Manages Discord roles
- Sets up channel permissions
- Validates user access

### Audio Components

#### AudioBuffer
Thread-safe buffer for Opus audio packets:
- Supports both async and sync interfaces
- Handles packet queuing and overflow
- Provides audio data to Discord voice system

#### OpusAudioSink
Captures audio from Discord voice channels:
- Receives Opus packets from Discord
- Filters invalid/silence packets
- Forwards audio via callbacks

#### OpusAudioSource
Plays audio to Discord voice channels:
- Reads from AudioBuffer
- Provides Opus packets to Discord
- Handles silence generation

### Networking Components

#### AudioRelayServer
Centralized WebSocket server for audio routing:
- Manages speaker-listener connections
- Routes audio data between bots
- Handles connection health monitoring

### Bot Implementations

#### AudioBroadcastBot (Main Bot)
The main control bot that provides user interface:
- Handles Discord commands
- Manages broadcast sections
- Provides status and monitoring

#### AudioForwarderBot
Captures audio from speaker channels:
- Connects to speaker voice channels
- Captures and forwards audio
- Manages WebSocket server

#### AudioReceiverBot
Plays audio to listener channels:
- Connects to listener voice channels
- Receives audio from forwarder bots
- Plays audio to Discord

## Data Flow

### 1. Audio Capture Flow
```
Speaker → AudioForwarderBot → WebSocket → AudioRelayServer → WebSocket → AudioReceiverBot → Listeners
```

### 2. Command Flow
```
User → Discord → AudioBroadcastBot → AudioRouter → SectionManager/ProcessManager → Discord API
```

### 3. Configuration Flow
```
Environment Variables → ConfigManager → SimpleConfig → Components
```

## Communication Patterns

### WebSocket Communication
- **Speaker Registration**: AudioForwarderBot registers with relay server
- **Listener Registration**: AudioReceiverBot registers with relay server
- **Audio Forwarding**: Real-time audio packet transmission
- **Health Monitoring**: Ping/pong for connection health

### Discord API Integration
- **Voice Channel Management**: Create, configure, and manage channels
- **Role Management**: Create and assign roles for access control
- **Audio Streaming**: Real-time audio capture and playback

## Error Handling

### Exception Hierarchy
```
AudioRouterError (Base)
├── ConfigurationError
├── BotProcessError
├── AudioProcessingError
└── NetworkError
```

### Error Recovery
- Automatic reconnection for network failures
- Process restart for bot failures
- Graceful degradation for partial failures

## Testing Strategy

### Unit Tests
- Test individual components in isolation
- Mock external dependencies
- Verify business logic correctness

### Integration Tests
- Test component interactions
- Verify WebSocket communication
- Test Discord API integration

### End-to-End Tests
- Test complete audio routing workflows
- Verify system behavior under load
- Test error scenarios and recovery

## Deployment Architecture

### Process Model
- **Main Process**: AudioBroadcastBot
- **Worker Processes**: AudioForwarderBot, AudioReceiverBot instances
- **Relay Server**: Centralized WebSocket server (optional)

### Scalability
- Horizontal scaling through multiple bot instances
- Centralized relay server for large deployments
- Process isolation for fault tolerance

## Security Considerations

### Access Control
- Role-based permissions
- Channel-level restrictions
- Bot token management

### Network Security
- Local WebSocket communication
- No external network exposure
- Secure token handling

## Monitoring and Observability

### Logging
- Structured logging with context
- Component-specific log files
- Configurable log levels

### Health Monitoring
- Process health checks
- Connection status monitoring
- Performance metrics

### Error Tracking
- Comprehensive error logging
- Exception context preservation
- Recovery attempt tracking
