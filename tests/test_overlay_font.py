from blurt.overlay import unresolved_font_warning


def test_no_warning_when_font_resolves_to_a_real_family():
    assert unresolved_font_warning("monospace 18", "DejaVu Sans Mono") is None


def test_no_warning_for_an_explicitly_configured_bitmap_lookalike():
    assert unresolved_font_warning("Courier 18", "Courier") is None


def test_warns_when_tk_falls_back_to_the_x11_last_resort_bitmap():
    warning = unresolved_font_warning("monospace 18", "fixed")
    assert warning is not None
    assert "monospace 18" in warning
    assert "python3-tk" in warning


def test_fallback_detection_ignores_case_and_padding():
    assert unresolved_font_warning("monospace 18", " Fixed ") is not None
