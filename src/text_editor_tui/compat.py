"""Runtime compatibility fixes for third-party libraries."""

from __future__ import annotations

from collections.abc import Iterable
from typing import cast

from textual import _ansi_sequences, events
from textual._xterm_parser import XTermParser
from textual.keys import _character_to_key

_MACOS_OPTION_MAPPINGS: dict[str, str] = {
    "\x1b§": "§",
    "\x1b1": "¡",
    "\x1b2": "™",
    "\x1b3": "£",
    "\x1b4": "¢",
    "\x1b5": "∞",
    "\x1b6": "§",
    "\x1b7": "¶",
    "\x1b8": "•",
    "\x1b9": "ª",
    "\x1b0": "º",
    "\x1b-": "–",
    "\x1b=": "≠",
}

_PATCH_MARKER = "_mark_editor_alt_patch"


def _alt_key_name(sequence: str) -> str:
    """Return the Textual key name for *sequence* pressed together with Alt."""
    mapped = _ansi_sequences.ANSI_SEQUENCES_KEYS.get(sequence)
    if isinstance(mapped, tuple) and mapped:
        return mapped[0].value
    return _character_to_key(sequence)


def _patch_alt_punctuation() -> None:
    """Keep the Alt modifier for keys whose Textual name is a word.

    Textual prefixes ``alt+`` only when the key name is a single character.
    Punctuation and named keys such as ``minus`` or ``enter`` therefore lose
    the modifier and become indistinguishable from the unmodified key.
    """
    original = XTermParser._sequence_to_key_events
    if getattr(original, _PATCH_MARKER, False):
        return

    def sequence_to_key_events(
        self: XTermParser, sequence: str, alt: bool = False
    ) -> Iterable[events.Key]:
        """Yield key events, preserving Alt for named keys."""
        if alt and len(sequence) == 1:
            name = _alt_key_name(sequence)
            if len(name) > 1:
                yield events.Key(f"alt+{name}", sequence)
                return
        yield from original(self, sequence, alt)

    setattr(sequence_to_key_events, _PATCH_MARKER, True)
    XTermParser._sequence_to_key_events = sequence_to_key_events


def restore_alt_key_shortcuts() -> None:
    """Remove Textual's macOS Option-key mappings from the ANSI key table.

    Textual maps ``ESC 1``..``ESC 0`` to the characters that WezTerm on macOS
    produces for Option+digit.  On Linux terminals the same sequences encode
    Alt+digit, so the mapping turns shortcuts such as Alt+1 into typographic
    characters.  Removing the mappings lets Textual report Alt+digit instead.
    """
    table = cast(dict[str, object], _ansi_sequences.ANSI_SEQUENCES_KEYS)
    for sequence, character in _MACOS_OPTION_MAPPINGS.items():
        if table.get(sequence) == character:
            del table[sequence]
    _patch_alt_punctuation()
