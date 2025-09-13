#!/usr/bin/env python3
"""
Development setup script for the Discord Audio Router system.

This script helps set up the development environment by:
- Creating necessary directories
- Setting up virtual environment
- Installing dependencies
- Running initial tests
"""

import os
import subprocess
import sys
from pathlib import Path


def run_command(command: str, description: str) -> bool:
    """Run a command and return success status."""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(
            command, shell=True, check=True, capture_output=True, text=True
        )
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e}")
        if e.stdout:
            print(f"STDOUT: {e.stdout}")
        if e.stderr:
            print(f"STDERR: {e.stderr}")
        return False


def create_directories():
    """Create necessary directories."""
    directories = [
        "logs",
        "data",
        "tests/fixtures",
        "examples",
    ]

    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"📁 Created directory: {directory}")


def setup_virtual_environment():
    """Set up Python virtual environment."""
    if not Path(".venv").exists():
        return run_command("python3 -m venv .venv", "Creating virtual environment")
    else:
        print("✅ Virtual environment already exists")
        return True


def install_dependencies():
    """Install project dependencies."""
    commands = [
        ("source .venv/bin/activate && pip install --upgrade pip", "Upgrading pip"),
        (
            "source .venv/bin/activate && pip install -r requirements.txt",
            "Installing dependencies",
        ),
        (
            "source .venv/bin/activate && pip install -e .",
            "Installing package in development mode",
        ),
    ]

    success = True
    for command, description in commands:
        if not run_command(command, description):
            success = False

    return success


def run_tests():
    """Run the test suite."""
    return run_command(
        "source .venv/bin/activate && python -m pytest tests/ -v", "Running test suite"
    )


def main():
    """Main setup function."""
    print("🚀 Setting up Discord Audio Router development environment...")

    # Change to project root
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)

    steps = [
        ("Creating directories", create_directories),
        ("Setting up virtual environment", setup_virtual_environment),
        ("Installing dependencies", install_dependencies),
        ("Running tests", run_tests),
    ]

    success = True
    for step_name, step_func in steps:
        print(f"\n📋 {step_name}")
        if not step_func():
            success = False
            print(f"❌ {step_name} failed")
            break

    if success:
        print("\n🎉 Development environment setup completed successfully!")
        print("\n📝 Next steps:")
        print("1. Copy .env.example to .env and configure your bot tokens")
        print("2. Run 'source .venv/bin/activate' to activate the virtual environment")
        print(
            "3. Run 'python -m discord_audio_router.bots.main_bot' to start the main bot"
        )
    else:
        print("\n❌ Setup failed. Please check the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
