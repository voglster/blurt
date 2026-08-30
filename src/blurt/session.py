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


def is_hyprland() -> bool:
    """True when the session's compositor is Hyprland.

    XDG_CURRENT_DESKTOP is what uwsm exports into the systemd user environment,
    so it is visible to the daemon; HYPRLAND_INSTANCE_SIGNATURE is checked too
    for sessions started without uwsm.
    """
    desktops = os.environ.get("XDG_CURRENT_DESKTOP", "").casefold().split(":")
    if "hyprland" in desktops:
        return True
    return bool(os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"))
