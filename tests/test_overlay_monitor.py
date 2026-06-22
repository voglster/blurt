from blurt import overlay

# center, right, left — matching a real 3-monitor XWayland layout
MONS = [(2560, 0, 2560, 1440), (5120, 0, 2560, 1440), (0, 0, 2560, 1440)]
CENTER, RIGHT, LEFT = MONS


def test_monitor_containing_picks_rect_with_point():
    assert overlay._monitor_containing(MONS, 3819, 670) == CENTER
    assert overlay._monitor_containing(MONS, 100, 700) == LEFT
    assert overlay._monitor_containing(MONS, 6000, 700) == RIGHT


def test_monitor_containing_returns_none_when_outside():
    assert overlay._monitor_containing(MONS, 99999, 0) is None


def test_resolve_monitor_uses_pointer_when_no_window(monkeypatch):
    monkeypatch.setattr(overlay, "_list_monitors", lambda: MONS)
    monkeypatch.setattr(overlay, "_pointer_xy", lambda: (6000, 700))
    assert overlay._resolve_monitor(None) == RIGHT


def test_resolve_monitor_prefers_window_over_pointer(monkeypatch):
    monkeypatch.setattr(overlay, "_list_monitors", lambda: MONS)
    monkeypatch.setattr(overlay, "_window_rect", lambda wid: (100, 100, 800, 600))
    monkeypatch.setattr(overlay, "_pointer_xy", lambda: (6000, 700))
    assert overlay._resolve_monitor(123) == LEFT


def test_resolve_monitor_falls_back_to_pointer_when_window_rect_missing(monkeypatch):
    monkeypatch.setattr(overlay, "_list_monitors", lambda: MONS)
    monkeypatch.setattr(overlay, "_window_rect", lambda wid: None)
    monkeypatch.setattr(overlay, "_pointer_xy", lambda: (6000, 700))
    assert overlay._resolve_monitor(123) == RIGHT


def test_resolve_monitor_falls_back_to_first_when_no_signal(monkeypatch):
    monkeypatch.setattr(overlay, "_list_monitors", lambda: MONS)
    monkeypatch.setattr(overlay, "_pointer_xy", lambda: None)
    assert overlay._resolve_monitor(None) == MONS[0]


def test_resolve_monitor_none_when_no_monitors(monkeypatch):
    monkeypatch.setattr(overlay, "_list_monitors", lambda: [])
    assert overlay._resolve_monitor(None) is None
