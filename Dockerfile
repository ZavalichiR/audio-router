FROM python:3.11-slim

# Install system dependencies for audio processing
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create logs directory
RUN mkdir -p logs

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose ports for WebSocket communication
EXPOSE 8000-8100

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import asyncio; import websockets; print('Health check passed')" || exit 1

# Default command runs the main bot
# Override with docker run for different components:
# - Main bot: docker run <image> python start_bot.py
# - Speaker bot: docker run <image> python bots/speaker_bot.py
# - Listener bot: docker run <image> python bots/listener_bot.py
# - Relay server: docker run <image> python websocket_relay.py
CMD ["python", "start_bot.py"]
