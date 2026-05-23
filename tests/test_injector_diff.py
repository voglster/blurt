from blurt.injector import diff


def test_empty_to_text() -> None:
    assert diff("", "hello") == (0, "hello")


def test_extend_text() -> None:
    assert diff("hello", "hello world") == (0, " world")


def test_replace_tail() -> None:
    assert diff("hello world", "hello there") == (5, "there")


def test_full_replace() -> None:
    assert diff("hello", "goodbye") == (5, "goodbye")


def test_shorten() -> None:
    assert diff("hello world", "hello") == (6, "")


def test_identical() -> None:
    assert diff("hello", "hello") == (0, "")


def test_empty_to_empty() -> None:
    assert diff("", "") == (0, "")


def test_text_to_empty() -> None:
    assert diff("hello", "") == (5, "")


def test_unicode() -> None:
    # backspace count is in characters, not bytes
    assert diff("café", "cafés") == (0, "s")
    assert diff("cafés", "café") == (1, "")
