# Discord Audio Router - Makefile
# Provides convenient commands for development and deployment

.PHONY: help install install-dev clean test lint format docs build run-bot run-relay run-all

# Default target
help:
	@echo "Discord Audio Router - Available Commands:"
	@echo ""
	@echo "Development:"
	@echo "  install      Install the package in development mode"
	@echo "  install-dev  Install with development dependencies"
	@echo "  clean        Clean build artifacts and cache files"
	@echo ""
	@echo "Code Quality:"
	@echo "  test         Run tests"
	@echo "  lint         Run linting checks"
	@echo "  format       Format code with black and isort"
	@echo ""
	@echo "Documentation:"
	@echo "  docs         Build documentation"
	@echo "  docs-serve   Serve documentation locally"
	@echo ""
	@echo "Building:"
	@echo "  build        Build the package"
	@echo "  dist         Create distribution packages"
	@echo ""
	@echo "Running:"
	@echo "  run-bot      Start the Discord bot"
	@echo "  run-relay    Start the WebSocket relay server"
	@echo "  run-all      Start both bot and relay server"
	@echo "  run-monitor  Start with health monitoring"
	@echo "  run-status   Check component status"
	@echo ""
	@echo "Setup:"
	@echo "  setup        Initial project setup"
	@echo "  setup-env    Create .env file from example"

# Development setup
install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"
	pre-commit install

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete

# Code quality
test:
	python test_audio_router.py

test-pytest:
	pytest

lint:
	flake8 bots/ --max-line-length=88 --ignore=E203,W503

format:
	black bots/ --line-length=88
	isort src/ tests/ scripts/

# Documentation
docs:
	cd docs && make html

docs-serve:
	cd docs/_build/html && python -m http.server 8000

# Building
build:
	python -m build

dist: build

# Running
run-bot:
	python launcher.py --component main_bot

run-relay:
	python launcher.py --component relay_server

run-all:
	python launcher.py

run-monitor:
	python launcher.py --monitor

run-status:
	python launcher.py --status

# Setup
setup: setup-env install-dev
	@echo "Project setup complete!"
	@echo "1. Edit .env file with your bot tokens"
	@echo "2. Run 'make run-all' to start all components"
	@echo "3. Or use 'python launcher.py' for more control"

setup-env:
	@if [ ! -f .env ]; then \
		cp env.example .env; \
		echo "Created .env file from example"; \
		echo "Please edit .env with your bot tokens"; \
	else \
		echo ".env file already exists"; \
	fi

# Docker
docker-build:
	docker build -t discord-audio-router .

docker-run:
	docker-compose up

# Database
db-init:
	@echo "Initializing database..."
	python -c "from src.discord_audio_router.utils.database import init_database; init_database()"

# Logs
logs:
	tail -f logs/*.log

logs-clean:
	rm -f logs/*.log

