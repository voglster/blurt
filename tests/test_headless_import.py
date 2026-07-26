import os
import subprocess
import sys

import pytest

HEADLESS_ENV = {
    k: v for k, v in os.environ.items() if k not in ("DISPLAY", "WAYLAND_DISPLAY")
}


def _import_headless(module: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        env=HEADLESS_ENV,
        capture_output=True,
        text=True,
    )


WITHOUT_TKINTER = """
import sys
sys.modules["tkinter"] = None
try:
    import tkinter
except ImportError:
    pass
else:
    raise AssertionError("test bug: tkinter is still importable, so this proves nothing")
import blurt.overlay
import blurt.daemon
"""


def test_imports_without_tkinter() -> None:
    """Tk ships as a separate OS package (python3-tk on Debian/Ubuntu).

    Importing blurt must not require it — only constructing an overlay does.
    Otherwise blurt is uninstallable-in-practice anywhere Tk is absent, which is
    how CI first broke.
    """
    result = subprocess.run(
        [sys.executable, "-c", WITHOUT_TKINTER],
        env=HEADLESS_ENV,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("module", ["blurt.tray", "blurt.daemon", "blurt.cli"])
def test_imports_without_a_display(module: str) -> None:
    """pystray opens the X display when it is imported, not when a tray is built.

    A module-scope import therefore makes `import blurt.daemon` fail on any
    headless machine — CI, a server, or a user running with tray disabled.
    """
    result = _import_headless(module)

    assert result.returncode == 0, result.stderr
