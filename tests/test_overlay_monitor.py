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
