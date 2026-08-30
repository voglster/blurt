import pytest

from blurt import overlay

# A real 3-monitor XWayland layout: DP-4 (primary) centre, DP-9 right, HDMI-1 left.
DETAILED = [
    overlay.MonitorInfo("DP-4", True, 2560, 0, 2560, 1440),
    overlay.MonitorInfo("DP-9", False, 5120, 0, 2560, 1440),
    overlay.MonitorInfo("HDMI-1", False, 0, 0, 2560, 1440),
]
CENTER, RIGHT, LEFT = (m[2:] for m in DETAILED)
MONS = [CENTER, RIGHT, LEFT]

XRANDR_OUTPUT = """Monitors: 3
 0: +*DP-4 2560/700x1440/390+2560+0  DP-4
 1: +DP-9 2560/600x1440/340+5120+0  DP-9
 2: +HDMI-1 2560/600x1440/340+0+0  HDMI-1
"""


@pytest.fixture(autouse=True)
def _off_hyprland_by_default(monkeypatch):
    """Keep the X11 path the default for every test in this module.

    Otherwise these tests read XDG_CURRENT_DESKTOP from whoever is running them
    and shell out to a real hyprctl — passing on a Hyprland box and taking a
    different path in CI. Hyprland tests opt in through `_patch_hyprland`.
    """
    monkeypatch.setattr(overlay, "is_hyprland", lambda: False)


def _patch_monitors(monkeypatch, monitors=DETAILED):
    monkeypatch.setattr(overlay, "_list_monitors_detailed", lambda: monitors)
    monkeypatch.setattr(overlay, "_list_monitors", lambda: [m[2:] for m in monitors])


def test_parse_monitors_extracts_names_and_primary_flag():
    mons = overlay._parse_listmonitors(XRANDR_OUTPUT)
    assert [m.name for m in mons] == ["DP-4", "DP-9", "HDMI-1"]
    assert [m.primary for m in mons] == [True, False, False]
    assert mons[0][2:] == CENTER


def test_parse_monitors_ignores_the_header_line():
    assert overlay._parse_listmonitors("Monitors: 0\n") == []


def test_list_monitors_stays_rect_only(monkeypatch):
    monkeypatch.setattr(
        overlay, "_list_monitors_detailed",
        lambda: overlay._parse_listmonitors(XRANDR_OUTPUT),
    )
    assert overlay._list_monitors() == [CENTER, RIGHT, LEFT]


def test_monitor_containing_picks_rect_with_point():
    assert overlay._monitor_containing(MONS, 3819, 670) == CENTER
    assert overlay._monitor_containing(MONS, 100, 700) == LEFT
    assert overlay._monitor_containing(MONS, 6000, 700) == RIGHT


def test_monitor_containing_returns_none_when_outside():
    assert overlay._monitor_containing(MONS, 99999, 0) is None


def test_resolve_monitor_primary_ignores_stale_pointer(monkeypatch):
    _patch_monitors(monkeypatch)
    monkeypatch.setattr(overlay, "_pointer_xy", lambda: (6000, 700))
    assert overlay._resolve_monitor(None, preference="primary") == CENTER


def test_resolve_monitor_by_output_name(monkeypatch):
    _patch_monitors(monkeypatch)
    monkeypatch.setattr(overlay, "_pointer_xy", lambda: (6000, 700))
    assert overlay._resolve_monitor(None, preference="HDMI-1") == LEFT


def test_resolve_monitor_unknown_name_falls_back_to_primary(monkeypatch):
    _patch_monitors(monkeypatch)
    monkeypatch.setattr(overlay, "_pointer_xy", lambda: None)
    assert overlay._resolve_monitor(None, preference="DP-99") == CENTER


def test_resolve_monitor_primary_falls_back_to_first_when_none_marked(monkeypatch):
    _patch_monitors(monkeypatch, [overlay.MonitorInfo("DP-9", False, 5120, 0, 2560, 1440)])
    assert overlay._resolve_monitor(None, preference="primary") == RIGHT


def test_resolve_monitor_pointer_uses_pointer_when_no_window(monkeypatch):
    _patch_monitors(monkeypatch)
    monkeypatch.setattr(overlay, "_pointer_xy", lambda: (6000, 700))
    assert overlay._resolve_monitor(None, preference="pointer") == RIGHT


def test_resolve_monitor_pointer_prefers_window_over_pointer(monkeypatch):
    _patch_monitors(monkeypatch)
    monkeypatch.setattr(overlay, "_window_rect", lambda wid: (100, 100, 800, 600))
    monkeypatch.setattr(overlay, "_pointer_xy", lambda: (6000, 700))
    assert overlay._resolve_monitor(123, preference="pointer") == LEFT


def test_resolve_monitor_pointer_falls_back_when_window_rect_missing(monkeypatch):
    _patch_monitors(monkeypatch)
    monkeypatch.setattr(overlay, "_window_rect", lambda wid: None)
    monkeypatch.setattr(overlay, "_pointer_xy", lambda: (6000, 700))
    assert overlay._resolve_monitor(123, preference="pointer") == RIGHT


def test_resolve_monitor_pointer_falls_back_to_first_when_no_signal(monkeypatch):
    _patch_monitors(monkeypatch)
    monkeypatch.setattr(overlay, "_pointer_xy", lambda: None)
    assert overlay._resolve_monitor(None, preference="pointer") == CENTER


def test_resolve_monitor_none_when_no_monitors(monkeypatch):
    _patch_monitors(monkeypatch, [])
    assert overlay._resolve_monitor(None) is None


# --- Hyprland ---
#
# The overlay is an X11 window, so its geometry must come from xrandr even on
# Hyprland. These fixtures deliberately disagree: Hyprland reports a 2880x1920
# panel at scale 2 as the 1440x960 box it lays windows out in, while XWayland
# (with xwayland:force_zero_scaling) reports the full 2880x1920 that an X11
# window is actually positioned in. Anything that returns 1440x960 to the
# overlay is a bug.
HIDPI_XRANDR = """Monitors: 2
 0: +eDP-1 2880/290x1920/190+0+0  eDP-1
 1: +DP-3 3840/600x2160/340+2880+0  DP-3
"""
HIDPI_HYPRCTL = """[
  {"name": "eDP-1", "width": 2880, "height": 1920, "x": 0, "y": 0,
   "scale": 2.0, "transform": 0, "focused": false},
  {"name": "DP-3", "width": 3840, "height": 2160, "x": 1440, "y": 0,
   "scale": 1.0, "transform": 0, "focused": true}
]"""
PANEL_X = (0, 0, 2880, 1920)      # eDP-1 as X sees it
DOCK_X = (2880, 0, 3840, 2160)    # DP-3 as X sees it


def _patch_hyprland(monkeypatch, hyprctl=HIDPI_HYPRCTL, cursor=None, xrandr=HIDPI_XRANDR):
    monkeypatch.setattr(overlay, "is_hyprland", lambda: True)
    monkeypatch.setattr(
        overlay, "_list_monitors_detailed",
        lambda: overlay._parse_listmonitors(xrandr),
    )

    def fake_hyprctl(*args):
        if args[0] == "monitors":
            return hyprctl
        if args[0] == "cursorpos":
            return cursor
        raise AssertionError(f"unexpected hyprctl {args}")

    monkeypatch.setattr(overlay, "_hyprctl", fake_hyprctl)


def test_parse_hyprctl_reports_logical_geometry():
    mons = overlay._parse_hyprctl_monitors(HIDPI_HYPRCTL)
    assert [m.name for m in mons] == ["eDP-1", "DP-3"]
    # 2880x1920 at scale 2 is a 1440x960 box in the space hyprctl answers in.
    assert mons[0][2:] == (0, 0, 1440, 960)
    assert mons[1][2:] == (1440, 0, 3840, 2160)
    assert [m.focused for m in mons] == [False, True]


def test_parse_hyprctl_swaps_axes_on_quarter_turn_transforms():
    for transform in (1, 3, 5, 7):
        payload = ('[{"name": "DP-1", "width": 2560, "height": 1440, "x": 0, "y": 0,'
                   f' "scale": 1.0, "transform": {transform}, "focused": true}}]')
        assert overlay._parse_hyprctl_monitors(payload)[0][2:] == (0, 0, 1440, 2560)


def test_parse_hyprctl_leaves_half_turn_transforms_alone():
    for transform in (0, 2, 4, 6):
        payload = ('[{"name": "DP-1", "width": 2560, "height": 1440, "x": 0, "y": 0,'
                   f' "scale": 1.0, "transform": {transform}, "focused": true}}]')
        assert overlay._parse_hyprctl_monitors(payload)[0][2:] == (0, 0, 2560, 1440)


def test_parse_hyprctl_survives_a_missing_or_zero_scale():
    payload = ('[{"name": "DP-1", "width": 2560, "height": 1440, "x": 0, "y": 0,'
               ' "focused": true}]')
    assert overlay._parse_hyprctl_monitors(payload)[0][2:] == (0, 0, 2560, 1440)


def test_list_monitors_hyprland_returns_empty_on_bad_json(monkeypatch):
    monkeypatch.setattr(overlay, "_hyprctl", lambda *a: "not json")
    assert overlay._list_monitors_hyprland() == []


def test_hyprland_names_the_focused_monitor(monkeypatch):
    _patch_hyprland(monkeypatch)
    assert overlay._hyprland_monitor_name("primary") == "DP-3"


def test_hyprland_names_the_monitor_under_the_cursor(monkeypatch):
    # 1077,493 is on the laptop panel in *logical* coordinates; in X coordinates
    # it would be on the panel too, but only because this fixture is at the
    # origin — the containment test has to happen in Hyprland's own space.
    _patch_hyprland(monkeypatch, cursor='{"x": 1077, "y": 493}')
    assert overlay._hyprland_monitor_name("pointer") == "eDP-1"


def test_hyprland_pointer_falls_back_to_focused_when_cursor_is_unknown(monkeypatch):
    _patch_hyprland(monkeypatch, cursor=None)
    assert overlay._hyprland_monitor_name("pointer") == "DP-3"


def test_hyprland_names_nothing_when_hyprctl_is_silent(monkeypatch):
    _patch_hyprland(monkeypatch, hyprctl=None)
    assert overlay._hyprland_monitor_name("primary") is None


def test_resolve_takes_the_name_from_hyprctl_and_the_rect_from_xrandr(monkeypatch):
    # The regression guard: DP-3 is 3840x2160 to both, but eDP-1 is where the
    # two disagree, so a "primary" that resolves through hyprctl geometry would
    # hand back 1440x960 instead of 2880x1920.
    _patch_hyprland(monkeypatch, cursor='{"x": 1077, "y": 493}')
    assert overlay._resolve_monitor(None, preference="pointer") == PANEL_X
    assert overlay._resolve_monitor(None, preference="primary") == DOCK_X
    assert overlay._resolve_monitor(None, preference="focused") == DOCK_X


def test_resolve_prefers_hyprctl_over_the_missing_xrandr_primary(monkeypatch):
    # XWayland marks no output primary, so without hyprctl this would silently
    # fall through to "the first monitor xrandr listed".
    _patch_hyprland(monkeypatch)
    assert not any(m.primary for m in overlay._parse_listmonitors(HIDPI_XRANDR))
    assert overlay._resolve_monitor(None, preference="primary") == DOCK_X


def test_resolve_by_output_name_does_not_consult_hyprctl(monkeypatch):
    _patch_hyprland(monkeypatch)
    monkeypatch.setattr(
        overlay, "_hyprland_monitor_name", lambda p: pytest.fail("consulted hyprctl")
    )
    assert overlay._resolve_monitor(None, preference="eDP-1") == PANEL_X


def test_resolve_ignores_a_hyprctl_monitor_xrandr_does_not_know(monkeypatch):
    # An output Hyprland has but XWayland has not picked up yet: fall back
    # rather than return a rect for the wrong screen.
    _patch_hyprland(monkeypatch)
    monkeypatch.setattr(overlay, "_hyprland_monitor_name", lambda p: "DP-99")
    assert overlay._resolve_monitor(None, preference="primary") == PANEL_X


def test_resolve_off_hyprland_keeps_the_xrandr_only_path(monkeypatch):
    _patch_monitors(monkeypatch)
    monkeypatch.setattr(overlay, "is_hyprland", lambda: False)
    monkeypatch.setattr(
        overlay, "_hyprland_monitor_name", lambda p: pytest.fail("consulted hyprctl")
    )
    monkeypatch.setattr(overlay, "_pointer_xy", lambda: (6000, 700))
    assert overlay._resolve_monitor(None, preference="primary") == CENTER
    assert overlay._resolve_monitor(None, preference="pointer") == RIGHT


def test_focused_is_accepted_as_a_synonym_for_primary(monkeypatch):
    _patch_monitors(monkeypatch)
    monkeypatch.setattr(overlay, "is_hyprland", lambda: False)
    monkeypatch.setattr(overlay, "_pointer_xy", lambda: (6000, 700))
    assert overlay._resolve_monitor(None, preference="focused") == CENTER


def test_hyprctl_env_left_alone_when_signature_is_already_set(monkeypatch):
    monkeypatch.setenv("HYPRLAND_INSTANCE_SIGNATURE", "sig_1")
    assert overlay._hyprctl_env() is None


def test_hyprctl_env_recovers_a_lone_instance_signature(monkeypatch, tmp_path):
    monkeypatch.delenv("HYPRLAND_INSTANCE_SIGNATURE", raising=False)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    (tmp_path / "hypr" / "sig_1").mkdir(parents=True)
    env = overlay._hyprctl_env()
    assert env is not None and env["HYPRLAND_INSTANCE_SIGNATURE"] == "sig_1"


def test_hyprctl_env_refuses_to_guess_between_instances(monkeypatch, tmp_path):
    monkeypatch.delenv("HYPRLAND_INSTANCE_SIGNATURE", raising=False)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    (tmp_path / "hypr" / "sig_1").mkdir(parents=True)
    (tmp_path / "hypr" / "sig_2").mkdir(parents=True)
    assert overlay._hyprctl_env() is None
