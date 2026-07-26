from blurt.overlay import _rounded_rect_scanlines


def _covered_pixels(rects):
    return {(x + dx, y + dy) for x, y, w, h in rects for dx in range(w) for dy in range(h)}


def test_zero_radius_is_one_plain_rectangle():
    assert _rounded_rect_scanlines(100, 40, 0) == [(0, 0, 100, 40)]


def test_negative_radius_is_treated_as_square():
    assert _rounded_rect_scanlines(100, 40, -5) == [(0, 0, 100, 40)]


def test_corners_are_cut_away():
    covered = _covered_pixels(_rounded_rect_scanlines(100, 40, 10))

    for corner in [(0, 0), (99, 0), (0, 39), (99, 39)]:
        assert corner not in covered


def test_edge_midpoints_survive():
    covered = _covered_pixels(_rounded_rect_scanlines(100, 40, 10))

    for edge_midpoint in [(50, 0), (50, 39), (0, 20), (99, 20)]:
        assert edge_midpoint in covered


def test_shape_stays_inside_its_bounds():
    rects = _rounded_rect_scanlines(100, 40, 10)

    for x, y, w, h in rects:
        assert x >= 0 and y >= 0
        assert x + w <= 100
        assert y + h <= 40


def test_shape_is_horizontally_symmetric():
    covered = _covered_pixels(_rounded_rect_scanlines(100, 40, 10))

    assert covered == {(99 - x, y) for x, y in covered}


def test_shape_is_vertically_symmetric():
    covered = _covered_pixels(_rounded_rect_scanlines(100, 40, 10))

    assert covered == {(x, 39 - y) for x, y in covered}


def test_radius_is_clamped_to_half_the_shortest_side():
    """A radius larger than the box would otherwise invert the corner insets."""
    huge = _covered_pixels(_rounded_rect_scanlines(40, 20, 500))
    circle_ish = _covered_pixels(_rounded_rect_scanlines(40, 20, 10))

    assert huge == circle_ish


def test_a_bigger_radius_removes_more_of_the_corner():
    small = _covered_pixels(_rounded_rect_scanlines(100, 40, 4))
    large = _covered_pixels(_rounded_rect_scanlines(100, 40, 16))

    assert len(large) < len(small)


def test_middle_band_is_full_width():
    rects = _rounded_rect_scanlines(100, 40, 10)

    assert (0, 10, 100, 20) in rects
