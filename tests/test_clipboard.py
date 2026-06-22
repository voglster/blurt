from blurt.clipboard import copy, make_copy


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], bytes]] = []

    def run(self, args: list[str], stdin_bytes: bytes) -> None:
        self.calls.append((args, stdin_bytes))


def test_copy_invokes_xclip_with_clipboard_selection() -> None:
    runner = FakeRunner()
    copy("hello world", runner=runner)
    assert runner.calls == [
        (["xclip", "-selection", "clipboard"], b"hello world"),
    ]


def test_copy_handles_empty_text() -> None:
    runner = FakeRunner()
    copy("", runner=runner)
    assert runner.calls == []


def test_copy_handles_unicode() -> None:
    runner = FakeRunner()
    copy("héllo", runner=runner)
    assert runner.calls[0][1] == "héllo".encode("utf-8")


def test_copy_uses_given_argv() -> None:
    runner = FakeRunner()
    copy("hi", runner=runner, argv=["wl-copy"])
    assert runner.calls == [(["wl-copy"], b"hi")]


def test_make_copy_selects_wl_copy_on_wayland(monkeypatch) -> None:
    monkeypatch.setattr("blurt.clipboard.is_wayland", lambda: True)
    runner = FakeRunner()
    make_copy(runner=runner)("hi")
    assert runner.calls == [(["wl-copy"], b"hi")]


def test_make_copy_selects_xclip_on_x11(monkeypatch) -> None:
    monkeypatch.setattr("blurt.clipboard.is_wayland", lambda: False)
    runner = FakeRunner()
    make_copy(runner=runner)("hi")
    assert runner.calls == [(["xclip", "-selection", "clipboard"], b"hi")]
