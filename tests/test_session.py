import pytest

from blurt.session import is_hyprland, is_wayland


@pytest.fixture(autouse=True)
def _clear_session_env(monkeypatch):
    monkeypatch.delenv("XDG_SESSION_TYPE", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.delenv("XDG_CURRENT_DESKTOP", raising=False)
    monkeypatch.delenv("HYPRLAND_INSTANCE_SIGNATURE", raising=False)


def test_wayland_via_session_type(monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    assert is_wayland() is True


def test_wayland_via_session_type_is_case_insensitive(monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "Wayland")
    assert is_wayland() is True


def test_wayland_via_wayland_display_when_session_type_unset(monkeypatch):
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    assert is_wayland() is True


def test_x11_session_type_is_not_wayland(monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
    monkeypatch.setenv("WAYLAND_DISPLAY", "")
    assert is_wayland() is False


def test_no_env_defaults_to_not_wayland():
    assert is_wayland() is False


def test_hyprland_via_current_desktop(monkeypatch):
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "Hyprland")
    assert is_hyprland() is True


def test_hyprland_current_desktop_may_be_a_colon_list(monkeypatch):
    # XDG_CURRENT_DESKTOP is specified as a colon-separated preference list, and
    # portals and greeters do prepend to it.
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "wlroots:Hyprland")
    assert is_hyprland() is True


def test_hyprland_via_instance_signature_when_desktop_unset(monkeypatch):
    monkeypatch.setenv("HYPRLAND_INSTANCE_SIGNATURE", "abc_123_456")
    assert is_hyprland() is True


def test_other_compositor_is_not_hyprland(monkeypatch):
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "GNOME")
    assert is_hyprland() is False


def test_no_env_defaults_to_not_hyprland():
    assert is_hyprland() is False
