"""Clickable menu bar and function-key bar for the Text Editor TUI."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.events import Click
from textual.message import Message
from textual.widgets import Static

MENU_NAMES = ("File", "Edit", "Help")

FUNCTION_KEYS: tuple[tuple[str, str, str], ...] = (
    ("F1", "help_shortcuts", "Help"),
    ("F2", "save_file", "Save"),
    ("F3", "save_as", "Save As"),
    ("F4", "find", "Find"),
    ("F5", "replace", "Replace"),
    ("F6", "select_all", "Select all"),
    ("F7", "cut", "Cut"),
    ("F8", "copy", "Copy"),
    ("F9", "paste", "Paste"),
    ("F10", "quit", "Quit"),
    ("F11", "undo", "Undo"),
    ("F12", "redo", "Redo"),
)


class MenuTitle(Static):
    """A single clickable menu title."""

    def __init__(self, label: str) -> None:
        """Create a menu title for *label*."""
        super().__init__(label, classes="menu-title")
        self.menu_name = label

    def on_click(self, _event: Click) -> None:
        """Ask the menu bar to open this menu."""
        self.post_message(MenuBar.MenuClicked(self.menu_name))


class MenuBar(Horizontal):
    """A row of clickable menu titles."""

    class MenuClicked(Message):
        """Posted when a menu title is clicked."""

        def __init__(self, menu: str) -> None:
            """Create the message for *menu*."""
            super().__init__()
            self.menu = menu

    def compose(self) -> ComposeResult:
        """Create the menu titles."""
        for name in MENU_NAMES:
            yield MenuTitle(name)


class FunctionKey(Static):
    """A clickable function key with its action name."""

    COMPONENT_CLASSES = {"function-key--key", "function-key--label"}

    def __init__(self, key: str, label: str, action: str) -> None:
        """Create a function key for *action*."""
        super().__init__(classes="function-key", id=f"function-{key.lower()}")
        self.function_key = key
        self.function_label = label
        self.function_action = action

    def render(self) -> Text:
        """Render the key name and its action label compactly."""
        key_style = self.get_component_rich_style("function-key--key")
        label_style = self.get_component_rich_style("function-key--label")
        text = Text.assemble(
            (f" {self.function_key}", key_style),
            (f" {self.function_label}", label_style),
        )
        text.stylize_before(self.rich_style)
        return text

    def on_click(self, _event: Click) -> None:
        """Ask the application to run this key's action."""
        self.post_message(FunctionKeyBar.KeyPressed(self.function_action))


class PaletteHint(Static):
    """A clickable Ctrl+P command-palette hint."""

    COMPONENT_CLASSES = {"function-key--key", "function-key--label"}

    def __init__(self) -> None:
        """Create the command-palette hint."""
        super().__init__("", classes="palette-hint", id="palette-hint")

    def render(self) -> Text:
        """Render the Ctrl+P chip and its label."""
        key_style = self.get_component_rich_style("function-key--key")
        label_style = self.get_component_rich_style("function-key--label")
        text = Text.assemble(
            (" Ctrl+P", key_style),
            (" Command palette", label_style),
        )
        text.stylize_before(self.rich_style)
        return text

    def on_click(self, _event: Click) -> None:
        """Open the command palette."""
        self.post_message(FunctionKeyBar.KeyPressed("command_palette"))


class FunctionKeyBar(Horizontal):
    """A row of clickable F1–F12 shortcuts in numeric order."""

    class KeyPressed(Message):
        """Posted when a function key is clicked."""

        def __init__(self, action: str) -> None:
            """Create the message for *action*."""
            super().__init__()
            self.action = action

    def compose(self) -> ComposeResult:
        """Create the function keys in numeric order, then the palette hint."""
        for key, action, label in FUNCTION_KEYS:
            yield FunctionKey(key, label, action)
        yield PaletteHint()
