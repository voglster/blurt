"""Simple synchronous audio recording."""

import io
import threading
import wave

import numpy as np
from pvrecorder import PvRecorder

from .config import Config


class SimpleAudioRecorder:
    """Simple synchronous audio recorder."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.recording: list[int] = []
        self.is_recording = False
        self.recorder: PvRecorder | None = None
        self.record_thread: threading.Thread | None = None

    def start_recording(self) -> None:
        """Start audio recording."""
        try:
            self.recording = []
            self.is_recording = True

            # Create PvRecorder instance
            self.recorder = PvRecorder(
                device_index=-1,  # Use default device
                frame_length=512,  # Frame length in samples
            )

            # Start recording in a separate thread
            self.record_thread = threading.Thread(target=self._record_audio, daemon=True)
            self.record_thread.start()

            print("✅ Audio recording started")

        except Exception as e:
            print(f"❌ Error starting recording: {e}")
            # List available devices for debugging
            try:
                devices = PvRecorder.get_audio_devices()
                print("Available audio devices:")
                for i, device in enumerate(devices):
                    print(f"  [{i}] {device}")
            except Exception:
                pass

    def _record_audio(self) -> None:
        """Record audio in a separate thread."""
        try:
            if self.recorder is not None:
                self.recorder.start()

                while self.is_recording:
                    # Read audio frame
                    frame = self.recorder.read()
                    self.recording.extend(frame)

        except Exception as e:
            print(f"Error during recording: {e}")
        finally:
            if self.recorder:
                self.recorder.stop()

    def stop_recording(self) -> bytes:
        """Stop recording and return audio data as bytes."""
        self.is_recording = False

        # Wait for recording thread to finish
        if self.record_thread:
            self.record_thread.join(timeout=1.0)

        # Clean up recorder
        if self.recorder:
            self.recorder.delete()
            self.recorder = None

        if not self.recording:
            print("⚠️ No audio data recorded")
            return b""

        print(f"✅ Recorded {len(self.recording)} audio samples")

        # Convert to numpy array and create WAV file
        try:
            audio_data = np.array(self.recording, dtype=np.int16)

            # Create WAV file in memory
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, "wb") as wav_file:
                wav_file.setnchannels(self.config.channels)
                wav_file.setsampwidth(2)  # 2 bytes for 16-bit
                wav_file.setframerate(self.config.sample_rate)
                wav_file.writeframes(audio_data.tobytes())

            return wav_buffer.getvalue()
        except Exception as e:
            print(f"❌ Error creating WAV file: {e}")
            return b""
