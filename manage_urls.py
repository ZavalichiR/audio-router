#!/usr/bin/env python3
"""
Simple script to manage bot URLs in the JSON file.
"""

import json
import sys
from pathlib import Path


def load_urls():
    """Load URLs from the JSON file."""
    file_path = Path("data/bot_urls.json")
    if not file_path.exists():
        print("Bot URLs file not found at data/bot_urls.json")
        return []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading URLs: {e}")
        return []


def save_urls(urls):
    """Save URLs to the JSON file."""
    file_path = Path("data/bot_urls.json")
    file_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(urls, f, indent=2)
        print(f"Saved {len(urls)} URLs to {file_path}")
        return True
    except Exception as e:
        print(f"Error saving URLs: {e}")
        return False


def list_urls():
    """List all URLs."""
    urls = load_urls()
    if not urls:
        print("No URLs found.")
        return

    print(f"Found {len(urls)} URLs:")
    for i, url in enumerate(urls, 1):
        print(f"{i:2d}. {url}")


def add_url(url):
    """Add a new URL."""
    urls = load_urls()
    if url in urls:
        print("URL already exists.")
        return

    urls.append(url)
    if save_urls(urls):
        print(f"Added URL: {url}")


def remove_url(index):
    """Remove URL by index."""
    urls = load_urls()
    if not urls:
        print("No URLs to remove.")
        return

    try:
        index = int(index) - 1  # Convert to 0-based index
        if 0 <= index < len(urls):
            removed_url = urls.pop(index)
            if save_urls(urls):
                print(f"Removed URL: {removed_url}")
        else:
            print(f"Invalid index. Use 1-{len(urls)}")
    except ValueError:
        print("Invalid index. Use a number.")


def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python manage_urls.py list")
        print("  python manage_urls.py add <url>")
        print("  python manage_urls.py remove <index>")
        return

    command = sys.argv[1].lower()

    if command == "list":
        list_urls()
    elif command == "add":
        if len(sys.argv) < 3:
            print("Usage: python manage_urls.py add <url>")
            return
        add_url(sys.argv[2])
    elif command == "remove":
        if len(sys.argv) < 3:
            print("Usage: python manage_urls.py remove <index>")
            return
        remove_url(sys.argv[2])
    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
