"""Textual application for Text Editor TUI."""

from __future__ import annotations

import asyncio
import contextlib
import re
import signal
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.command import DiscoveryHit, Hit, Hits, Provider
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static, TextArea
from textual.widgets.text_area import Selection

from text_editor_tui import text_ops
from text_editor_tui.compat import restore_alt_key_shortcuts
from text_editor_tui.constants import APP_NAME, DEFAULT_THEME, THEMES, VERSION
from text_editor_tui.editor import TextEditor
from text_editor_tui.help_text import about_markdown, shortcuts_markdown
from text_editor_tui.helpers import (
    cleanup_temp_files,
    ensure_cache_dir,
    load_temp_file,
    load_theme,
    save_temp_file,
    save_theme,
)
from text_editor_tui.menubar import FunctionKeyBar, MenuBar
from text_editor_tui.screens import (
    ConfirmScreen,
    FieldSpec,
    FileDialogScreen,
    FindScreen,
    FormScreen,
    InfoScreen,
    MenuScreen,
    ReplaceScreen,
)
from text_editor_tui.themes import APP_THEMES, EDITOR_THEMES

Command = tuple[str, Callable[[], Any], str]

APP_ROOT = Path(__file__).resolve().parent
STYLES_PATH = APP_ROOT / "styles.tcss"


class EditorCommands(Provider):
    """Command-palette provider for editor commands."""

    async def search(self, query: str) -> Hits:
        """Search application commands by name."""
        matcher = self.matcher(query)
        app = cast("TextEditorApp", self.app)
        for label, callback, help_text in app.command_items():
            score = matcher.match(label)
            if score > 0:
                yield Hit(score, matcher.highlight(label), callback, help=help_text)

    async def discover(self) -> Hits:
        """Show all application commands when the palette is empty."""
        app = cast("TextEditorApp", self.app)
        for label, callback, help_text in app.command_items():
            yield DiscoveryHit(label, callback, help=help_text)


class TextEditorApp(App[None]):
    """Main Textual application."""

    CSS_PATH = str(STYLES_PATH)
    TITLE = APP_NAME
    SUB_TITLE = f"v{VERSION}"
    COMMANDS = App.COMMANDS | {EditorCommands}
    COMMAND_PALETTE_DISPLAY = "Ctrl+P"
    ENABLE_COMMAND_PALETTE = True

    BINDINGS = [
        Binding("f1", "help_shortcuts", "Help", show=True, priority=True),
        Binding("f2", "save_file", "Save", show=True, priority=True),
        Binding("f3", "save_as", "Save As", show=True, priority=True),
        Binding("f4", "find", "Find", show=True, priority=True),
        Binding("f5", "replace", "Replace", show=True, priority=True),
        Binding("f6", "select_all", "Select all", show=True, priority=True),
        Binding("f7", "cut", "Cut", show=True, priority=True),
        Binding("f8", "copy", "Copy", show=True, priority=True),
        Binding("f9", "paste", "Paste", show=True, priority=True),
        Binding("f10", "quit", "Quit", show=True, priority=True),
        Binding("f11", "undo", "Undo", show=True, priority=True),
        Binding("f12", "redo", "Redo", show=True, priority=True),
        Binding("ctrl+n", "new_file", "New", show=False, priority=True),
        Binding("ctrl+o", "open_file", "Open", show=False, priority=True),
        Binding("ctrl+shift+o", "reopen_file", "Reopen", show=False, priority=True),
        Binding("ctrl+s", "save_file", "Save", show=False, priority=True),
        Binding("ctrl+shift+s", "save_as", "Save As", show=False, priority=True),
        Binding("ctrl+z", "undo", "Undo", show=False, priority=True),
        Binding("ctrl+y", "redo", "Redo", show=False, priority=True),
        Binding("ctrl+x", "cut", "Cut", show=False, priority=True),
        Binding("shift+delete", "cut", "Cut", show=False, priority=True),
        Binding("ctrl+c", "copy", "Copy", show=False, priority=True),
        Binding("ctrl+v", "paste", "Paste", show=False, priority=True),
        Binding("shift+insert", "paste", "Paste", show=False, priority=True),
        Binding("ctrl+a", "select_all", "Select all", show=False, priority=True),
        Binding("ctrl+f", "find", "Find", show=False, priority=True),
        Binding("ctrl+r", "replace", "Replace", show=False, priority=True),
        Binding(
            "ctrl+shift+a", "remove_selection", "Deselect", show=False, priority=True
        ),
        Binding("ctrl+shift+d", "date_time", "Date/time", show=False, priority=True),
        Binding("alt+up", "line_up", "Line up", show=False, priority=True),
        Binding("alt+down", "line_down", "Line down", show=False, priority=True),
        Binding(
            "ctrl+underscore", "go_to_line", "Go to line", show=False, priority=True
        ),
        Binding("alt+d", "delete_line", "Delete line", show=False, priority=True),
        Binding("alt+t", "toggle_theme", "Theme", show=False, priority=True),
    ]

    COMMAND_SPECS: tuple[tuple[str, str, str, str], ...] = (
        ("File", "New File", "action_new_file", "Ctrl+N"),
        ("File", "Open...", "action_open_file", "Ctrl+O"),
        ("File", "Reopen", "action_reopen_file", "Ctrl+Shift+O"),
        ("File", "Save", "action_save_file", "Ctrl+S / F2"),
        ("File", "Save As...", "action_save_as", "Ctrl+Shift+S / F3"),
        ("File", "Toggle Theme", "action_toggle_theme", "Alt+T"),
        ("File", "Quit", "action_quit", "F10"),
        ("Edit", "Undo", "action_undo", "F11"),
        ("Edit", "Redo", "action_redo", "F12"),
        ("Edit", "Cut", "action_cut", "F7 / Shift+Delete"),
        ("Edit", "Copy", "action_copy", "F8 / Ctrl+C"),
        ("Edit", "Paste", "action_paste", "F9 / Shift+Insert"),
        ("Edit", "Find...", "action_find", "F4 / Ctrl+F"),
        ("Edit", "Replace...", "action_replace", "F5 / Ctrl+R"),
        ("Edit", "Select All", "action_select_all", "F6 / Ctrl+A"),
        ("Edit", "Remove Selection", "action_remove_selection", "Ctrl+Shift+A"),
        ("Edit", "Date and Time...", "action_date_time", "Ctrl+Shift+D"),
        ("Edit", "Add Indent", "action_add_indent", "Tab"),
        ("Edit", "Remove Indent", "action_remove_indent", "Shift+Tab"),
        ("Edit", "Line Up", "action_line_up", "Alt+Up"),
        ("Edit", "Line Down", "action_line_down", "Alt+Down"),
        ("Edit", "Go to Line...", "action_go_to_line", "Ctrl+_"),
        ("Edit", "Delete Line", "action_delete_line", "Alt+D"),
        ("Help", "Keyboard Shortcuts", "action_help_shortcuts", "F1"),
        ("Help", "About Editor", "action_about", ""),
    )

    def __init__(self, initial_file: Path | None = None) -> None:
        """Create the application, optionally opening *initial_file*."""
        restore_alt_key_shortcuts()
        super().__init__()
        for theme in APP_THEMES.values():
            self.register_theme(theme)
        self.initial_file = initial_file
        self.current_file: Path | None = None
        self.is_modified = False
        self.theme_mode = load_theme()
        self._suppress_change = 0

    def get_theme_variable_defaults(self) -> dict[str, str]:
        """Return fallback theme variables used while the stylesheet loads."""
        mode = getattr(self, "theme_mode", DEFAULT_THEME)
        return dict(APP_THEMES.get(mode, APP_THEMES[DEFAULT_THEME]).variables)

    def compose(self) -> ComposeResult:
        """Build the menu bar, editor, status bar and function-key bar."""
        with Vertical(id="main"):
            yield MenuBar()
            yield TextEditor(text="", id="editor", mode=self.theme_mode)
            yield Static("Ln 1, Col 1", id="status")
        yield FunctionKeyBar()

    async def on_function_key_bar_key_pressed(
        self, event: FunctionKeyBar.KeyPressed
    ) -> None:
        """Run the action of a clicked function key."""
        event.stop()
        await self.run_action(event.action)

    @property
    def editor(self) -> TextEditor:
        """Return the text editor widget."""
        return self.query_one("#editor", TextEditor)

    def on_mount(self) -> None:
        """Apply the saved theme and open the initial document."""
        self._install_signal_handlers()
        self._apply_theme(self.theme_mode)
        self.editor.focus()
        if self.initial_file is not None:
            self._open_path(self.initial_file)
        else:
            self._restore_pending_text()
        self._update_title()
        self._update_status()

    def _install_signal_handlers(self) -> None:
        """Clean temporary files on terminal hangup or termination signals."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        for sig_name in ("SIGHUP", "SIGTERM"):
            sig = getattr(signal, sig_name, None)
            if sig is None:
                continue
            with contextlib.suppress(NotImplementedError, RuntimeError, ValueError):
                loop.add_signal_handler(sig, self._handle_exit_signal, sig)

    def _handle_exit_signal(self, signum: int) -> None:
        """Remove temporary files and exit after a termination signal."""
        self._cleanup_temp_files()
        self.exit()

    def check_action(self, action: str, _parameters: tuple[object, ...]) -> bool:
        """Disable editor shortcuts while a modal dialog is open."""
        return not (isinstance(self.screen, ModalScreen) and action != "quit")

    def on_unmount(self) -> None:
        """Remove temporary files when the application closes."""
        self._cleanup_temp_files()

    def _update_title(self) -> None:
        """Refresh the window title with the file name and modified marker."""
        symbol = "*" if self.is_modified else ""
        name = self.current_file.name if self.current_file else "New File"
        self.title = f"{APP_NAME} - {symbol}{name}"
        self.sub_title = f"v{VERSION}"

    def _update_status(self) -> None:
        """Update line, column, selection and file information."""
        try:
            editor = self.editor
            row, col = editor.cursor_location
            selected = len(editor.selected_text)
            name = self.current_file.name if self.current_file else "untitled"
            mark = "*" if self.is_modified else ""
            selection = f"   Sel {selected}" if selected else ""
            text = (
                f" Ln {row + 1}, Col {col + 1}{selection}"
                f"   {mark}{name}   UTF-8   LF   Text "
            )
            self.query_one("#status", Static).update(text)
        except Exception:
            pass

    @on(TextArea.Changed)
    def _on_text_changed(self, _event: TextArea.Changed) -> None:
        """Track modifications and autosave the current buffer."""
        if self._suppress_change:
            self._suppress_change -= 1
            self._update_status()
            return
        self.is_modified = True
        self._update_title()
        self._update_status()
        with contextlib.suppress(OSError):
            save_temp_file(self.editor.text, self.current_file)

    @on(TextArea.SelectionChanged)
    def _on_selection_changed(self, _event: TextArea.SelectionChanged) -> None:
        """Refresh the cursor position in the status bar."""
        self._update_status()

    def _load_text(self, text: str) -> None:
        """Load text without marking the document as modified."""
        self._suppress_change += 1
        self.editor.load_text(text)

    def _apply_theme(self, mode: str) -> None:
        """Apply the selected color theme."""
        mode = mode if mode in THEMES else DEFAULT_THEME
        self.theme_mode = mode
        self.theme = APP_THEMES[mode].name
        with contextlib.suppress(Exception):
            self.editor.theme = EDITOR_THEMES[mode].name

    def action_toggle_theme(self) -> None:
        """Cycle through the available color themes."""
        next_index = (THEMES.index(self.theme_mode) + 1) % len(THEMES)
        self._apply_theme(THEMES[next_index])
        save_theme(self.theme_mode)
        self.notify(f"Theme: {self.theme_mode}")

    def _restore_pending_text(self) -> None:
        """Restore an unsaved buffer left by a previous session."""
        text = load_temp_file(None)
        if text and text.strip():
            self._load_text(text)
            self.is_modified = True
            self.notify("Restored unsaved text from the previous session")

    def _cleanup_temp_files(self) -> None:
        """Delete temporary files for the current document."""
        if self.current_file is not None:
            cleanup_temp_files(self.current_file.parent)
        cleanup_temp_files(ensure_cache_dir())

    def _open_path(self, path: Path) -> None:
        """Load *path* into the editor."""
        path = path.expanduser().resolve()
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            self.notify(
                f"Cannot open {path}: {exc}", title="Open file", severity="error"
            )
            return
        old_file = self.current_file
        self._load_text(text)
        self.current_file = path
        self.is_modified = False
        if old_file is not None:
            cleanup_temp_files(old_file.parent)
        self._update_title()
        self._update_status()
        self.editor.focus()
        self.notify(f"Opened {path.name}")

    def _save_to(self, path: Path) -> None:
        """Write the current buffer to *path*."""
        path = path.expanduser().resolve()
        old_file = self.current_file
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self.editor.text, encoding="utf-8")
        except OSError as exc:
            self.notify(
                f"Cannot save {path}: {exc}", title="Save file", severity="error"
            )
            return
        if old_file is not None and old_file.resolve() != path:
            cleanup_temp_files(old_file.parent)
        self.current_file = path
        self.is_modified = False
        self._update_title()
        self._update_status()
        self.editor.focus()
        self.notify(f"Saved {path}")

    def _confirm_discard(self, callback: Callable[[], None]) -> None:
        """Run *callback* after confirming that unsaved changes may be lost."""
        if not self.is_modified:
            callback()
            return

        def on_result(result: bool | None) -> None:
            """Discard the document when the user confirms."""
            if result:
                callback()

        self.push_screen(
            ConfirmScreen(
                "The document has unsaved changes. Discard them?",
                title="Unsaved changes",
            ),
            on_result,
        )

    def action_new_file(self) -> None:
        """Create an empty document."""
        self._confirm_discard(self._new_file)

    def _new_file(self) -> None:
        """Reset the editor to an empty untitled document."""
        old_file = self.current_file
        self._load_text("")
        self.current_file = None
        self.is_modified = False
        if old_file is not None:
            cleanup_temp_files(old_file.parent)
        self._update_title()
        self._update_status()
        self.editor.focus()

    def action_open_file(self) -> None:
        """Show the open-file dialog."""
        self._confirm_discard(self._show_open_dialog)

    def _show_open_dialog(self) -> None:
        """Push the open-file dialog."""
        self.push_screen(
            FileDialogScreen(
                mode="open",
                title="Open text file",
                start=self.current_file.parent if self.current_file else Path.cwd(),
                patterns=("*.txt", "*.text", "*.*"),
            ),
            self._open_dialog_result,
        )

    def _open_dialog_result(self, path: Path | None) -> None:
        """Open the selected file."""
        if path is not None:
            self._open_path(path)

    def action_reopen_file(self) -> None:
        """Reload the current file from disk."""
        if self.current_file is None:
            self.notify("No file is open", severity="warning")
            return
        self._confirm_discard(self._reopen_file)

    def _reopen_file(self) -> None:
        """Reload the current file without changing its path."""
        if self.current_file is None:
            return
        try:
            text = self.current_file.read_text(encoding="utf-8")
        except OSError as exc:
            self.notify(str(exc), title="Reopen file", severity="error")
            return
        self._load_text(text)
        self.is_modified = False
        self._update_title()
        self._update_status()
        self.editor.focus()
        self.notify("File reopened")

    def action_save_file(self) -> None:
        """Save to the current path or open Save As."""
        if self.current_file is not None:
            self._save_to(self.current_file)
        else:
            self.action_save_as()

    def action_save_as(self) -> None:
        """Show the save-as dialog."""
        start = self.current_file.parent if self.current_file else Path.cwd()
        name = self.current_file.name if self.current_file else "untitled.txt"
        self.push_screen(
            FileDialogScreen(
                mode="save",
                title="Save text file",
                start=start,
                start_name=name,
                patterns=("*.txt",),
            ),
            self._save_as_result,
        )

    def _save_as_result(self, path: Path | None) -> None:
        """Save to the path selected in the dialog."""
        if path is not None:
            self._save_to(path)

    def action_undo(self) -> None:
        """Undo the last edit."""
        self.editor.undo()

    def action_redo(self) -> None:
        """Redo the last undone edit."""
        self.editor.redo()

    def action_copy(self) -> None:
        """Copy the selection to the clipboard."""
        text = self.editor.selected_text
        if text:
            self.copy_to_clipboard(text)
            self.notify("Copied to clipboard")
        else:
            self.notify("Select text first", severity="warning")

    def action_cut(self) -> None:
        """Cut the selection to the clipboard."""
        text = self.editor.selected_text
        if not text:
            self.notify("Select text first", severity="warning")
            return
        self.copy_to_clipboard(text)
        self.editor.replace_selection("")
        self.editor.focus()

    def action_paste(self) -> None:
        """Paste clipboard text at the cursor."""
        text = self.clipboard
        if not text:
            self.notify(
                "Clipboard is empty; use the terminal paste shortcut",
                severity="warning",
            )
            return
        self.editor.replace_selection(text)
        self.editor.focus()

    def action_select_all(self) -> None:
        """Select the whole document."""
        self.editor.select_all()
        self.editor.focus()

    def action_remove_selection(self) -> None:
        """Collapse the selection without deleting text."""
        self.editor.move_cursor(self.editor.selection.end)
        self.editor.focus()

    def action_find(self) -> None:
        """Open the Find dialog."""
        self.push_screen(FindScreen())

    def action_replace(self) -> None:
        """Open the Replace dialog."""
        self.push_screen(ReplaceScreen())

    def _compile_pattern(self, term: str, use_regex: bool) -> re.Pattern | None:
        """Compile a search pattern, returning ``None`` for an empty term."""
        if not term:
            return None
        try:
            return re.compile(term if use_regex else re.escape(term))
        except re.error as exc:
            self.notify(f"Invalid regular expression: {exc}", severity="error")
            return None

    def find_next(self, term: str, use_regex: bool = False) -> bool:
        """Select the next match after the cursor, wrapping at the end."""
        pattern = self._compile_pattern(term, use_regex)
        if pattern is None:
            return False
        editor = self.editor
        text = editor.text
        start = editor.document.get_index_from_location(editor.selection.end)
        match = pattern.search(text, start) or pattern.search(text)
        if match is None:
            return False
        first = editor.document.get_location_from_index(match.start())
        last = editor.document.get_location_from_index(match.end())
        editor.selection = Selection(first, last)
        editor.scroll_cursor_visible()
        return True

    def replace_next(
        self, term: str, replacement: str, use_regex: bool = False
    ) -> bool:
        """Replace the next match."""
        if not self.find_next(term, use_regex):
            return False
        selected = self.editor.selected_text
        if use_regex:
            pattern = self._compile_pattern(term, True)
            if pattern is None:
                return False
            new_text = pattern.sub(replacement, selected, count=1)
        else:
            new_text = replacement
        self.editor.replace_selection(new_text)
        self.editor.focus()
        return True

    def replace_all(self, term: str, replacement: str, use_regex: bool = False) -> int:
        """Replace every occurrence and return the number of replacements."""
        if not term:
            return 0
        text = self.editor.text
        if use_regex:
            pattern = self._compile_pattern(term, True)
            if pattern is None:
                return 0
            new_text, count = pattern.subn(replacement, text)
        else:
            count = text.count(term)
            new_text = text.replace(term, replacement)
        if count:
            row, col = self.editor.cursor_location
            self.editor.replace_whole_text(new_text, cursor_row=row, cursor_col=col)
            self.editor.focus()
        return count

    def action_date_time(self) -> None:
        """Insert a formatted date and/or time."""
        options = (
            ("Date and time", "date_time"),
            ("Date only", "date"),
            ("Time only", "time"),
        )

        def on_result(result: dict[str, Any] | None) -> None:
            """Insert the selected date or time value."""
            if result is None:
                return
            now = datetime.now()
            choice = result["choice"]
            if choice == "date_time":
                value = now.strftime("%Y-%m-%d %H:%M:%S")
            elif choice == "date":
                value = now.strftime("%Y-%m-%d")
            else:
                value = now.strftime("%H:%M:%S")
            self.editor.replace_selection(value)
            self.editor.focus()

        self.push_screen(
            FormScreen(
                "Insert Date and Time",
                [
                    FieldSpec(
                        "choice",
                        "Insert:",
                        kind="select",
                        options=options,
                        default="date_time",
                    )
                ],
                submit_label="Insert",
            ),
            on_result,
        )

    def action_add_indent(self) -> None:
        """Indent the current line or selected lines by two spaces."""
        editor = self.editor
        start, end = editor.selection_line_range()
        has_selection = editor.selection.start != editor.selection.end
        new_text = text_ops.indent_lines(editor.text, start, end)
        editor.replace_whole_text(new_text, cursor_row=start, cursor_col=0)
        if has_selection:
            editor.select_lines(start, end)
        editor.focus()

    def action_remove_indent(self) -> None:
        """Remove up to two leading spaces from the current or selected lines."""
        editor = self.editor
        start, end = editor.selection_line_range()
        has_selection = editor.selection.start != editor.selection.end
        new_text = text_ops.outdent_lines(editor.text, start, end)
        editor.replace_whole_text(new_text, cursor_row=start, cursor_col=0)
        if has_selection:
            editor.select_lines(start, end)
        editor.focus()

    def action_line_up(self) -> None:
        """Move the current line or selected block one line up."""
        self._move_lines(-1)

    def action_line_down(self) -> None:
        """Move the current line or selected block one line down."""
        self._move_lines(1)

    def _move_lines(self, delta: int) -> None:
        """Move the current or selected line block by *delta*."""
        editor = self.editor
        has_selection = editor.selection.start != editor.selection.end
        start, end = editor.selection_line_range()
        result = text_ops.move_lines(editor.text, start, end, delta)
        if result is None:
            return
        new_text, new_start, new_end = result
        editor.replace_whole_text(new_text, cursor_row=new_start)
        if has_selection:
            editor.select_lines(new_start, new_end)
        editor.focus()

    def action_go_to_line(self) -> None:
        """Ask for a line number and move the cursor to that line."""

        def on_result(result: dict[str, Any] | None) -> None:
            """Move the cursor to the chosen line."""
            if result is None:
                return
            editor = self.editor
            row = max(0, min(int(result["line"]) - 1, editor.line_count - 1))
            editor.move_cursor((row, 0), center=True)
            editor.focus()

        line_count = max(1, self.editor.line_count)
        current_line = min(self.editor.cursor_row + 1, line_count)
        self.push_screen(
            FormScreen(
                "Go to Line",
                [
                    FieldSpec(
                        "line",
                        f"Line number (1–{line_count}):",
                        kind="int",
                        default=current_line,
                        minimum=1,
                        maximum=line_count,
                    )
                ],
                submit_label="Go",
            ),
            on_result,
        )

    def action_delete_line(self) -> None:
        """Delete the current line."""
        editor = self.editor
        new_text, row, col = text_ops.delete_line(editor.text, editor.cursor_row)
        editor.replace_whole_text(new_text, cursor_row=row, cursor_col=col)
        editor.focus()

    def action_help_shortcuts(self) -> None:
        """Show the keyboard-shortcuts screen."""
        self.push_screen(InfoScreen("Keyboard Shortcuts", shortcuts_markdown()))

    def action_about(self) -> None:
        """Show the About screen."""
        self.push_screen(InfoScreen("About", about_markdown()))

    def menu_items(self, menu: str) -> list[Command]:
        """Return ``(label, callback, shortcut)`` tuples for *menu*."""
        return [
            (label, getattr(self, action), shortcut)
            for name, label, action, shortcut in self.COMMAND_SPECS
            if name == menu
        ]

    def open_menu(self, title: str, items: list[Command]) -> None:
        """Show a menu and run the chosen command in the application context."""
        self.push_screen(MenuScreen(title, items), self._run_menu_command)

    def _run_menu_command(self, callback: Callable[[], Any] | None) -> None:
        """Run a command returned by :meth:`open_menu`."""
        if callback is not None:
            self.call_after_refresh(callback)

    def command_items(self) -> list[Command]:
        """Return all commands for the command palette."""
        items: list[Command] = []
        for menu, label, action, shortcut in self.COMMAND_SPECS:
            help_text = menu
            if shortcut:
                help_text += f" · {shortcut}"
            items.append((label, getattr(self, action), help_text))
        return items

    def on_menu_bar_menu_clicked(self, event: MenuBar.MenuClicked) -> None:
        """Open the menu that was clicked."""
        self.open_menu(event.menu, self.menu_items(event.menu))

    def action_quit(self) -> None:
        """Quit after confirming that unsaved changes may be lost."""
        self._confirm_discard(self._finish_quit)

    def _finish_quit(self) -> None:
        """Clean up temporary files and exit."""
        self._cleanup_temp_files()
        self.exit()
