"""Modal screens used by the Text Editor TUI."""

from __future__ import annotations

import fnmatch
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    Input,
    Label,
    Markdown,
    OptionList,
    Select,
    Static,
)
from textual.widgets.option_list import Option


@dataclass
class FieldSpec:
    """Description of one field in a :class:`FormScreen`."""

    name: str
    label: str
    kind: str = "text"
    default: Any = ""
    options: tuple[tuple[str, str], ...] = ()
    placeholder: str = ""
    minimum: int = 0
    maximum: int = 9999


class FormScreen(ModalScreen[dict[str, Any] | None]):
    """A generic modal form returning a dictionary of submitted values."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(
        self,
        title: str,
        fields: Iterable[FieldSpec],
        *,
        submit_label: str = "OK",
        intro: str = "",
    ) -> None:
        """Create a form with the given title and field descriptions."""
        super().__init__()
        self.form_title = title
        self.fields = list(fields)
        self.submit_label = submit_label
        self.intro = intro
        self._inputs: dict[str, Input] = {}
        self._selects: dict[str, Select] = {}
        self._checks: dict[str, Checkbox] = {}

    def compose(self) -> ComposeResult:
        """Compose labels, fields and buttons."""
        with Vertical(id="dialog"):
            yield Label(self.form_title, id="dialog-title")
            if self.intro:
                yield Static(self.intro, classes="dialog-intro")
            with VerticalScroll(id="form-body"):
                for spec in self.fields:
                    if spec.kind == "bool":
                        yield Checkbox(
                            spec.label,
                            value=bool(spec.default),
                            id=f"field-{spec.name}",
                        )
                        continue
                    yield Label(spec.label, classes="field-label")
                    if spec.kind in {"select", "select_text"}:
                        options = list(spec.options)
                        values = {value for _, value in options}
                        default = str(spec.default) if spec.default else None
                        if default not in values:
                            default = options[0][1] if options else None
                        yield Select(
                            options,
                            value=default if default is not None else Select.BLANK,
                            allow_blank=False,
                            id=f"select-{spec.name}",
                        )
                        if spec.kind == "select_text":
                            yield Input(
                                value=str(spec.default or ""),
                                placeholder=spec.placeholder,
                                id=f"field-{spec.name}",
                            )
                        continue
                    if spec.kind == "int":
                        yield Input(
                            value=str(spec.default),
                            placeholder=spec.placeholder,
                            type="integer",
                            id=f"field-{spec.name}",
                        )
                    else:
                        yield Input(
                            value=str(spec.default or ""),
                            placeholder=spec.placeholder,
                            id=f"field-{spec.name}",
                        )
            with Horizontal(id="dialog-buttons"):
                yield Button(self.submit_label, variant="primary", id="dialog-ok")
                yield Button("Cancel", id="dialog-cancel")

    def on_mount(self) -> None:
        """Focus the first editable field."""
        self._collect_widgets()
        for spec in self.fields:
            widget = self._inputs.get(spec.name)
            if widget is not None:
                widget.focus()
                return
            select = self._selects.get(spec.name)
            if select is not None:
                select.focus()
                return
            check = self._checks.get(spec.name)
            if check is not None:
                check.focus()
                return
        self.query_one("#dialog-ok", Button).focus()

    def _collect_widgets(self) -> None:
        """Find and remember the widgets that belong to each field."""
        for widget in self.query(Input):
            if widget.id and widget.id.startswith("field-"):
                self._inputs[widget.id.removeprefix("field-")] = widget
        for widget in self.query(Select):
            if widget.id and widget.id.startswith("select-"):
                self._selects[widget.id.removeprefix("select-")] = widget
        for widget in self.query(Checkbox):
            if widget.id and widget.id.startswith("field-"):
                self._checks[widget.id.removeprefix("field-")] = widget

    @on(Select.Changed)
    def _select_changed(self, event: Select.Changed) -> None:
        """Fill the matching text entry when a drop-down option is chosen."""
        select_id = event.select.id or ""
        if not select_id.startswith("select-"):
            return
        name = select_id.removeprefix("select-")
        input_widget = self._inputs.get(name)
        if input_widget is not None and event.value is not Select.BLANK:
            input_widget.value = str(event.value)

    @on(Input.Submitted)
    def _submitted(self, _event: Input.Submitted) -> None:
        """Submit the form when Enter is pressed in a text field."""
        self._submit()

    @on(Button.Pressed, "#dialog-ok")
    def _ok_pressed(self) -> None:
        """Submit the form."""
        self._submit()

    @on(Button.Pressed, "#dialog-cancel")
    def _cancel_pressed(self) -> None:
        """Cancel the form."""
        self.dismiss(None)

    def action_cancel(self) -> None:
        """Cancel the form with Escape."""
        self.dismiss(None)

    def _submit(self) -> None:
        """Collect values and dismiss with the result."""
        result: dict[str, Any] = {}
        for spec in self.fields:
            if spec.kind == "bool":
                check = self._checks.get(spec.name)
                result[spec.name] = bool(check.value) if check else False
                continue
            input_widget = self._inputs.get(spec.name)
            if spec.kind == "int":
                raw = input_widget.value.strip() if input_widget else str(spec.default)
                try:
                    value = int(raw)
                except ValueError:
                    self.notify(f"{spec.label}: enter a whole number", severity="error")
                    return
                if value < spec.minimum or value > spec.maximum:
                    self.notify(
                        f"{spec.label}: use a number from "
                        f"{spec.minimum} to {spec.maximum}",
                        severity="error",
                    )
                    return
                result[spec.name] = value
                continue
            if spec.kind == "select" and input_widget is None:
                select = self._selects.get(spec.name)
                value = select.value if select else None
                result[spec.name] = None if value is Select.BLANK else value
                continue
            if spec.kind == "select_text":
                select = self._selects.get(spec.name)
                selected = select.value if select else None
                typed = input_widget.value.strip() if input_widget else ""
                result[spec.name] = typed or (
                    "" if selected is Select.BLANK else str(selected or "")
                )
                continue
            result[spec.name] = input_widget.value.strip() if input_widget else ""
        self.dismiss(result)


class ConfirmScreen(ModalScreen[bool]):
    """A small yes/no confirmation dialog."""

    BINDINGS = [Binding("escape", "no", "No")]

    def __init__(self, message: str, *, title: str = "Confirm") -> None:
        """Create a confirmation dialog with *message*."""
        super().__init__()
        self.message = message
        self.dialog_title = title

    def compose(self) -> ComposeResult:
        """Compose the dialog."""
        with Vertical(id="dialog", classes="dialog-small"):
            yield Label(self.dialog_title, id="dialog-title")
            yield Static(self.message, classes="dialog-message")
            with Horizontal(id="dialog-buttons"):
                yield Button("Yes", variant="primary", id="dialog-yes")
                yield Button("No", id="dialog-no")

    @on(Button.Pressed, "#dialog-yes")
    def _yes(self) -> None:
        """Confirm."""
        self.dismiss(True)

    @on(Button.Pressed, "#dialog-no")
    def _no(self) -> None:
        """Reject."""
        self.dismiss(False)

    def action_no(self) -> None:
        """Reject with Escape."""
        self.dismiss(False)


class InfoScreen(ModalScreen[None]):
    """A scrollable dialog showing Markdown help or about text."""

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("q", "close", "Close", show=False),
        Binding("pagedown", "page_down", "Page down", show=False),
        Binding("pageup", "page_up", "Page up", show=False),
        Binding("home", "scroll_top", "Top", show=False),
        Binding("end", "scroll_bottom", "Bottom", show=False),
    ]

    def __init__(self, title: str, body: str, *, markdown: bool = True) -> None:
        """Create an information screen."""
        super().__init__()
        self.dialog_title = title
        self.body = body
        self.is_markdown = markdown

    def compose(self) -> ComposeResult:
        """Compose the dialog."""
        with Vertical(id="info-dialog"):
            yield Label(self.dialog_title, id="dialog-title")
            if self.is_markdown:
                yield Markdown(self.body, id="info-body")
            else:
                with VerticalScroll(id="info-body"):
                    yield Static(self.body)
            with Horizontal(id="dialog-buttons"):
                yield Button("Close", variant="primary", id="dialog-close")

    @on(Button.Pressed, "#dialog-close")
    def _close_pressed(self) -> None:
        """Close the dialog."""
        self.dismiss(None)

    def action_close(self) -> None:
        """Close the dialog with Escape or q."""
        self.dismiss(None)

    def _scroll_body(self, method: str) -> None:
        """Call a scrolling method on the help body when it exists."""
        try:
            body = self.query_one("#info-body")
            getattr(body, method)()
        except Exception:
            pass

    def action_page_down(self) -> None:
        """Scroll the help text one page down."""
        self._scroll_body("scroll_page_down")

    def action_page_up(self) -> None:
        """Scroll the help text one page up."""
        self._scroll_body("scroll_page_up")

    def action_scroll_top(self) -> None:
        """Scroll the help text to the top."""
        self._scroll_body("scroll_home")

    def action_scroll_bottom(self) -> None:
        """Scroll the help text to the bottom."""
        self._scroll_body("scroll_end")


class MenuScreen(ModalScreen["Callable[[], Any] | None"]):
    """A keyboard- and mouse-friendly list of commands for one menu."""

    BINDINGS = [Binding("escape", "close", "Close")]

    def __init__(
        self,
        title: str,
        items: Iterable[tuple[str, Callable[[], Any], str]],
    ) -> None:
        """Create a menu with ``(label, callback, shortcut)`` items."""
        super().__init__()
        self.menu_title = title
        self.items = list(items)

    def compose(self) -> ComposeResult:
        """Compose the option list."""
        options = [
            Option(
                f"{label} ({shortcut})" if shortcut else label,
                id=str(index),
            )
            for index, (label, _callback, shortcut) in enumerate(self.items)
        ]
        with Vertical(id="menu-dialog"):
            yield Label(self.menu_title, id="dialog-title")
            yield OptionList(*options, id="menu-list", classes="menu-list")
            with Horizontal(id="dialog-buttons"):
                yield Button("Close", id="dialog-close")

    @on(OptionList.OptionSelected, "#menu-list")
    def _selected(self, event: OptionList.OptionSelected) -> None:
        """Dismiss the menu and return the selected command to the app."""
        if event.option.id is None:
            return
        index = int(event.option.id)
        callback = self.items[index][1]
        self.dismiss(callback)

    @on(Button.Pressed, "#dialog-close")
    def _close_pressed(self) -> None:
        """Close the menu."""
        self.dismiss(None)

    def action_close(self) -> None:
        """Close the menu with Escape."""
        self.dismiss(None)


class FindScreen(ModalScreen[None]):
    """Find text and select the next match in the editor."""

    BINDINGS = [Binding("escape", "close", "Close")]

    def __init__(self) -> None:
        """Create the find dialog."""
        super().__init__()
        self._entry = Input(placeholder="Search text...", id="find-text")
        self._regex = Checkbox("Use regular expression", id="find-regex")

    def compose(self) -> ComposeResult:
        """Compose the dialog."""
        with Vertical(id="dialog"):
            yield Label("Find", id="dialog-title")
            yield Label("Find:", classes="field-label")
            yield self._entry
            yield self._regex
            with Horizontal(id="dialog-buttons"):
                yield Button("Find Next", variant="primary", id="find-next")
                yield Button("Close", id="find-close")

    def on_mount(self) -> None:
        """Focus the search entry."""
        self._entry.focus()

    @on(Input.Submitted, "#find-text")
    def _submitted(self, _event: Input.Submitted) -> None:
        """Find the next match on Enter."""
        self._find_next()

    @on(Button.Pressed, "#find-next")
    def _next_pressed(self) -> None:
        """Find the next match."""
        self._find_next()

    @on(Button.Pressed, "#find-close")
    def _close_pressed(self) -> None:
        """Close the dialog."""
        self.dismiss(None)

    def _find_next(self) -> None:
        """Ask the application to select the next match."""
        term = self._entry.value
        if not term:
            return
        found = self.app.find_next(term, self._regex.value)
        if not found:
            self.notify("Not found", severity="warning")

    def action_close(self) -> None:
        """Close the dialog with Escape."""
        self.dismiss(None)


class ReplaceScreen(ModalScreen[None]):
    """Find, replace one occurrence, or replace all occurrences."""

    BINDINGS = [Binding("escape", "close", "Close")]

    def __init__(self) -> None:
        """Create the replace dialog."""
        super().__init__()
        self._find = Input(placeholder="Find text...", id="replace-find")
        self._replacement = Input(placeholder="Replacement text...", id="replace-with")
        self._regex = Checkbox("Use regular expression", id="replace-regex")

    def compose(self) -> ComposeResult:
        """Compose the dialog."""
        with Vertical(id="dialog", classes="dialog-wide"):
            yield Label("Replace", id="dialog-title")
            yield Label("Find:", classes="field-label")
            yield self._find
            yield Label("Replace with:", classes="field-label")
            yield self._replacement
            yield self._regex
            with Horizontal(id="dialog-buttons"):
                yield Button("Find Next", id="replace-next")
                yield Button("Replace", id="replace-one")
                yield Button("Replace All", id="replace-all")
                yield Button("Close", id="replace-close")

    def on_mount(self) -> None:
        """Focus the find entry."""
        self._find.focus()

    @on(Input.Submitted, "#replace-find")
    def _find_submitted(self, _event: Input.Submitted) -> None:
        """Find the next match on Enter."""
        self._find_next()

    @on(Button.Pressed, "#replace-next")
    def _next_pressed(self) -> None:
        """Find the next match."""
        self._find_next()

    @on(Button.Pressed, "#replace-one")
    def _replace_pressed(self) -> None:
        """Replace the next match."""
        count = self.app.replace_next(
            self._find.value, self._replacement.value, self._regex.value
        )
        if not count:
            self.notify("Not found", severity="warning")

    @on(Button.Pressed, "#replace-all")
    def _replace_all_pressed(self) -> None:
        """Replace all matches."""
        count = self.app.replace_all(
            self._find.value, self._replacement.value, self._regex.value
        )
        self.notify(f"Replaced {count} occurrence(s)")

    @on(Button.Pressed, "#replace-close")
    def _close_pressed(self) -> None:
        """Close the dialog."""
        self.dismiss(None)

    def _find_next(self) -> None:
        """Select the next match."""
        if self._find.value and not self.app.find_next(
            self._find.value, self._regex.value
        ):
            self.notify("Not found", severity="warning")

    def action_close(self) -> None:
        """Close the dialog with Escape."""
        self.dismiss(None)


class FileDialogScreen(ModalScreen[Path | None]):
    """A terminal-native open/save dialog with a directory listing."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(
        self,
        *,
        mode: str = "open",
        title: str = "Open file",
        start: Path | None = None,
        patterns: tuple[str, ...] = ("*.txt", "*.text"),
        start_name: str = "",
    ) -> None:
        """Create a file dialog.

        ``mode`` is ``"open"`` or ``"save"``.  ``patterns`` filters the visible
        files; files that do not match are hidden unless "Show all files" is
        enabled.
        """
        super().__init__()
        self.mode = mode
        self.dialog_title = title
        start_dir = start.parent if start and start.is_file() else start
        self.cwd = (start_dir or Path.cwd()).expanduser().resolve()
        self.patterns = patterns
        self.start_name = start_name
        self._path = Input(id="file-path")
        self._show_all = Checkbox("Show all files", id="file-show-all")
        self._listing = OptionList(id="file-list")

    def compose(self) -> ComposeResult:
        """Compose the path entry, directory listing and buttons."""
        with Vertical(id="file-dialog"):
            yield Label(self.dialog_title, id="dialog-title")
            yield Label("Path:", classes="field-label")
            yield self._path
            yield self._show_all
            with VerticalScroll(id="file-list-wrap"):
                yield self._listing
            with Horizontal(id="dialog-buttons"):
                yield Button("Up", id="file-up")
                yield Button("Home", id="file-home")
                yield Button("Cancel", id="file-cancel")
                label = "Open" if self.mode == "open" else "Save"
                yield Button(label, variant="primary", id="file-accept")

    def on_mount(self) -> None:
        """Populate the listing and focus the path entry."""
        if self.start_name:
            self._path.value = str(self.cwd / self.start_name)
        else:
            self._path.value = str(self.cwd) + "/"
        self._refresh_listing()
        self._path.focus()

    def _refresh_listing(self) -> None:
        """Rebuild the option list from the current directory."""
        self._listing.clear_options()
        try:
            entries = sorted(
                self.cwd.iterdir(),
                key=lambda p: (not p.is_dir(), p.name.lower()),
            )
        except OSError as exc:
            self.notify(str(exc), severity="error")
            return
        if self.cwd.parent != self.cwd:
            self._listing.add_option(Option("../", id=str(self.cwd.parent)))
        for entry in entries:
            if entry.name.startswith(".") and not self._show_all.value:
                continue
            if entry.is_dir():
                self._listing.add_option(Option(f"{entry.name}/", id=str(entry)))
            elif self._show_all.value or any(
                fnmatch.fnmatch(entry.name, pattern) for pattern in self.patterns
            ):
                self._listing.add_option(Option(entry.name, id=str(entry)))

    @on(Checkbox.Changed, "#file-show-all")
    def _show_all_changed(self) -> None:
        """Refresh the listing when the filter changes."""
        self._refresh_listing()

    @on(OptionList.OptionSelected, "#file-list")
    def _listing_selected(self, event: OptionList.OptionSelected) -> None:
        """Navigate into a directory or choose a file."""
        if event.option.id is None:
            return
        path = Path(event.option.id)
        if path.is_dir():
            self._navigate(path)
        else:
            self._path.value = str(path)
            if self.mode == "open":
                self.dismiss(path)
            else:
                self._path.focus()

    @on(Input.Submitted, "#file-path")
    def _path_submitted(self, _event: Input.Submitted) -> None:
        """Activate the path entered by the user."""
        self._activate_path()

    @on(Button.Pressed, "#file-accept")
    def _accept_pressed(self) -> None:
        """Activate the path entered by the user."""
        self._activate_path()

    @on(Button.Pressed, "#file-up")
    def _up_pressed(self) -> None:
        """Go to the parent directory."""
        if self.cwd.parent != self.cwd:
            self._navigate(self.cwd.parent)

    @on(Button.Pressed, "#file-home")
    def _home_pressed(self) -> None:
        """Go to the home directory."""
        self._navigate(Path.home())

    @on(Button.Pressed, "#file-cancel")
    def _cancel_pressed(self) -> None:
        """Cancel the dialog."""
        self.dismiss(None)

    def _navigate(self, path: Path) -> None:
        """Change the current directory and update the input field."""
        self.cwd = path.expanduser().resolve()
        self._path.value = str(self.cwd) + "/"
        self._refresh_listing()

    def _activate_path(self) -> None:
        """Open or save the path entered in the input field."""
        raw = self._path.value.strip()
        if not raw:
            return
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = (self.cwd / path).resolve()
        if path.is_dir():
            self._navigate(path)
            return
        if self.mode == "open":
            if path.exists() and path.is_file():
                self.dismiss(path)
            else:
                self.notify("File does not exist", severity="error")
            return
        self.dismiss(path)

    def action_cancel(self) -> None:
        """Cancel the dialog with Escape."""
        self.dismiss(None)
