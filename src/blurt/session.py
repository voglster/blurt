from __future__ import annotations

import os


def is_wayland() -> bool:
    """True when running under a Wayland session.

    Checks XDG_SESSION_TYPE first (authoritative when logind sets it), then
    falls back to the presence of WAYLAND_DISPLAY. Note that Tk/xdotool/xclip
    talk to X(Wayland) and behave very differently here, so callers use this to
    pick evdev/uinput-based input injection instead.
    """
    if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland":
        return True
    return bool(os.environ.get("WAYLAND_DISPLAY"))
