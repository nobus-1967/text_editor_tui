"""Tests for Text Editor TUI 0.2.0."""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from textual._xterm_parser import XTermParser

from text_editor_tui import text_ops as ops
from text_editor_tui.compat import restore_alt_key_shortcuts
from text_editor_tui.constants import (
    APP_NAME,
    CONFIG_DIR,
    DEFAULT_THEME,
    RELEASE,
    THEME_FILE,
    THEMES,
    VERSION,
)
from text_editor_tui.help_text import about_markdown, shortcuts_markdown
from text_editor_tui.helpers import (
    cleanup_temp_files,
    clear_pending_text,
    ensure_cache_dir,
    export_to_pdf,
    get_temp_file_path,
    load_temp_file,
    load_theme,
    save_temp_file,
    save_theme,
)
from text_editor_tui.main import build_parser, main
from text_editor_tui.themes import APP_THEMES, EDITOR_THEMES


class _IsolatedCacheMixin:
    """Point config and cache paths at a temporary directory."""

    def setUp(self) -> None:
        """Redirect config and cache paths to a fresh temporary directory."""
        import text_editor_tui.helpers as helpers

        self._orig = (helpers.CONFIG_DIR, helpers.THEME_FILE, helpers.CACHE_DIR)
        self._tmp = Path(tempfile.mkdtemp(prefix="text_editor_tui-test-"))
        helpers.CONFIG_DIR = self._tmp / ".config" / "text_editor"
        helpers.THEME_FILE = helpers.CONFIG_DIR / "theme.json"
        helpers.CACHE_DIR = self._tmp / ".cache"

    def tearDown(self) -> None:
        """Restore the original config and cache paths."""
        import text_editor_tui.helpers as helpers

        helpers.CONFIG_DIR, helpers.THEME_FILE, helpers.CACHE_DIR = self._orig


class TestAppMetadata(unittest.TestCase):
    """Verify application metadata and theme definitions."""

    def test_app_name(self) -> None:
        """The application name is Text Editor TUI."""
        self.assertEqual(APP_NAME, "Text Editor TUI")

    def test_version(self) -> None:
        """The application version is 0.2.0."""
        self.assertEqual(VERSION, "0.2.0")

    def test_release(self) -> None:
        """The release identifier is 2026.11."""
        self.assertEqual(RELEASE, "2026.11")

    def test_themes(self) -> None:
        """Theme names and definitions are available."""
        self.assertEqual(THEMES, ("default", "green", "magenta", "blue"))
        self.assertEqual(set(APP_THEMES), set(THEMES))
        self.assertEqual(set(EDITOR_THEMES), set(THEMES))

    def test_config_path(self) -> None:
        """Theme settings are stored in ~/.config/text_editor/theme.json."""
        self.assertEqual(CONFIG_DIR, Path.home() / ".config" / "text_editor")
        self.assertEqual(THEME_FILE, CONFIG_DIR / "theme.json")


class TestCommandLine(unittest.TestCase):
    """Verify command-line options."""

    def _run(self, arguments: list[str]) -> tuple[int, str]:
        """Run *arguments* through ``main`` and capture standard output."""
        capture = io.StringIO()
        with (
            self.assertRaises(SystemExit) as raised,
            contextlib.redirect_stdout(capture),
        ):
            main(arguments)
        return raised.exception.code, capture.getvalue()

    def test_short_version(self) -> None:
        """-v prints the application name, version and release."""
        code, output = self._run(["-v"])
        self.assertEqual(code, 0)
        self.assertIn(f"{APP_NAME} {VERSION} ({RELEASE})", output)

    def test_long_version(self) -> None:
        """--version behaves exactly like -v."""
        short_code, short_output = self._run(["-v"])
        long_code, long_output = self._run(["--version"])
        self.assertEqual(short_code, long_code)
        self.assertEqual(short_output, long_output)

    def test_short_help(self) -> None:
        """-h prints usage information."""
        capture = io.StringIO()
        with (
            self.assertRaises(SystemExit) as raised,
            contextlib.redirect_stdout(capture),
        ):
            build_parser(prog="text_editor_tui").parse_args(["-h"])
        self.assertEqual(raised.exception.code, 0)
        output = capture.getvalue()
        self.assertIn("usage: text_editor_tui", output)
        self.assertIn(APP_NAME, output)
        self.assertIn("FILE", output)
        self.assertIn("-v, --version", output)

    def test_program_name_in_usage(self) -> None:
        """The parser accepts an explicit program name for help output."""
        parser = build_parser(prog="text-editor-bin")
        self.assertEqual(parser.prog, "text-editor-bin")


class TestThemeStorage(_IsolatedCacheMixin, unittest.TestCase):
    """Verify reading and writing the color-theme preference."""

    def test_default_theme(self) -> None:
        """A missing config file falls back to the default theme."""
        self.assertEqual(load_theme(), DEFAULT_THEME)

    def test_save_and_load_theme(self) -> None:
        """Every theme can be saved and loaded again."""
        for expected in THEMES:
            save_theme(expected)
            self.assertEqual(load_theme(), expected)

    def test_unknown_theme_falls_back(self) -> None:
        """An unknown mode resolves to the default theme."""
        self._tmp.joinpath(".config", "text_editor").mkdir(parents=True, exist_ok=True)
        self._tmp.joinpath(".config", "text_editor", "theme.json").write_text(
            '{"mode": "purple"}', encoding="utf-8"
        )
        self.assertEqual(load_theme(), DEFAULT_THEME)


class TestCacheAndTempFiles(_IsolatedCacheMixin, unittest.TestCase):
    """Verify cache and temporary file helpers."""

    def test_ensure_cache_dir(self) -> None:
        """ensure_cache_dir creates and returns the cache directory."""
        path = ensure_cache_dir()
        self.assertTrue(path.is_dir())
        self.assertEqual(path, self._tmp / ".cache")

    def test_temp_path_for_unsaved_file(self) -> None:
        """Unsaved documents use Temp.txt in the cache directory."""
        self.assertEqual(get_temp_file_path(None), self._tmp / ".cache" / "Temp.txt")

    def test_temp_path_for_saved_file(self) -> None:
        """Saved documents use a tilde-prefixed temporary file next to them."""
        path = self._tmp / "notes.txt"
        self.assertEqual(get_temp_file_path(path), self._tmp / "~notes.txt")

    def test_save_and_load_temp_file(self) -> None:
        """Temporary file content can be saved and restored."""
        save_temp_file("hello", None)
        self.assertEqual(load_temp_file(None), "hello")

    def test_cleanup_temp_files(self) -> None:
        """cleanup_temp_files removes temporary text backup files."""
        directory = self._tmp / "work"
        directory.mkdir()
        (directory / "~doc.txt").write_text("x", encoding="utf-8")
        (directory / "doc.txt").write_text("x", encoding="utf-8")
        cleanup_temp_files(directory)
        self.assertFalse((directory / "~doc.txt").exists())
        self.assertTrue((directory / "doc.txt").exists())

    def test_clear_pending_text(self) -> None:
        """clear_pending_text removes the cached unsaved buffer."""
        save_temp_file("pending", None)
        clear_pending_text()
        self.assertIsNone(load_temp_file(None))


class TestPDFExport(unittest.TestCase):
    """Verify direct Chromium PDF export of text files."""

    def setUp(self) -> None:
        """Create a temporary directory for source and output files."""
        self._tmp = Path(tempfile.mkdtemp(prefix="text_editor_tui-pdf-"))

    def tearDown(self) -> None:
        """Remove the temporary directory and its contents."""
        for path in sorted(self._tmp.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        self._tmp.rmdir()

    def test_uses_source_file_directly(self) -> None:
        """Chromium receives the open text file without an HTML conversion."""
        source = self._tmp / "notes.txt"
        source.write_text("hello", encoding="utf-8")
        output = self._tmp / "notes.pdf"
        calls: list[list[str]] = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return None

        with patch("text_editor_tui.helpers.subprocess.run", side_effect=fake_run):
            export_to_pdf(source, str(output))

        self.assertEqual(
            calls,
            [
                [
                    "chromium",
                    "--headless",
                    f"--print-to-pdf={output.resolve()}",
                    str(source.resolve()),
                ]
            ],
        )
        self.assertEqual(list(self._tmp.glob("*.html")), [])

    def test_source_without_extension(self) -> None:
        """A file without an extension is passed to Chromium unchanged."""
        source = self._tmp / "script"
        source.write_text("echo hello", encoding="utf-8")
        calls: list[list[str]] = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return None

        with patch("text_editor_tui.helpers.subprocess.run", side_effect=fake_run):
            export_to_pdf(source, str(self._tmp / "script.pdf"))

        self.assertEqual(calls[0][3], str(source.resolve()))

    def test_missing_chromium(self) -> None:
        """A missing Chromium executable raises a clear error."""
        source = self._tmp / "notes.txt"
        source.write_text("hello", encoding="utf-8")

        with (
            patch(
                "text_editor_tui.helpers.subprocess.run",
                side_effect=FileNotFoundError,
            ),
            self.assertRaisesRegex(RuntimeError, "Chromium is required"),
        ):
            export_to_pdf(source, str(self._tmp / "notes.pdf"))


class TestTextOps(unittest.TestCase):
    """Verify pure text transformations."""

    def test_move_lines_single(self) -> None:
        """A single line moves up and down."""
        self.assertEqual(
            ops.move_lines("first\nsecond\nthird", 1, 1, -1),
            ("second\nfirst\nthird", 0, 0),
        )
        self.assertEqual(
            ops.move_lines("first\nsecond\nthird", 1, 1, 1),
            ("first\nthird\nsecond", 2, 2),
        )

    def test_move_lines_block(self) -> None:
        """A selected block moves as a unit."""
        self.assertEqual(
            ops.move_lines("first\nsecond\nthird\nfourth", 1, 2, -1),
            ("second\nthird\nfirst\nfourth", 0, 1),
        )

    def test_move_lines_boundaries(self) -> None:
        """Moving past a document edge returns None."""
        self.assertIsNone(ops.move_lines("first\nsecond", 0, 0, -1))
        self.assertIsNone(ops.move_lines("first\nsecond", 1, 1, 1))

    def test_delete_line(self) -> None:
        """Deleting a line keeps a valid cursor location."""
        self.assertEqual(ops.delete_line("a\nb\nc", 1), ("a\nc", 1, 0))
        self.assertEqual(ops.delete_line("only", 0), ("", 0, 0))

    def test_indent_and_outdent(self) -> None:
        """Indenting and outdenting affect each selected line."""
        indented = ops.indent_lines("a\nb\nc", 0, 2)
        self.assertEqual(indented, "  a\n  b\n  c")
        self.assertEqual(ops.outdent_lines(indented, 0, 2), "a\nb\nc")
        self.assertEqual(ops.outdent_lines(" a", 0, 0), "a")


class TestHelpText(unittest.TestCase):
    """Verify help and about content."""

    def test_shortcuts_cover_menu_commands(self) -> None:
        """The shortcut sheet lists the simplified menu commands."""
        text = shortcuts_markdown()
        self.assertIn(APP_NAME, text)
        for label in (
            "New File",
            "Open...",
            "Save",
            "Save As...",
            "Toggle Theme",
            "Quit",
            "Date and Time...",
            "Add Indent",
            "Remove Indent",
            "Line Up",
            "Keyboard Shortcuts",
            "About Editor",
        ):
            self.assertIn(label, text)
        for removed in ("Export...", "Bold", "Heading 1", "Table...", "Paragraph"):
            self.assertNotIn(removed, text)

    def test_about_text(self) -> None:
        """The about text identifies the simplified editor."""
        text = about_markdown()
        self.assertIn(APP_NAME, text)
        self.assertIn(VERSION, text)
        self.assertIn("simple terminal text editor", text.lower())


class TestAltKeyCompat(unittest.TestCase):
    """Alt+key combinations survive terminal escape encoding."""

    def setUp(self) -> None:
        """Apply the compatibility fixes before parsing test sequences."""
        restore_alt_key_shortcuts()

    @staticmethod
    def _parse(sequence: str) -> list[str]:
        """Return the key names Textual reports for *sequence*."""
        parser = XTermParser()
        return [event.key for event in parser.feed(sequence)] + [
            event.key for event in parser.feed("")
        ]

    def test_alt_digits_and_punctuation(self) -> None:
        """Alt-modified keys keep the Alt modifier."""
        self.assertEqual(self._parse("\x1b1"), ["alt+1"])
        self.assertEqual(self._parse("\x1b-"), ["alt+minus"])


class TestTextualApp(_IsolatedCacheMixin, unittest.IsolatedAsyncioTestCase):
    """Smoke tests for the Textual application."""

    async def _make_app(self):
        """Return a new application instance."""
        from text_editor_tui.app import TextEditorApp

        return TextEditorApp()

    async def test_startup(self) -> None:
        """The application starts with an empty editor."""
        app = await self._make_app()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            self.assertEqual(app.editor.text, "")
            self.assertEqual(app.theme_mode, DEFAULT_THEME)
            self.assertIn(APP_NAME, app.title)
            self.assertIsNone(app.editor.language)

    async def test_function_key_bindings(self) -> None:
        """F1–F12 are mapped to the expected actions."""
        from text_editor_tui.app import TextEditorApp

        bindings = {
            key.strip(): binding.action
            for binding in TextEditorApp.BINDINGS
            for key in binding.key.split(",")
        }
        expected = {
            "f1": "help_shortcuts",
            "f2": "save_file",
            "f3": "save_as",
            "f4": "find",
            "f5": "replace",
            "f6": "select_all",
            "f7": "cut",
            "f8": "copy",
            "f9": "paste",
            "f10": "quit",
            "f11": "undo",
            "f12": "redo",
        }
        for key, action in expected.items():
            self.assertEqual(bindings[key], action)

    async def test_menus_and_shortcuts(self) -> None:
        """File/Edit/Help menus contain the simplified commands in order."""
        from textual.widgets import OptionList

        app = await self._make_app()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            expected_menus = {
                "File": [
                    "New File (Ctrl+N)",
                    "Open... (Ctrl+O)",
                    "Reopen (Ctrl+Shift+O)",
                    "Save (Ctrl+S / F2)",
                    "Save As... (Ctrl+Shift+S / F3)",
                    "Export to PDF (Ctrl+E)",
                    "Toggle Theme (Alt+T)",
                    "Quit (F10)",
                ],
                "Edit": [
                    "Undo (F11)",
                    "Redo (F12)",
                    "Cut (F7 / Shift+Delete)",
                    "Copy (F8 / Ctrl+C)",
                    "Paste (F9 / Shift+Insert)",
                    "Find... (F4 / Ctrl+F)",
                    "Replace... (F5 / Ctrl+R)",
                    "Select All (F6 / Ctrl+A)",
                    "Remove Selection (Ctrl+Shift+A)",
                    "Date and Time... (Ctrl+Shift+D)",
                    "Add Indent (Tab)",
                    "Remove Indent (Shift+Tab)",
                    "Line Up (Alt+Up)",
                    "Line Down (Alt+Down)",
                    "Go to Line... (Ctrl+_)",
                    "Delete Line (Alt+D)",
                ],
                "Help": [
                    "Keyboard Shortcuts (F1)",
                    "About Editor",
                ],
            }
            self.assertEqual(list(expected_menus), ["File", "Edit", "Help"])
            self.assertEqual(app.menu_items("Format"), [])
            self.assertEqual(app.menu_items("Paragraph"), [])
            for menu, labels in expected_menus.items():
                items = app.menu_items(menu)
                self.assertEqual(
                    [
                        f"{label} ({shortcut})" if shortcut else label
                        for label, _callback, shortcut in items
                    ],
                    labels,
                )
                app.open_menu(menu, items)
                await pilot.pause()
                option_list = app.screen.query_one("#menu-list", OptionList)
                shown = [
                    str(option_list.get_option_at_index(index).prompt)
                    for index in range(option_list.option_count)
                ]
                self.assertEqual(shown, labels)
                await pilot.press("escape")
                await pilot.pause()

    async def test_edit_menu_order(self) -> None:
        """Date/Time and Indent commands are placed as requested in Edit."""
        app = await self._make_app()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            labels = [label for label, _cb, _sc in app.menu_items("Edit")]
            self.assertLess(
                labels.index("Remove Selection"), labels.index("Date and Time...")
            )
            self.assertLess(
                labels.index("Date and Time..."), labels.index("Add Indent")
            )
            self.assertLess(labels.index("Add Indent"), labels.index("Remove Indent"))
            self.assertLess(labels.index("Remove Indent"), labels.index("Line Up"))

    async def test_export_to_pdf_action(self) -> None:
        """Export passes the open text file directly to Chromium."""
        app = await self._make_app()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            source = self._tmp / "note.txt"
            source.write_text("hello", encoding="utf-8")
            app._open_path(source)
            await pilot.pause()
            pdf_path = self._tmp / "note.pdf"
            inputs: list[str] = []

            def fake_run(cmd, **kwargs):
                inputs.append(cmd[3])
                output = Path(cmd[2].split("=", 1)[1])
                output.write_bytes(b"%PDF-1.4 test")
                return None

            with patch("text_editor_tui.helpers.subprocess.run", side_effect=fake_run):
                app.action_export_pdf()
                await pilot.pause()
                app.screen.query_one("#file-path").value = str(pdf_path)
                app.screen._activate_path()
                await pilot.pause()

            self.assertTrue(pdf_path.exists())
            self.assertEqual(inputs, [str(source.resolve())])
            self.assertFalse((self._tmp / "note.html").exists())

    async def test_export_to_pdf_without_extension(self) -> None:
        """A source file without an extension is passed to Chromium as-is."""
        app = await self._make_app()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            source = self._tmp / "script"
            source.write_text("echo hello", encoding="utf-8")
            app._open_path(source)
            await pilot.pause()
            inputs: list[str] = []

            def fake_run(cmd, **kwargs):
                inputs.append(cmd[3])
                output = Path(cmd[2].split("=", 1)[1])
                output.write_bytes(b"%PDF-1.4 test")
                return None

            with patch("text_editor_tui.helpers.subprocess.run", side_effect=fake_run):
                app._export_pdf_result(self._tmp / "script.pdf")
                await pilot.pause()

            self.assertEqual(inputs, [str(source.resolve())])

    async def test_export_to_pdf_unsaved_uses_temp_txt(self) -> None:
        """An unsaved buffer is printed from Temp.txt without HTML output."""
        app = await self._make_app()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.editor.load_text("unsaved text")
            await pilot.pause()
            inputs: list[str] = []

            def fake_run(cmd, **kwargs):
                html_path = Path(cmd[3])
                inputs.append(html_path.name)
                output = Path(cmd[2].split("=", 1)[1])
                output.write_bytes(b"%PDF-1.4 test")
                return None

            with patch("text_editor_tui.helpers.subprocess.run", side_effect=fake_run):
                app._export_pdf_result(self._tmp / "document.pdf")
                await pilot.pause()

            self.assertEqual(inputs, ["Temp.txt"])
            self.assertEqual(load_temp_file(None), "unsaved text")
            self.assertFalse((ensure_cache_dir() / "document.html").exists())

    async def test_external_change_reloads_file(self) -> None:
        """External edits update the buffer without changing the file path."""
        app = await self._make_app()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            path = self._tmp / "notes.txt"
            path.write_text("old", encoding="utf-8")
            app._open_path(path)
            await pilot.pause()
            path.write_text("new text", encoding="utf-8")
            app._check_external_change()
            await pilot.pause()
            self.assertEqual(app.editor.text, "new text")
            self.assertEqual(app.current_file, path.resolve())

    async def test_save_does_not_trigger_reload(self) -> None:
        """Saving updates the file signature so the editor keeps its buffer."""
        app = await self._make_app()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            path = self._tmp / "notes.txt"
            path.write_text("old", encoding="utf-8")
            app._open_path(path)
            await pilot.pause()
            app.editor.load_text("edited in app")
            await pilot.pause()
            app._save_to(path)
            await pilot.pause()
            app._check_external_change()
            await pilot.pause()
            self.assertEqual(app.editor.text, "edited in app")

    async def test_save_preserves_name_without_extension(self) -> None:
        """Saving preserves an explicit name without an extension."""
        app = await self._make_app()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            path = self._tmp / "script"
            app.editor.load_text("#!/bin/sh\n")
            await pilot.pause()
            app._save_to(path)
            await pilot.pause()
            self.assertTrue(path.exists())
            self.assertFalse((self._tmp / "script.txt").exists())
            self.assertEqual(app.current_file, path.resolve())

    async def test_save_preserves_existing_extension(self) -> None:
        """Saving an opened file keeps its original name and extension."""
        app = await self._make_app()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            path = self._tmp / "config.conf"
            path.write_text("old", encoding="utf-8")
            app._open_path(path)
            await pilot.pause()
            app.editor.load_text("new")
            await pilot.pause()
            app.action_save_file()
            await pilot.pause()
            self.assertEqual(path.read_text(encoding="utf-8"), "new")
            self.assertEqual(app.current_file, path.resolve())

    async def test_save_as_suggests_txt_for_new_file(self) -> None:
        """Save As suggests a .txt name for a new document."""
        app = await self._make_app()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.action_save_as()
            await pilot.pause()
            self.assertEqual(app.screen.dialog_title, "Save text file")
            self.assertTrue(
                app.screen.query_one("#file-path").value.endswith("untitled.txt")
            )
            await pilot.press("escape")
            await pilot.pause()

    async def test_save_and_open(self) -> None:
        """Saving and opening a text file round-trips content."""
        app = await self._make_app()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            path = self._tmp / "document.txt"
            app.editor.load_text("Hello\n")
            await pilot.pause()
            app._save_to(path)
            await pilot.pause()
            self.assertEqual(path.read_text(encoding="utf-8"), "Hello\n")
            app.editor.load_text("")
            app._open_path(path)
            await pilot.pause()
            self.assertEqual(app.editor.text, "Hello\n")

    async def test_find_and_replace(self) -> None:
        """Find, replace and replace-all work on plain text."""
        app = await self._make_app()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.editor.load_text("alpha beta alpha")
            self.assertTrue(app.find_next("alpha"))
            await pilot.pause()
            self.assertEqual(app.editor.selected_text, "alpha")
            self.assertTrue(app.replace_next("beta", "B"))
            await pilot.pause()
            self.assertIn("B", app.editor.text)
            count = app.replace_all("alpha", "X")
            await pilot.pause()
            self.assertEqual(count, 2)
            self.assertEqual(app.editor.text, "X B X")

    async def test_indent_and_line_actions(self) -> None:
        """Indent, outdent, line move and delete actions update the buffer."""
        app = await self._make_app()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.editor.load_text("a\nb\nc")
            app.editor.select_lines(0, 1)
            app.action_add_indent()
            await pilot.pause()
            self.assertEqual(app.editor.text, "  a\n  b\nc")
            app.action_remove_indent()
            await pilot.pause()
            self.assertEqual(app.editor.text, "a\nb\nc")
            app.editor.set_cursor(1, 0)
            app.action_line_up()
            await pilot.pause()
            self.assertEqual(app.editor.text, "b\na\nc")
            app.action_delete_line()
            await pilot.pause()
            self.assertEqual(app.editor.text, "a\nc")

    async def test_go_to_line(self) -> None:
        """Go to Line moves the cursor to the requested line."""
        app = await self._make_app()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.editor.load_text("one\ntwo\nthree\nfour")
            await pilot.press("ctrl+underscore")
            await pilot.pause()
            self.assertEqual(app.screen.form_title, "Go to Line")
            app.screen.query_one("#field-line").value = "3"
            app.screen._submit()
            await pilot.pause()
            self.assertEqual(app.editor.cursor_location, (2, 0))

    async def test_date_time_insert(self) -> None:
        """Date and Time inserts text at the cursor."""
        app = await self._make_app()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.editor.load_text("")
            app.action_date_time()
            await pilot.pause()
            self.assertEqual(app.screen.form_title, "Insert Date and Time")
            app.screen._submit()
            await pilot.pause()
            self.assertRegex(app.editor.text, r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")

    async def test_theme_toggle(self) -> None:
        """The theme toggle cycles through all themes and persists."""
        app = await self._make_app()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            current = app.theme_mode
            for _ in THEMES:
                expected = THEMES[(THEMES.index(current) + 1) % len(THEMES)]
                app.action_toggle_theme()
                await pilot.pause()
                self.assertEqual(app.theme_mode, expected)
                self.assertEqual(load_theme(), expected)
                current = expected

    async def test_help_dialogs(self) -> None:
        """Help actions open the expected information screens."""
        app = await self._make_app()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            for action, title in (
                (app.action_help_shortcuts, "Keyboard Shortcuts"),
                (app.action_about, "About"),
            ):
                action()
                await pilot.pause()
                self.assertEqual(app.screen.dialog_title, title)
                await pilot.press("escape")
                await pilot.pause()


if __name__ == "__main__":
    unittest.main()
