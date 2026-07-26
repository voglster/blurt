import logging

from blurt.overlay import _EDGE_MARGIN_PX, OverlayConfig, _overlay_geometry

FULL_HD = (0, 0, 1920, 1080)
SECOND_MONITOR = (2560, 0, 2560, 1440)


def _cfg(position: str = "top-center", width_fraction: float = 0.6) -> OverlayConfig:
    return OverlayConfig(position=position, width_fraction=width_fraction)


def test_top_center_sits_one_margin_below_the_top_edge():
    _, _, _, y = _overlay_geometry(FULL_HD, _cfg("top-center"), height=150)

    assert y == _EDGE_MARGIN_PX


def test_bottom_center_sits_one_margin_above_the_bottom_edge():
    _, height, _, y = _overlay_geometry(FULL_HD, _cfg("bottom-center"), height=150)

    assert y + height == 1080 - _EDGE_MARGIN_PX


def test_the_two_positions_mirror_each_other():
    top = _overlay_geometry(FULL_HD, _cfg("top-center"), height=150)[3]
    bottom_y = _overlay_geometry(FULL_HD, _cfg("bottom-center"), height=150)[3]
    gap_below_bottom_box = 1080 - (bottom_y + 150)

    assert top == gap_below_bottom_box


def test_width_is_a_fraction_of_the_monitor_and_the_box_is_centred():
    w, _, x, _ = _overlay_geometry(FULL_HD, _cfg(width_fraction=0.6), height=150)

    assert w == 1152
    assert x == (1920 - 1152) // 2


def test_geometry_is_relative_to_the_monitor_not_the_desktop():
    w, _, x, y = _overlay_geometry(SECOND_MONITOR, _cfg("top-center"), height=150)

    assert w == 1536
    assert x == 2560 + (2560 - 1536) // 2
    assert y == _EDGE_MARGIN_PX


def test_growing_taller_keeps_a_bottom_anchored_box_pinned_to_the_bottom():
    short = _overlay_geometry(FULL_HD, _cfg("bottom-center"), height=150)[3]
    tall = _overlay_geometry(FULL_HD, _cfg("bottom-center"), height=300)[3]

    assert tall == short - 150


def test_growing_taller_leaves_a_top_anchored_box_where_it_is():
    short = _overlay_geometry(FULL_HD, _cfg("top-center"), height=150)[3]
    tall = _overlay_geometry(FULL_HD, _cfg("top-center"), height=300)[3]

    assert tall == short


def test_height_passes_through_unchanged():
    assert _overlay_geometry(FULL_HD, _cfg(), height=222)[1] == 222


def test_center_puts_equal_space_above_and_below():
    _, height, _, y = _overlay_geometry(FULL_HD, _cfg("center"), height=200)
    above = y
    below = 1080 - (y + height)

    assert abs(above - below) <= 1


def test_center_grows_in_both_directions():
    short = _overlay_geometry(FULL_HD, _cfg("center"), height=200)[3]
    tall = _overlay_geometry(FULL_HD, _cfg("center"), height=400)[3]

    assert tall == short - 100


def test_center_is_relative_to_the_monitor():
    _, _, _, y = _overlay_geometry(SECOND_MONITOR, _cfg("center"), height=200)

    assert y == (1440 - 200) // 2


def test_unrecognised_position_falls_back_to_the_default(caplog):
    with caplog.at_level(logging.WARNING):
        fallback = _overlay_geometry(FULL_HD, _cfg("middle-left"), height=150)

    assert fallback == _overlay_geometry(FULL_HD, _cfg("center"), height=150)
    assert "middle-left" in caplog.text


def test_a_recognised_position_warns_about_nothing(caplog):
    with caplog.at_level(logging.WARNING):
        _overlay_geometry(FULL_HD, _cfg("bottom-center"), height=150)

    assert caplog.text == ""
