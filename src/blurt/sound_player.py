"""Simple sound player using system commands."""

import subprocess  # nosec B404 - needed for audio playback
import threading
from pathlib import Path


class SoundPlayer:
    """Simple sound player using system audio players."""

    def __init__(self) -> None:
        self.sounds_dir = Path(__file__).parent.parent.parent / "sounds"

    def play_start(self) -> None:
        """Play recording start sound."""
        self._play_sound("record_start.wav")

    def play_stop(self) -> None:
        """Play recording stop sound."""
        self._play_sound("record_stop.wav")

    def _play_sound(self, filename: str) -> None:
        """Play a sound file using system player."""
        sound_file = self.sounds_dir / filename

        if not sound_file.exists():
            # print(f"Sound file not found: {sound_file}")
            return

        # Play in background thread so it doesn't block
        def play_async() -> None:
            try:
                # Try different system audio players
                players = ["paplay", "aplay", "play", "ffplay"]

                for player in players:
                    try:
                        # Use subprocess with devnull to suppress output
                        subprocess.run(  # nosec B603 - safe, no user input
                            [player, str(sound_file)],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            timeout=2,
                            check=True,
                        )
                        break  # Success, exit loop
                    except (
                        subprocess.CalledProcessError,
                        FileNotFoundError,
                        subprocess.TimeoutExpired,
                    ):
                        continue  # Try next player

            except Exception:  # nosec B110 - graceful degradation
                # Silently fail if no audio player works
                pass

        threading.Thread(target=play_async, daemon=True).start()
