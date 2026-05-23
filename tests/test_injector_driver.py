from blurt.injector import Injector


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def run(self, args: list[str]) -> None:
        self.calls.append(args)


def test_commit_initial_text() -> None:
    runner = FakeRunner()
    inj = Injector(runner=runner)
    inj.commit("hello")
    assert runner.calls == [
        ["xdotool", "type", "--clearmodifiers", "--delay", "0", "hello"],
    ]
    assert inj.last_typed == "hello"


def test_commit_extend() -> None:
    runner = FakeRunner()
    inj = Injector(runner=runner)
    inj.commit("hello")
    inj.commit("hello world")
    assert runner.calls[-1] == [
        "xdotool", "type", "--clearmodifiers", "--delay", "0", " world",
    ]
    assert inj.last_typed == "hello world"


def test_commit_replace_tail() -> None:
    runner = FakeRunner()
    inj = Injector(runner=runner)
    inj.commit("hello world")
    runner.calls.clear()
    inj.commit("hello there")
    assert runner.calls == [
        ["xdotool", "key", "--clearmodifiers", "--delay", "0", "--repeat", "5", "BackSpace"],
        ["xdotool", "type", "--clearmodifiers", "--delay", "0", "there"],
    ]
    assert inj.last_typed == "hello there"


def test_commit_shorten_only_backspaces() -> None:
    runner = FakeRunner()
    inj = Injector(runner=runner)
    inj.commit("hello world")
    runner.calls.clear()
    inj.commit("hello")
    assert runner.calls == [
        ["xdotool", "key", "--clearmodifiers", "--delay", "0", "--repeat", "6", "BackSpace"],
    ]
    assert inj.last_typed == "hello"


def test_commit_noop_when_identical() -> None:
    runner = FakeRunner()
    inj = Injector(runner=runner)
    inj.commit("hello")
    runner.calls.clear()
    inj.commit("hello")
    assert runner.calls == []


def test_reset_clears_last_typed() -> None:
    runner = FakeRunner()
    inj = Injector(runner=runner)
    inj.commit("hello")
    inj.reset()
    assert inj.last_typed == ""
    runner.calls.clear()
    inj.commit("world")
    assert runner.calls == [
        ["xdotool", "type", "--clearmodifiers", "--delay", "0", "world"],
    ]
