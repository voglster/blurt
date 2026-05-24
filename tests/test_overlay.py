import multiprocessing
import os

import pytest

# Tk needs a display. Skip the whole module on headless CI.
pytest.importorskip("tkinter")
if not os.environ.get("DISPLAY"):
    pytest.skip("no DISPLAY", allow_module_level=True)


# NOTE: Tk + Python has a known issue where a Tk root created in a non-main
# thread cannot be torn down cleanly from the same process — its registered
# Tcl async handler is bound to the worker thread and triggers
# `Tcl_AsyncDelete: async handler deleted by the wrong thread` (often a hard
# abort) when ANY subsequent test runs Python's shutdown machinery. In
# production, the daemon owns a single Overlay for the lifetime of the
# process, so this never matters. For tests, we isolate by running the
# lifecycle in a forked subprocess.


def _overlay_lifecycle_child() -> None:
    """Runs in a forked subprocess. Exits with code 0 on success."""
    from blurt.overlay import Overlay, OverlayConfig

    ov = Overlay(OverlayConfig())
    ov.start()
    try:
        ov.set_text("buffered before show")  # must not raise
        ov.show()
        ov.set_text("hello")
        ov.set_text("hello world")
        ov.hide()
    finally:
        ov.stop()


def test_overlay_lifecycle_smoke() -> None:
    """Construct, show, set_text, hide, stop — without crashing.

    Also exercises set_text called before show() (must buffer, not raise).
    Runs in a forked subprocess to isolate Tk's threading footprint from the
    rest of the test session.
    """
    ctx = multiprocessing.get_context("fork")
    proc = ctx.Process(target=_overlay_lifecycle_child)
    proc.start()
    proc.join(timeout=10.0)
    assert proc.exitcode == 0, f"child exited with {proc.exitcode}"
