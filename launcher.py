#!/usr/bin/env python3
"""
Discord Audio Router Launcher

A robust process manager for starting, stopping, and monitoring all bot components.
Always starts all components with comprehensive error handling and validation.
"""

import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List


class ProcessManager:
    """Manages bot processes with health monitoring and graceful shutdown."""

    def __init__(self, config_path: str = ".env"):
        """Initialize the process manager."""
        self.config_path = config_path
        self.processes: Dict[str, subprocess.Popen] = {}
        self.process_info: Dict[str, Dict] = {}
        self.running = False
        self.logger = self._setup_logging()

    def _setup_logging(self) -> logging.Logger:
        """Set up logging for the launcher."""
        # Ensure logs directory exists
        Path("logs").mkdir(exist_ok=True)

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler("logs/launcher.log"),
            ],
        )
        return logging.getLogger("launcher")

    def _load_environment(self) -> bool:
        """Load environment variables from config file."""
        if not os.path.exists(self.config_path):
            self.logger.error(f"Configuration file {self.config_path} not found")
            return False

        try:
            from dotenv import load_dotenv

            load_dotenv(self.config_path, override=True)
            self.logger.info(f"Loaded configuration from {self.config_path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            return False

    def _validate_environment(self) -> bool:
        """Validate that all required environment variables are set."""
        required_vars = ["AUDIO_BROADCAST_TOKEN", "AUDIO_FORWARDER_TOKEN"]

        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)

        if missing_vars:
            self.logger.error(
                f"Missing required environment variables: {', '.join(missing_vars)}"
            )
            return False

        self.logger.info("Environment validation passed")
        return True

    def _validate_database(self) -> bool:
        """Validate that the database exists and is accessible."""
        try:
            # Check for common database file locations
            db_files = ["data/subscriptions.db", "subscriptions.db", "data/database.db"]

            db_found = False
            for db_file in db_files:
                if os.path.exists(db_file):
                    self.logger.info(f"Database file found: {db_file}")
                    db_found = True
                    break

            if not db_found:
                self.logger.warning("No database file found, but continuing...")
                # Don't fail here as the database might be created on first run

            self.logger.info("Database validation passed")
            return True

        except Exception as e:
            self.logger.error(f"Database validation failed: {e}")
            return False

    def _validate_bot_files(self) -> bool:
        """Validate that all required bot files exist."""
        required_files = [
            "src/discord_audio_router/bots/main_bot.py",
            "src/discord_audio_router/bots/forwarder_bot.py",
            "src/discord_audio_router/bots/receiver_bot.py",
            "src/discord_audio_router/networking/websocket_server.py",
        ]

        missing_files = []
        for file_path in required_files:
            if not os.path.exists(file_path):
                missing_files.append(file_path)

        if missing_files:
            self.logger.error(f"Missing required files: {', '.join(missing_files)}")
            return False

        self.logger.info("Bot files validation passed")
        return True

    def start_component(self, component: str, args: List[str] = None) -> bool:
        """Start a specific component with error handling."""
        if component in self.processes:
            self.logger.warning(f"Component {component} is already running")
            return True

        try:
            # Prepare environment
            env = os.environ.copy()
            src_path = str(Path.cwd() / "src")
            current_pythonpath = env.get("PYTHONPATH", "")
            if current_pythonpath:
                env["PYTHONPATH"] = f"{src_path}:{current_pythonpath}"
            else:
                env["PYTHONPATH"] = src_path

            # Start the process
            cmd = [sys.executable] + (args or [])
            self.logger.info(f"Starting {component} with command: {' '.join(cmd)}")

            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Store process info
            self.processes[component] = process
            self.process_info[component] = {
                "start_time": time.time(),
                "command": cmd,
                "pid": process.pid,
            }

            # Give the process a moment to start
            time.sleep(2)

            # Check if process is still running
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                self.logger.error(f"Component {component} failed to start")
                self.logger.error(f"STDOUT: {stdout}")
                self.logger.error(f"STDERR: {stderr}")
                return False

            self.logger.info(f"Started {component} (PID: {process.pid})")
            return True

        except Exception as e:
            self.logger.error(f"Failed to start {component}: {e}")
            return False

    def start_all_components(self) -> bool:
        """Start all components with validation and error handling."""
        self.logger.info("Starting Discord Audio Router...")

        # Step 1: Load environment
        if not self._load_environment():
            self.logger.error("Failed to load environment")
            return False

        # Step 2: Validate environment
        if not self._validate_environment():
            self.logger.error("Environment validation failed")
            return False

        # Step 3: Validate database
        if not self._validate_database():
            self.logger.error("Database validation failed")
            return False

        # Step 4: Validate bot files
        if not self._validate_bot_files():
            self.logger.error("Bot files validation failed")
            return False

        # Step 5: Start components
        components = [
            (
                "relay_server",
                ["-m", "discord_audio_router.networking.websocket_server"],
            ),
            ("audiobroadcast_bot", ["src/discord_audio_router/bots/main_bot.py"]),
        ]

        failed_components = []
        for component, args in components:
            if not self.start_component(component, args):
                failed_components.append(component)
                # Stop already started components
                self.stop_all()
                break

        if failed_components:
            self.logger.error(
                f"Failed to start components: {', '.join(failed_components)}"
            )
            return False

        self.logger.info("All components started successfully")
        return True

    def stop_component(self, component: str) -> bool:
        """Stop a specific component."""
        if component not in self.processes:
            self.logger.warning(f"Component {component} is not running")
            return True

        try:
            process = self.processes[component]
            process.terminate()

            # Wait for graceful shutdown
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.logger.warning(
                    f"Component {component} did not stop gracefully, forcing..."
                )
                process.kill()
                process.wait()

            del self.processes[component]
            del self.process_info[component]
            self.logger.info(f"Stopped {component}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to stop {component}: {e}")
            return False

    def stop_all(self) -> None:
        """Stop all components."""
        self.logger.info("Stopping all components...")

        for component in list(self.processes.keys()):
            self.stop_component(component)

        self.logger.info("All components stopped")

    def monitor_processes(self, interval: int = 5) -> None:
        """Monitor all processes and restart if needed."""
        self.logger.info("Starting process monitoring...")

        while self.running:
            try:
                for component, process in list(self.processes.items()):
                    if process.poll() is not None:
                        self.logger.error(
                            f"Component {component} has stopped unexpectedly"
                        )
                        # For now, just log the error. In production, you might want to restart
                        del self.processes[component]
                        if component in self.process_info:
                            del self.process_info[component]

                time.sleep(interval)
            except KeyboardInterrupt:
                break

    def run(self) -> None:
        """Main run loop."""
        try:
            # Start all components
            if not self.start_all_components():
                self.logger.error("Failed to start all components")
                sys.exit(1)

            self.running = True

            # Set up signal handlers for graceful shutdown
            def signal_handler(signum, frame):
                self.logger.info(f"Received signal {signum}, shutting down...")
                self.running = False
                self.stop_all()
                sys.exit(0)

            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)

            # Monitor processes
            self.monitor_processes()

        except Exception as e:
            self.logger.error(f"Fatal error: {e}")
            self.stop_all()
            sys.exit(1)


def main():
    """Main entry point."""
    print("🚀 Starting Discord Audio Router...")

    # Create and run the process manager
    manager = ProcessManager()
    manager.run()


if __name__ == "__main__":
    main()
