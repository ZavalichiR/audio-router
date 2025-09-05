#!/usr/bin/env python3
"""
Discord Audio Router Launcher

A robust process manager for starting, stopping, and monitoring all bot components.
Supports both development and production environments.
"""

import asyncio
import argparse
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Set


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
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler("logs/launcher.log")
            ]
        )
        return logging.getLogger("launcher")
    
    def _load_environment(self) -> bool:
        """Load environment variables from config file."""
        if not os.path.exists(self.config_path):
            self.logger.error(f"Configuration file {self.config_path} not found")
            return False
        
        try:
            from dotenv import load_dotenv
            load_dotenv(self.config_path)
            self.logger.info(f"Loaded configuration from {self.config_path}")
            return True
        except ImportError:
            self.logger.error("python-dotenv not installed. Please install it with: pip install python-dotenv")
            return False
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}", exc_info=True)
            return False
    
    def _check_dependencies(self) -> bool:
        """Check if required dependencies are available."""
        required_deps = [
            ("discord.py", "discord"),
            ("websockets", "websockets"),
            ("aiohttp", "aiohttp"),
            ("numpy", "numpy"),
            ("ffmpeg-python", "ffmpeg")
        ]
        
        missing_deps = []
        for dep_name, import_name in required_deps:
            try:
                __import__(import_name)
            except ImportError:
                missing_deps.append(dep_name)
        
        if missing_deps:
            self.logger.error(f"Missing dependencies: {', '.join(missing_deps)}")
            self.logger.error("Install them with: pip install -r requirements.txt")
            return False
        
        return True
    
    def _ensure_directories(self):
        """Ensure required directories exist."""
        directories = ["logs", "data"]
        for directory in directories:
            Path(directory).mkdir(exist_ok=True)
    
    def start_component(self, component: str, args: List[str] = None) -> bool:
        """Start a specific component."""
        if component in self.processes:
            self.logger.warning(f"Component {component} is already running")
            return True
        
        try:
            # Prepare environment
            env = os.environ.copy()
            env["PYTHONPATH"] = str(Path.cwd())
            
            # Start the process
            cmd = [sys.executable] + (args or [])
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            self.processes[component] = process
            self.process_info[component] = {
                "start_time": time.time(),
                "command": " ".join(cmd),
                "pid": process.pid
            }
            
            self.logger.info(f"Started {component} (PID: {process.pid})")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start {component}: {e}", exc_info=True)
            return False
    
    def stop_component(self, component: str, timeout: int = 10) -> bool:
        """Stop a specific component gracefully."""
        if component not in self.processes:
            self.logger.warning(f"Component {component} is not running")
            return True
        
        process = self.processes[component]
        
        try:
            # Try graceful shutdown first
            process.terminate()
            
            # Wait for graceful shutdown
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self.logger.warning(f"Component {component} did not stop gracefully, forcing shutdown")
                process.kill()
                process.wait()
            
            del self.processes[component]
            del self.process_info[component]
            
            self.logger.info(f"Stopped {component}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to stop {component}: {e}", exc_info=True)
            return False
    
    def stop_all(self, timeout: int = 15) -> bool:
        """Stop all components gracefully."""
        self.logger.info("Stopping all components...")
        success = True
        
        for component in list(self.processes.keys()):
            if not self.stop_component(component, timeout):
                success = False
        
        return success
    
    def get_status(self) -> Dict[str, Dict]:
        """Get status of all components."""
        status = {}
        
        for component, process in self.processes.items():
            info = self.process_info[component].copy()
            info["running"] = process.poll() is None
            info["return_code"] = process.returncode
            info["uptime"] = time.time() - info["start_time"]
            status[component] = info
        
        return status
    
    def monitor_health(self, interval: int = 30):
        """Monitor component health and restart if needed."""
        while self.running:
            try:
                for component, process in list(self.processes.items()):
                    if process.poll() is not None:
                        self.logger.warning(f"Component {component} has stopped unexpectedly")
                        # Could implement auto-restart here if desired
                
                time.sleep(interval)
            except KeyboardInterrupt:
                break
    
    def start_main_bot(self) -> bool:
        """Start the AudioBroadcast bot."""
        return self.start_component("audiobroadcast_bot", ["start_bot.py"])
    
    def start_relay_server(self) -> bool:
        """Start the WebSocket relay server."""
        return self.start_component("relay_server", ["websocket_relay.py"])
    
    def start_all(self) -> bool:
        """Start all components."""
        self.logger.info("Starting Discord Audio Router...")
        
        # Ensure directories exist
        self._ensure_directories()
        
        # Load configuration
        if not self._load_environment():
            return False
        
        # Check dependencies
        if not self._check_dependencies():
            return False
        
        # Start components
        success = True
        
        # Start relay server first (if needed)
        if os.getenv("START_RELAY_SERVER", "true").lower() == "true":
            if not self.start_relay_server():
                self.logger.warning("Failed to start relay server, continuing...")
        
        # Start main bot
        if not self.start_main_bot():
            success = False
        
        if success:
            self.logger.info("All components started successfully")
            self.running = True
        else:
            self.logger.error("Some components failed to start")
            self.stop_all()
        
        return success


def signal_handler(signum, frame, manager: ProcessManager):
    """Handle shutdown signals."""
    print(f"\nReceived signal {signum}, shutting down...")
    manager.running = False
    manager.stop_all()
    sys.exit(0)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Discord Audio Router Launcher")
    parser.add_argument("--config", "-c", default=".env", help="Configuration file path")
    parser.add_argument("--component", help="Start specific component (audiobroadcast_bot, relay_server)")
    parser.add_argument("--no-relay", action="store_true", help="Don't start relay server")
    parser.add_argument("--monitor", action="store_true", help="Enable health monitoring")
    parser.add_argument("--status", action="store_true", help="Show component status")
    
    args = parser.parse_args()
    
    # Ensure logs directory exists
    os.makedirs("logs", exist_ok=True)
    
    manager = ProcessManager(args.config)
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, lambda s, f: signal_handler(s, f, manager))
    signal.signal(signal.SIGTERM, lambda s, f: signal_handler(s, f, manager))
    
    try:
        if args.status:
            # Show status (would need to read from PID files in production)
            print("Status check not implemented yet")
            return
        
        if args.component:
            # Start specific component
            if args.component == "audiobroadcast_bot":
                success = manager.start_main_bot()
            elif args.component == "relay_server":
                success = manager.start_relay_server()
            else:
                print(f"Unknown component: {args.component}")
                return
            
            if not success:
                sys.exit(1)
        else:
            # Start all components
            if args.no_relay:
                os.environ["START_RELAY_SERVER"] = "false"
            
            if not manager.start_all():
                sys.exit(1)
        
        # Keep running and monitor health if requested
        if args.monitor:
            manager.monitor_health()
        else:
            # Wait for all processes
            try:
                while manager.processes:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
        
    except Exception as e:
        manager.logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        manager.stop_all()


if __name__ == "__main__":
    main()
