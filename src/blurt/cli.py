#!/usr/bin/env python3
"""Command-line interface for Blurt."""

import atexit
import logging
import os
import signal
import sys
from pathlib import Path


class BlurtCLI:
    """CLI handler for Blurt voice transcription."""

    def __init__(self) -> None:
        self.config_dir = Path.home() / ".config" / "blurt"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # PID file goes in runtime directory (XDG spec)
        runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
        if runtime_dir:
            self.pid_file = Path(runtime_dir) / "blurt.pid"
        else:
            # Fallback to /tmp if XDG_RUNTIME_DIR not available
            self.pid_file = Path("/tmp") / f"blurt-{os.getuid()}.pid"  # nosec B108

        # Log file stays in config directory
        self.log_file = self.config_dir / "blurt.log"

    def start(self) -> None:
        """Start the Blurt daemon."""
        if self._is_running():
            print("Blurt is already running.")
            print(f"PID: {self._get_pid()}")
            return

        print("Starting Blurt daemon...")

        # Fork process to create daemon
        try:
            pid = os.fork()
            if pid > 0:
                # Parent process - save PID and exit
                self._write_pid(pid)
                print(f"Blurt daemon started (PID: {pid})")
                print(f"Logs: {self.log_file}")
                return
        except OSError as e:
            print(f"Fork failed: {e}")
            return

        # Child process - become daemon
        self._daemonize()

        # Set up logging for daemon
        self._setup_logging()

        # Register cleanup on exit
        atexit.register(self._cleanup_on_exit)

        # Start the main application
        try:
            from .main import main_daemon

            main_daemon()
        except Exception as e:
            logging.error(f"Daemon failed: {e}")
            sys.exit(1)

    def stop(self) -> None:
        """Stop the Blurt daemon."""
        pid = self._get_pid()
        if not pid:
            print("Blurt is not running.")
            return

        print(f"Stopping Blurt (PID: {pid})...")
        try:
            os.kill(pid, signal.SIGTERM)
            self.pid_file.unlink(missing_ok=True)
            print("Blurt stopped.")
        except ProcessLookupError:
            print("Process not found. Cleaning up PID file.")
            self.pid_file.unlink(missing_ok=True)
        except Exception as e:
            print(f"Error stopping Blurt: {e}")

    def restart(self) -> None:
        """Restart the Blurt daemon."""
        print("Restarting Blurt...")
        self.stop()
        self.start()

    def status(self) -> None:
        """Show Blurt daemon status."""
        if self._is_running():
            print(f"Blurt is running (PID: {self._get_pid()})")
        else:
            print("Blurt is not running")

    def install(self) -> None:
        """Install Blurt for autostart."""
        desktop_file = Path.home() / ".config" / "autostart" / "blurt.desktop"
        desktop_file.parent.mkdir(parents=True, exist_ok=True)

        desktop_content = """[Desktop Entry]
Type=Application
Name=Blurt
Comment=Push-to-talk voice transcription
Exec=blurt start
Icon=audio-input-microphone
X-GNOME-Autostart-enabled=true
Hidden=false
NoDisplay=false
"""

        desktop_file.write_text(desktop_content)
        print(f"Autostart file created: {desktop_file}")
        print("Blurt will start automatically on login.")

    def _is_running(self) -> bool:
        """Check if Blurt is running."""
        pid = self._get_pid()
        if not pid:
            return False

        try:
            # Check if process exists
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            # Process doesn't exist, clean up PID file
            self.pid_file.unlink(missing_ok=True)
            return False

    def _get_pid(self) -> int | None:
        """Get PID from PID file."""
        if not self.pid_file.exists():
            return None

        try:
            return int(self.pid_file.read_text().strip())
        except Exception:
            return None

    def _write_pid(self, pid: int) -> None:
        """Write PID to PID file."""
        self.pid_file.write_text(str(pid))

    def _daemonize(self) -> None:
        """Daemonize the current process."""
        # Create new session
        os.setsid()

        # Fork again to prevent acquiring terminal
        try:
            pid = os.fork()
            if pid > 0:
                os._exit(0)
        except OSError:
            os._exit(1)

        # Change working directory and umask
        os.chdir("/")
        os.umask(0)

        # Redirect standard file descriptors to /dev/null
        devnull = os.open(os.devnull, os.O_RDWR)
        os.dup2(devnull, sys.stdin.fileno())
        os.dup2(devnull, sys.stdout.fileno())
        os.dup2(devnull, sys.stderr.fileno())
        os.close(devnull)

    def _setup_logging(self) -> None:
        """Set up logging for daemon mode."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(self.log_file),
                logging.StreamHandler(),  # This will go to /dev/null due to daemonization
            ],
        )

        # Log daemon start
        logging.info("Blurt daemon started")

    def _cleanup_on_exit(self) -> None:
        """Clean up PID file on daemon exit."""
        self.pid_file.unlink(missing_ok=True)
        logging.info("Blurt daemon stopped")


def main() -> None:
    """Main CLI entry point."""

    cli = BlurtCLI()

    if len(sys.argv) < 2:
        print("Usage: blurt [start|stop|restart|status|install]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "start":
        cli.start()
    elif command == "stop":
        cli.stop()
    elif command == "restart":
        cli.restart()
    elif command == "status":
        cli.status()
    elif command == "install":
        cli.install()
    else:
        print(f"Unknown command: {command}")
        print("Usage: blurt [start|stop|restart|status|install]")
        sys.exit(1)


if __name__ == "__main__":
    main()
