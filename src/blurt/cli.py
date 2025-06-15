#!/usr/bin/env python3
"""Command-line interface for Blurt."""

import os
import sys
import signal
import subprocess
from pathlib import Path
from typing import Optional


class BlurtCLI:
    """CLI handler for Blurt voice transcription."""
    
    def __init__(self) -> None:
        self.pid_file = Path.home() / '.config' / 'blurt' / 'blurt.pid'
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
        
    def start(self) -> None:
        """Start the Blurt daemon."""
        if self._is_running():
            print("Blurt is already running.")
            print(f"PID: {self._get_pid()}")
            return
            
        print("Starting Blurt...")
        
        # TODO: Replace with proper daemon mode
        # For now, just run in foreground
        from .main import main
        main()
        
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
        desktop_file = Path.home() / '.config' / 'autostart' / 'blurt.desktop'
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
            
    def _get_pid(self) -> Optional[int]:
        """Get PID from PID file."""
        if not self.pid_file.exists():
            return None
            
        try:
            return int(self.pid_file.read_text().strip())
        except Exception:
            return None
            
    def _write_pid(self) -> None:
        """Write current PID to file."""
        self.pid_file.write_text(str(os.getpid()))


def main() -> None:
    """Main CLI entry point."""
    import sys
    
    cli = BlurtCLI()
    
    if len(sys.argv) < 2:
        print("Usage: blurt [start|stop|restart|status|install]")
        sys.exit(1)
        
    command = sys.argv[1]
    
    if command == 'start':
        cli.start()
    elif command == 'stop':
        cli.stop()
    elif command == 'restart':
        cli.restart()
    elif command == 'status':
        cli.status()
    elif command == 'install':
        cli.install()
    else:
        print(f"Unknown command: {command}")
        print("Usage: blurt [start|stop|restart|status|install]")
        sys.exit(1)


if __name__ == '__main__':
    main()