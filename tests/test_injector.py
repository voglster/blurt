from blurt.injector import type_at_window


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
