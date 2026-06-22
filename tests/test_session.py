import pytest

from blurt.session import is_wayland


@pytest.fixture(autouse=True)
def _clear_session_env(monkeypatch):
    monkeypatch.delenv("XDG_SESSION_TYPE", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)


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
