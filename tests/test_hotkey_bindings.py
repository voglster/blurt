import textwrap
from pathlib import Path

from blurt.config import HotkeyConfig, load
from blurt.hotkey import group_bindings


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "config.toml"
    p.write_text(textwrap.dedent(body))
    return p


def test_singular_hotkey_section_yields_one_binding(tmp_path):
    cfg = load(_write(tmp_path, """
        [hotkey]
        keycode = "KEY_CALC"
        device = "/dev/input/event2"
    """))

    assert cfg.hotkeys == (HotkeyConfig(keycode="KEY_CALC", device="/dev/input/event2"),)


def test_missing_config_still_yields_one_default_binding(tmp_path):
    cfg = load(tmp_path / "absent.toml")

    assert cfg.hotkeys == (HotkeyConfig(),)


def test_hotkeys_array_yields_every_binding(tmp_path):
    cfg = load(_write(tmp_path, """
        [[hotkeys]]
        keycode = "KEY_MEDIA"
        device = "/dev/input/event2"

        [[hotkeys]]
        keycode = "KEY_CALC"
        device = "/dev/input/event14"
    """))

    assert cfg.hotkeys == (
        HotkeyConfig(keycode="KEY_MEDIA", device="/dev/input/event2"),
        HotkeyConfig(keycode="KEY_CALC", device="/dev/input/event14"),
    )


def test_hotkeys_array_wins_over_the_singular_section(tmp_path):
    cfg = load(_write(tmp_path, """
        [hotkey]
        keycode = "KEY_CALC"
        device = "auto"

        [[hotkeys]]
        keycode = "KEY_MEDIA"
        device = "/dev/input/event2"
    """))

    assert cfg.hotkeys == (HotkeyConfig(keycode="KEY_MEDIA", device="/dev/input/event2"),)


def test_hotkey_stays_readable_as_the_first_binding(tmp_path):
    """Legacy attribute, so existing callers and configs keep working."""
    cfg = load(_write(tmp_path, """
        [[hotkeys]]
        keycode = "KEY_MEDIA"
        device = "/dev/input/event2"

        [[hotkeys]]
        keycode = "KEY_CALC"
        device = "/dev/input/event14"
    """))

    assert cfg.hotkey.keycode == "KEY_MEDIA"


def test_a_binding_may_omit_the_device(tmp_path):
    cfg = load(_write(tmp_path, """
        [[hotkeys]]
        keycode = "KEY_MEDIA"
    """))

    assert cfg.hotkeys == (HotkeyConfig(keycode="KEY_MEDIA", device="auto"),)


def test_bindings_on_one_device_are_grouped_together():
    """Two keys on the same keyboard must not open it twice."""
    grouped = group_bindings([
        HotkeyConfig(keycode="KEY_MEDIA", device="/dev/input/event2"),
        HotkeyConfig(keycode="KEY_CALC", device="/dev/input/event2"),
    ])

    assert grouped == {"/dev/input/event2": ["KEY_MEDIA", "KEY_CALC"]}


def test_bindings_on_separate_devices_stay_separate():
    grouped = group_bindings([
        HotkeyConfig(keycode="KEY_MEDIA", device="/dev/input/event2"),
        HotkeyConfig(keycode="KEY_CALC", device="/dev/input/event14"),
    ])

    assert grouped == {
        "/dev/input/event2": ["KEY_MEDIA"],
        "/dev/input/event14": ["KEY_CALC"],
    }


def test_duplicate_bindings_collapse():
    grouped = group_bindings([
        HotkeyConfig(keycode="KEY_CALC", device="auto"),
        HotkeyConfig(keycode="KEY_CALC", device="auto"),
    ])

    assert grouped == {"auto": ["KEY_CALC"]}


def test_grouping_preserves_declaration_order():
    grouped = group_bindings([
        HotkeyConfig(keycode="KEY_CALC", device="/dev/input/event14"),
        HotkeyConfig(keycode="KEY_MEDIA", device="/dev/input/event2"),
    ])

    assert list(grouped) == ["/dev/input/event14", "/dev/input/event2"]
