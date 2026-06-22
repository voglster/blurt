from __future__ import annotations

import logging
import string
import subprocess
import time
from typing import Protocol

from evdev import ecodes

from blurt.session import is_wayland

log = logging.getLogger(__name__)


class Runner(Protocol):
    def run(self, args: list[str]) -> None: ...


class SubprocessRunner:
    def run(self, args: list[str]) -> None:
        subprocess.run(args, check=False)


def type_at_window(
    window_id: int | None,
    text: str,
    runner: Runner | None = None,
    settle_ms: int = 30,
    append_return: bool = False,
) -> None:
    """Restore focus to `window_id` (if given) and type `text` via xdotool.

    One-shot: no diff, no backspaces. The overlay UX guarantees the caller
    only invokes this on commit, after the user has visually verified the text.

    If `append_return` is True, a Return keystroke is sent after the text —
    used when commit was triggered by Enter (vs. the toggle key), matching
    user expectation of "Enter submits."
    """
    if not text and not append_return:
        return
    runner = runner or SubprocessRunner()
    if window_id is not None:
        runner.run(["xdotool", "windowactivate", "--sync", str(window_id)])
        if settle_ms > 0:
            time.sleep(settle_ms / 1000.0)
    if text:
        runner.run(["xdotool", "type", "--clearmodifiers", "--delay", "0", text])
    if append_return:
        runner.run(["xdotool", "key", "--clearmodifiers", "Return"])


class XdotoolTyper:
    """X11 typer: restores window focus and types via xdotool (XTEST)."""

    def __call__(
        self, window_id: int | None, text: str, append_return: bool = False
    ) -> None:
        type_at_window(window_id, text, append_return=append_return)


# --- Wayland uinput typer ---
#
# Under Wayland there is no XTEST, so xdotool cannot inject keystrokes. We
# instead create a virtual keyboard via /dev/uinput (the same evdev layer the
# hotkey listener reads from) and synthesize key events at the kernel level,
# below the compositor. This is compositor-agnostic — unlike `wtype`, which
# needs the wlroots virtual-keyboard protocol that GNOME/Mutter doesn't expose.

_SHIFT = "KEY_LEFTSHIFT"


def _build_char_keys() -> dict[str, tuple[str, bool]]:
    """Map each typable character to (evdev key name, needs-shift) for a US
    layout. Shift is needed for uppercase letters and shifted symbols."""
    m: dict[str, tuple[str, bool]] = {}
    for ch in string.ascii_lowercase:
        key = f"KEY_{ch.upper()}"
        m[ch] = (key, False)
        m[ch.upper()] = (key, True)
    shifted_digits = {
        "1": "!", "2": "@", "3": "#", "4": "$", "5": "%",
        "6": "^", "7": "&", "8": "*", "9": "(", "0": ")",
    }
    for digit, shifted in shifted_digits.items():
        m[digit] = (f"KEY_{digit}", False)
        m[shifted] = (f"KEY_{digit}", True)
    symbol_pairs = {
        "-": ("KEY_MINUS", "_"),
        "=": ("KEY_EQUAL", "+"),
        "[": ("KEY_LEFTBRACE", "{"),
        "]": ("KEY_RIGHTBRACE", "}"),
        "\\": ("KEY_BACKSLASH", "|"),
        ";": ("KEY_SEMICOLON", ":"),
        "'": ("KEY_APOSTROPHE", '"'),
        "`": ("KEY_GRAVE", "~"),
        ",": ("KEY_COMMA", "<"),
        ".": ("KEY_DOT", ">"),
        "/": ("KEY_SLASH", "?"),
    }
    for base, (key, shifted) in symbol_pairs.items():
        m[base] = (key, False)
        m[shifted] = (key, True)
    m[" "] = ("KEY_SPACE", False)
    m["\t"] = ("KEY_TAB", False)
    m["\n"] = ("KEY_ENTER", False)
    return m


_CHAR_KEYS = _build_char_keys()

# Non-ASCII characters the cleanup model commonly emits, mapped to ASCII so the
# US-layout keymap can type them. Values may expand to multiple characters.
_NORMALIZE = {
    "—": "-", "–": "-", "‒": "-", "−": "-",  # —, –, ‒, −
    "“": '"', "”": '"', "″": '"',                  # “, ”, ″
    "‘": "'", "’": "'", "′": "'",                  # ‘, ’, ′
    "…": "...",                                               # …
    " ": " ",                                                # nbsp
}


def text_to_keystrokes(text: str) -> list[tuple[str, bool]]:
    """Translate `text` into an ordered list of (key name, needs-shift) chords.

    Smart punctuation is normalized to ASCII first; characters with no key on a
    US layout (e.g. CJK, accented letters) are skipped with a debug log rather
    than aborting the whole transcript.
    """
    out: list[tuple[str, bool]] = []
    for raw in text:
        for ch in _NORMALIZE.get(raw, raw):
            spec = _CHAR_KEYS.get(ch)
            if spec is None:
                log.debug("uinput: no key for %r (U+%04X); skipping", ch, ord(ch))
                continue
            out.append(spec)
    return out


def _capabilities() -> dict[int, list[int]]:
    keys = {ecodes.ecodes[_SHIFT]}
    for key_name, _ in _CHAR_KEYS.values():
        keys.add(ecodes.ecodes[key_name])
    return {ecodes.EV_KEY: sorted(keys)}


class UinputTyper:
    """Wayland typer: synthesizes keystrokes through a /dev/uinput virtual
    keyboard. `window_id` is ignored — Wayland has no global window activation,
    so we rely on the daemon hiding the overlay first, which returns focus to
    the app the user was in."""

    def __init__(
        self,
        device: object | None = None,
        settle_ms: int = 30,
        key_delay_ms: int = 2,
    ) -> None:
        self._device = device  # evdev.UInput; lazily created if None
        self._settle_ms = settle_ms
        self._key_delay_ms = key_delay_ms

    def _ui(self) -> object:
        if self._device is None:
            from evdev import UInput

            self._device = UInput(_capabilities(), name="blurt-virtual-kbd")
            log.info("uinput virtual keyboard created")
        return self._device

    def _emit(self, ui: object, key_name: str, shift: bool) -> None:
        shift_code = ecodes.ecodes[_SHIFT]
        code = ecodes.ecodes[key_name]
        if shift:
            ui.write(ecodes.EV_KEY, shift_code, 1)
        ui.write(ecodes.EV_KEY, code, 1)
        ui.syn()
        ui.write(ecodes.EV_KEY, code, 0)
        if shift:
            ui.write(ecodes.EV_KEY, shift_code, 0)
        ui.syn()
        if self._key_delay_ms > 0:
            time.sleep(self._key_delay_ms / 1000.0)

    def __call__(
        self, window_id: int | None, text: str, append_return: bool = False
    ) -> None:
        if not text and not append_return:
            return
        keystrokes = text_to_keystrokes(text)
        if append_return:
            keystrokes.append(("KEY_ENTER", False))
        if not keystrokes:
            return
        ui = self._ui()
        if self._settle_ms > 0:
            time.sleep(self._settle_ms / 1000.0)
        for key_name, shift in keystrokes:
            self._emit(ui, key_name, shift)


def make_typer() -> XdotoolTyper | UinputTyper:
    """Pick the keystroke injector for the current session."""
    return UinputTyper() if is_wayland() else XdotoolTyper()
