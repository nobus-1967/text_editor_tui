"""Help texts shown by Text Editor TUI."""

from __future__ import annotations

from text_editor_tui.constants import APP_NAME, RELEASE, VERSION


def shortcuts_markdown() -> str:
    """Return the keyboard-shortcuts cheat sheet as Markdown."""
    return f"""# {APP_NAME} {VERSION} ({RELEASE}) — Keyboard Shortcuts

The application runs in a terminal. The F1–F12 row follows the classic
console-editor layout and is the primary shortcut set. Ctrl and Alt combinations
remain available as aliases. The row ends with a clickable Ctrl+P command
palette hint.

### File

| Action | Shortcut |
| :--- | :--- |
| New File | Ctrl+N |
| Open... | Ctrl+O |
| Reopen | Ctrl+Shift+O |
| Save | Ctrl+S, F2 |
| Save As... | Ctrl+Shift+S, F3 |
| Toggle Theme | Alt+T |
| Quit | F10 |

### Edit

| Action | Shortcut |
| :--- | :--- |
| Undo | Ctrl+Z, F11 |
| Redo | Ctrl+Y, F12 |
| Cut | Ctrl+X, Shift+Delete, F7 |
| Copy | Ctrl+C, F8 |
| Paste | Ctrl+V, Shift+Insert, F9 |
| Find... | Ctrl+F, F4 |
| Replace... | Ctrl+R, F5 |
| Select All | Ctrl+A, F6 |
| Remove Selection | Ctrl+Shift+A |
| Date and Time... | Ctrl+Shift+D |
| Add Indent | Tab |
| Remove Indent | Shift+Tab |
| Line Up | Alt+Up |
| Line Down | Alt+Down |
| Go to Line... | Ctrl+_ |
| Delete Line | Alt+D |

### Help

| Action | Shortcut |
| :--- | :--- |
| Keyboard Shortcuts | F1 |
| About Editor | — |

### Command palette

| Action | Shortcut |
| :--- | :--- |
| Command palette | Ctrl+P |
| Menus | Mouse click |
| Close menu or command palette | Esc |
"""


def about_markdown() -> str:
    """Return the About text as Markdown."""
    return f"""# {APP_NAME}

Version **{VERSION}** ({RELEASE})

A simple terminal text editor written in Python with
[Textual](https://textual.textualize.io/).

It provides basic file operations, search and replace, line editing, indentation,
date and time insertion, multiple color themes, and a command palette.
"""
