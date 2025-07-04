#!/usr/bin/env python3
"""Main entry point for blurt."""

import os
import sys
from typing import NoReturn

from .config import Config
from .hotkey_handler import HotkeyHandler
from .speech_recognizer import SpeechRecognizer
from .text_output import TextOutput


class Blurt:
    """Main application class."""

    def __init__(self) -> None:
        self.config = Config()
        self.text_output = TextOutput(self.config)
        self.speech_recognizer = SpeechRecognizer(self.config)
        self.hotkey_handler = HotkeyHandler(self.config, self._on_voice_text)

    def _on_voice_text(self, audio_data: bytes) -> None:
        """Handle voice text recognition."""
        text = self.speech_recognizer.recognize(audio_data)
        if text.strip():
            self.text_output.type_text(text)

    def run(self) -> NoReturn:
        """Run the application."""
        print("Blurt starting... (Press Ctrl+C to exit)")

        try:
            self.hotkey_handler.start()
        except KeyboardInterrupt:
            print("\nShutting down...")
            sys.exit(0)
        # This should never be reached, but satisfy mypy
        raise RuntimeError("Unexpected exit from infinite loop")


def main() -> None:
    """Main entry point."""
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print("Blurt - Voice-to-text using Ctrl+Space trigger")
        print("Usage: uv run python -m blurt.main")
        print("Hold Ctrl+Space for push-to-talk voice recording")
        print("Uses X11 directly, no sudo needed")
        sys.exit(0)

    # Check if we have X11 display
    if not os.environ.get("DISPLAY"):
        print("Error: No X11 display found")
        print("This app requires X11 (not Wayland)")
        sys.exit(1)

    app = Blurt()
    app.run()


def main_daemon() -> None:
    """Daemon entry point - runs without console output."""
    import logging

    # Check if we have X11 display
    if not os.environ.get("DISPLAY"):
        logging.error("No X11 display found - daemon cannot run")
        sys.exit(1)

    try:
        app = Blurt()
        logging.info("Starting Blurt application")
        app.run()
    except Exception as e:
        logging.error(f"Application error: {e}")
        raise


if __name__ == "__main__":
    main()
