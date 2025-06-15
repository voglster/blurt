"""Tests for CLI daemon functionality."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.blurt.cli import BlurtCLI


@pytest.fixture
def temp_home():
    """Provide temporary home directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        old_home = os.environ.get("HOME")
        old_runtime = os.environ.get("XDG_RUNTIME_DIR")

        os.environ["HOME"] = temp_dir
        os.environ["XDG_RUNTIME_DIR"] = str(Path(temp_dir) / "runtime")

        try:
            yield temp_dir
        finally:
            if old_home:
                os.environ["HOME"] = old_home
            if old_runtime:
                os.environ["XDG_RUNTIME_DIR"] = old_runtime
            elif "XDG_RUNTIME_DIR" in os.environ:
                del os.environ["XDG_RUNTIME_DIR"]


def test_cli_initialization_with_xdg_runtime(temp_home):
    """Test CLI initializes with XDG_RUNTIME_DIR."""
    cli = BlurtCLI()

    assert cli.config_dir == Path(temp_home) / ".config" / "blurt"
    assert cli.pid_file == Path(temp_home) / "runtime" / "blurt.pid"
    assert cli.log_file == Path(temp_home) / ".config" / "blurt" / "blurt.log"
    assert cli.config_dir.exists()


def test_cli_initialization_without_xdg_runtime(temp_home):
    """Test CLI falls back to /tmp when XDG_RUNTIME_DIR not available."""
    if "XDG_RUNTIME_DIR" in os.environ:
        del os.environ["XDG_RUNTIME_DIR"]

    with patch("os.getuid", return_value=1000):
        cli = BlurtCLI()

        assert cli.pid_file == Path("/tmp") / "blurt-1000.pid"


def test_get_pid_no_file(temp_home):
    """Test _get_pid returns None when PID file doesn't exist."""
    cli = BlurtCLI()

    assert cli._get_pid() is None


def test_get_pid_valid_file(temp_home):
    """Test _get_pid returns PID from valid file."""
    cli = BlurtCLI()
    cli.pid_file.parent.mkdir(parents=True, exist_ok=True)
    cli.pid_file.write_text("12345")

    assert cli._get_pid() == 12345


def test_get_pid_invalid_file(temp_home):
    """Test _get_pid returns None for invalid PID file."""
    cli = BlurtCLI()
    cli.pid_file.parent.mkdir(parents=True, exist_ok=True)
    cli.pid_file.write_text("not-a-number")

    assert cli._get_pid() is None


def test_write_pid(temp_home):
    """Test _write_pid creates file with correct PID."""
    cli = BlurtCLI()
    cli.pid_file.parent.mkdir(parents=True, exist_ok=True)

    cli._write_pid(54321)

    assert cli.pid_file.read_text() == "54321"


def test_is_running_no_pid_file(temp_home):
    """Test _is_running returns False when no PID file exists."""
    cli = BlurtCLI()

    assert cli._is_running() is False


def test_is_running_with_valid_process(temp_home):
    """Test _is_running returns True for valid running process."""
    cli = BlurtCLI()
    cli.pid_file.parent.mkdir(parents=True, exist_ok=True)
    cli.pid_file.write_text("1")  # init process should always exist

    with patch("os.kill") as mock_kill:
        mock_kill.return_value = None  # No exception = process exists

        assert cli._is_running() is True
        mock_kill.assert_called_once_with(1, 0)


def test_is_running_with_dead_process(temp_home):
    """Test _is_running cleans up PID file for dead process."""
    cli = BlurtCLI()
    cli.pid_file.parent.mkdir(parents=True, exist_ok=True)
    cli.pid_file.write_text("99999")  # Unlikely to exist

    with patch("os.kill", side_effect=ProcessLookupError):
        assert cli._is_running() is False
        assert not cli.pid_file.exists()


def test_status_not_running(temp_home, capsys):
    """Test status command when daemon is not running."""
    cli = BlurtCLI()

    cli.status()

    captured = capsys.readouterr()
    assert "Blurt is not running" in captured.out


def test_status_running(temp_home, capsys):
    """Test status command when daemon is running."""
    cli = BlurtCLI()
    cli.pid_file.parent.mkdir(parents=True, exist_ok=True)
    cli.pid_file.write_text("12345")

    with patch("os.kill"):  # Mock successful process check
        cli.status()

    captured = capsys.readouterr()
    assert "Blurt is running (PID: 12345)" in captured.out


def test_stop_not_running(temp_home, capsys):
    """Test stop command when daemon is not running."""
    cli = BlurtCLI()

    cli.stop()

    captured = capsys.readouterr()
    assert "Blurt is not running" in captured.out


def test_stop_running_success(temp_home, capsys):
    """Test stop command successfully terminates daemon."""
    cli = BlurtCLI()
    cli.pid_file.parent.mkdir(parents=True, exist_ok=True)
    cli.pid_file.write_text("12345")

    with patch("os.kill") as mock_kill:
        cli.stop()

    mock_kill.assert_called_once_with(12345, 15)  # SIGTERM
    assert not cli.pid_file.exists()

    captured = capsys.readouterr()
    assert "Stopping Blurt (PID: 12345)" in captured.out
    assert "Blurt stopped" in captured.out


def test_stop_process_not_found(temp_home, capsys):
    """Test stop command cleans up when process not found."""
    cli = BlurtCLI()
    cli.pid_file.parent.mkdir(parents=True, exist_ok=True)
    cli.pid_file.write_text("99999")

    with patch("os.kill", side_effect=ProcessLookupError):
        cli.stop()

    assert not cli.pid_file.exists()

    captured = capsys.readouterr()
    assert "Process not found. Cleaning up PID file." in captured.out


def test_start_already_running(temp_home, capsys):
    """Test start command when daemon is already running."""
    cli = BlurtCLI()
    cli.pid_file.parent.mkdir(parents=True, exist_ok=True)
    cli.pid_file.write_text("12345")

    with patch("os.kill"):  # Mock process exists
        cli.start()

    captured = capsys.readouterr()
    assert "Blurt is already running" in captured.out
    assert "PID: 12345" in captured.out


def test_start_fork_success(temp_home, capsys):
    """Test start command successfully forks daemon."""
    cli = BlurtCLI()
    cli.pid_file.parent.mkdir(parents=True, exist_ok=True)  # Create runtime dir

    with patch("os.fork", return_value=12345):  # Parent process
        cli.start()

    # Should save PID and exit parent
    assert cli.pid_file.read_text() == "12345"

    captured = capsys.readouterr()
    assert "Blurt daemon started (PID: 12345)" in captured.out


def test_start_fork_failure(temp_home, capsys):
    """Test start command handles fork failure."""
    cli = BlurtCLI()

    with patch("os.fork", side_effect=OSError("Fork failed")):
        cli.start()

    captured = capsys.readouterr()
    assert "Fork failed" in captured.out


def test_restart_calls_stop_then_start(temp_home):
    """Test restart command calls stop then start."""
    cli = BlurtCLI()

    with patch.object(cli, "stop") as mock_stop, patch.object(cli, "start") as mock_start:
        cli.restart()

        mock_stop.assert_called_once()
        mock_start.assert_called_once()


def test_cleanup_on_exit(temp_home):
    """Test _cleanup_on_exit removes PID file."""
    cli = BlurtCLI()
    cli.pid_file.parent.mkdir(parents=True, exist_ok=True)
    cli.pid_file.write_text("12345")

    with patch("logging.info"):
        cli._cleanup_on_exit()

    assert not cli.pid_file.exists()
