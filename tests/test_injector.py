from evdev import ecodes as e

from blurt.injector import (
    UinputTyper,
    XdotoolTyper,
    make_typer,
    text_to_keystrokes,
    type_at_window,
)


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def run(self, args: list[str]) -> None:
        self.calls.append(args)


def test_type_at_window_activates_then_types() -> None:
    runner = FakeRunner()
    type_at_window(12345, "hello world", runner=runner, settle_ms=0)
    assert runner.calls == [
        ["xdotool", "windowactivate", "--sync", "12345"],
        ["xdotool", "type", "--clearmodifiers", "--delay", "0", "hello world"],
    ]


def test_type_at_window_skips_when_empty() -> None:
    runner = FakeRunner()
    type_at_window(12345, "", runner=runner, settle_ms=0)
    assert runner.calls == []


def test_type_at_window_without_window_id_just_types() -> None:
    runner = FakeRunner()
    type_at_window(None, "hi", runner=runner, settle_ms=0)
    assert runner.calls == [
        ["xdotool", "type", "--clearmodifiers", "--delay", "0", "hi"],
    ]


def test_type_at_window_append_return_adds_return_keystroke() -> None:
    runner = FakeRunner()
    type_at_window(42, "hello", runner=runner, settle_ms=0, append_return=True)
    assert runner.calls == [
        ["xdotool", "windowactivate", "--sync", "42"],
        ["xdotool", "type", "--clearmodifiers", "--delay", "0", "hello"],
        ["xdotool", "key", "--clearmodifiers", "Return"],
    ]


def test_type_at_window_append_return_with_empty_text_still_presses_return() -> None:
    runner = FakeRunner()
    type_at_window(42, "", runner=runner, settle_ms=0, append_return=True)
    assert runner.calls == [
        ["xdotool", "windowactivate", "--sync", "42"],
        ["xdotool", "key", "--clearmodifiers", "Return"],
    ]


# --- Wayland uinput typer ---


def test_text_to_keystrokes_handles_case_and_shifted_symbols() -> None:
    assert text_to_keystrokes("Hi!") == [
        ("KEY_H", True),
        ("KEY_I", False),
        ("KEY_1", True),
    ]


def test_text_to_keystrokes_handles_space_and_punctuation() -> None:
    assert text_to_keystrokes("a b.") == [
        ("KEY_A", False),
        ("KEY_SPACE", False),
        ("KEY_B", False),
        ("KEY_DOT", False),
    ]


def test_text_to_keystrokes_normalizes_smart_punctuation() -> None:
    # em-dash -> hyphen, curly quotes -> straight, ellipsis -> three dots
    assert text_to_keystrokes("—") == [("KEY_MINUS", False)]
    assert text_to_keystrokes("“") == [("KEY_APOSTROPHE", True)]
    assert text_to_keystrokes("…") == [
        ("KEY_DOT", False),
        ("KEY_DOT", False),
        ("KEY_DOT", False),
    ]


def test_text_to_keystrokes_skips_untypable_chars() -> None:
    assert text_to_keystrokes("a中b") == [("KEY_A", False), ("KEY_B", False)]


class FakeUInput:
    """Records (code, value) key events and syn() barriers."""

    def __init__(self) -> None:
        self.events: list[tuple[int, int]] = []
        self.syns: int = 0
        self.closed = False

    def write(self, etype: int, code: int, value: int) -> None:
        assert etype == e.EV_KEY
        self.events.append((code, value))

    def syn(self) -> None:
        self.syns += 1

    def close(self) -> None:
        self.closed = True


def _press_release(key_name: str, shift: bool) -> list[tuple[int, int]]:
    shift_code = e.ecodes["KEY_LEFTSHIFT"]
    code = e.ecodes[key_name]
    down = ([(shift_code, 1)] if shift else []) + [(code, 1)]
    up = [(code, 0)] + ([(shift_code, 0)] if shift else [])
    return down + up


def test_uinput_typer_emits_press_release_per_char() -> None:
    dev = FakeUInput()
    typer = UinputTyper(device=dev, settle_ms=0, key_delay_ms=0)
    typer(None, "Hi")
    assert dev.events == _press_release("KEY_H", True) + _press_release("KEY_I", False)


def test_uinput_typer_appends_return() -> None:
    dev = FakeUInput()
    typer = UinputTyper(device=dev, settle_ms=0, key_delay_ms=0)
    typer(None, "x", append_return=True)
    assert dev.events == _press_release("KEY_X", False) + _press_release("KEY_ENTER", False)


def test_uinput_typer_empty_text_with_return_presses_only_enter() -> None:
    dev = FakeUInput()
    typer = UinputTyper(device=dev, settle_ms=0, key_delay_ms=0)
    typer(None, "", append_return=True)
    assert dev.events == _press_release("KEY_ENTER", False)


def test_uinput_typer_empty_text_no_return_does_nothing() -> None:
    dev = FakeUInput()
    typer = UinputTyper(device=dev, settle_ms=0, key_delay_ms=0)
    typer(None, "")
    assert dev.events == []


def test_make_typer_selects_backend_by_session(monkeypatch) -> None:
    monkeypatch.setattr("blurt.injector.is_wayland", lambda: True)
    assert isinstance(make_typer(), UinputTyper)
    monkeypatch.setattr("blurt.injector.is_wayland", lambda: False)
    assert isinstance(make_typer(), XdotoolTyper)
