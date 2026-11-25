"""Application constants for Text Editor TUI."""

from __future__ import annotations

from pathlib import Path

APP_NAME = "Text Editor TUI"
VERSION = "0.2.0"
RELEASE = "2026.11"

CONFIG_DIR = Path.home() / ".config" / "text_editor"
THEME_FILE = CONFIG_DIR / "theme.json"

CACHE_DIR = Path.home() / ".cache" / "text_editor_tui"
TEMP_FILE = "Temp.txt"

THEMES: tuple[str, ...] = ("default", "green", "magenta", "blue")
DEFAULT_THEME = "default"
