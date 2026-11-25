"""Helper utilities for Text Editor TUI."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from text_editor_tui.constants import (
    CACHE_DIR,
    CONFIG_DIR,
    DEFAULT_THEME,
    TEMP_FILE,
    THEME_FILE,
    THEMES,
)


def _read_config() -> dict:
    """Read the theme configuration file, returning an empty mapping on error."""
    try:
        return json.loads(THEME_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_config(**updates) -> None:
    """Merge *updates* into the theme configuration file."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = _read_config()
        data.update(updates)
        THEME_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


def load_theme() -> str:
    """Load the saved appearance mode from the theme configuration file."""
    name = str(_read_config().get("mode", DEFAULT_THEME)).lower()
    return name if name in THEMES else DEFAULT_THEME


def save_theme(name: str) -> None:
    """Save the current appearance mode."""
    _write_config(mode=name)


def ensure_cache_dir() -> Path:
    """Create and return the application cache directory."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR


def get_temp_file_path(current_file: Path | None) -> Path:
    """Return the recovery file path for the current document.

    - No file saved yet: ``~/.cache/text_editor_tui/Temp.txt``
    - File saved/opened: ``<dir>/~<name>`` next to the document
    """
    if current_file is None:
        return ensure_cache_dir() / TEMP_FILE
    return current_file.parent / f"~{current_file.name}"


def save_temp_file(text: str, current_file: Path | None) -> None:
    """Save *text* to the temporary file for the current document."""
    path = get_temp_file_path(current_file)
    path.write_text(text, encoding="utf-8")


def load_temp_file(current_file: Path | None) -> str | None:
    """Load text from the temporary file, returning ``None`` if absent."""
    path = get_temp_file_path(current_file)
    try:
        if path.exists():
            return path.read_text(encoding="utf-8")
    except Exception:
        pass
    return None


def _delete_tilde_files(directory: Path, suffix: str) -> None:
    """Delete temporary ``~*<suffix>`` files in *directory*."""
    try:
        if directory.exists():
            for file_path in directory.iterdir():
                if (
                    file_path.is_file()
                    and file_path.name.startswith("~")
                    and file_path.name.endswith(suffix)
                ):
                    file_path.unlink()
    except Exception:
        pass


def cleanup_temp_files(directory: Path) -> None:
    """Delete temporary text backup files in *directory*."""
    _delete_tilde_files(directory, ".txt")


def clear_pending_text() -> None:
    """Delete the cached unsaved-buffer file used for session restore."""
    (ensure_cache_dir() / TEMP_FILE).unlink(missing_ok=True)


def export_to_pdf(source: Path, path: str) -> None:
    """Print the text file *source* directly to PDF with headless Chromium.

    The input may have any extension or no extension at all. Chromium opens it
    as plain text; no intermediate HTML file is created.
    """
    input_path = source.expanduser().resolve()
    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [
                "chromium",
                "--headless",
                f"--print-to-pdf={output}",
                str(input_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("Chromium is required for PDF export") from exc
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.strip() or exc.stdout.strip()
        raise RuntimeError(
            message or f"Chromium failed with code {exc.returncode}"
        ) from exc
