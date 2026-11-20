"""Pure text transformations used by the text editor actions."""

from __future__ import annotations


def move_lines(
    text: str, start: int, end: int, delta: int
) -> tuple[str, int, int] | None:
    """Move the 0-based line block ``start..end`` by *delta*.

    Returns ``(new_text, new_start, new_end)`` or ``None`` at a document edge.
    """
    lines = text.split("\n")
    if delta < 0:
        if start <= 0:
            return None
        block = lines[start : end + 1]
        lines[start - 1 : end + 1] = [*block, lines[start - 1]]
        return "\n".join(lines), start - 1, end - 1
    if delta > 0:
        if end >= len(lines) - 1:
            return None
        block = lines[start : end + 1]
        lines[start : end + 2] = [lines[end + 1], *block]
        return "\n".join(lines), start + 1, end + 1
    return None


def delete_line(text: str, row: int) -> tuple[str, int, int]:
    """Delete 0-based *row* and return ``(new_text, cursor_row, cursor_col)``."""
    lines = text.split("\n")
    if not lines:
        return text, 0, 0
    row = max(0, min(row, len(lines) - 1))
    lines.pop(row)
    if not lines:
        lines = [""]
    new_row = min(row, len(lines) - 1)
    return "\n".join(lines), new_row, 0


def indent_lines(text: str, start: int, end: int, prefix: str = "  ") -> str:
    """Prefix every 0-based line in ``start..end`` with *prefix*."""
    lines = text.split("\n")
    for row in range(max(0, start), min(end, len(lines) - 1) + 1):
        lines[row] = prefix + lines[row]
    return "\n".join(lines)


def outdent_lines(text: str, start: int, end: int) -> str:
    """Remove up to two leading spaces from lines in ``start..end``."""
    lines = text.split("\n")
    for row in range(max(0, start), min(end, len(lines) - 1) + 1):
        if lines[row].startswith("  "):
            lines[row] = lines[row][2:]
        elif lines[row].startswith(" "):
            lines[row] = lines[row][1:]
    return "\n".join(lines)
