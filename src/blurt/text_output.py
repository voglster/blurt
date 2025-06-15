"""Text output using keyboard simulation."""

import time

from pynput.keyboard import Controller

from .config import Config


class TextOutput:
    """Text output handler."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.keyboard = Controller()

    def type_text(self, text: str) -> None:
        """Type the given text."""
        if not text.strip():
            return

        print(f"Typing: {text}")

        # Add a small delay before typing
        time.sleep(0.1)

        # Type character by character with delay
        for char in text:
            self.keyboard.type(char)
            if self.config.typing_delay > 0:
                time.sleep(self.config.typing_delay)
