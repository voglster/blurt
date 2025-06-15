"""Simple hotkey handler using pynput."""

import time
import threading
from typing import Callable, Optional
from pynput import keyboard

from .config import Config


class SimpleHotkeyHandler:
    """Simple hotkey handler using pynput."""
    
    def __init__(self, config: Config, on_voice_callback: Callable[[bytes], None]) -> None:
        self.config = config
        self.on_voice_callback = on_voice_callback
        self.is_recording = False
        self.recording_started = False
        self.ctrl_pressed = False
        
        # Initialize sound player
        from .sound_player import SoundPlayer
        self.sound_player = SoundPlayer()
        
    def start(self) -> None:
        """Start the hotkey handler."""
        print("🎙️ Tab Voice ready! Ctrl+Space to start, release Ctrl to stop")
        print("1. Press Ctrl+Space to start recording")
        print("2. Release Space (keep holding Ctrl)")  
        print("3. Release Ctrl to stop and transcribe")
        
        # Set up keyboard listener for individual key events
        listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release
        )
        
        listener.start()
        
        # Keep running
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n👋 Tab Voice stopped")
            listener.stop()
    
    def _on_key_press(self, key) -> None:
        """Handle individual key press events."""
        try:
            # Track Ctrl key state
            if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
                self.ctrl_pressed = True
                
            # Check for Ctrl+Space combination to start recording
            if key == keyboard.Key.space and self.ctrl_pressed and not self.is_recording:
                print("🎯 Ctrl+Space detected! Starting recording...")
                self.sound_player.play_start()  # Play start sound
                self.is_recording = True
                self.recording_started = True
                threading.Thread(target=self._start_recording, daemon=True).start()
                
        except AttributeError:
            # Handle regular character keys if needed
            pass
    
    def _on_key_release(self, key) -> None:
        """Handle individual key release events."""
        try:
            # When Ctrl is released and we're recording, stop recording
            if (key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r) and self.is_recording:
                print("🎯 Ctrl released! Stopping recording...")
                self.sound_player.play_stop()  # Play stop sound
                self.is_recording = False
                self.recording_started = False
                self.ctrl_pressed = False
                threading.Thread(target=self._stop_recording, daemon=True).start()
            
            # Update Ctrl state when released
            if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
                self.ctrl_pressed = False
                
        except AttributeError:
            # Handle regular character keys if needed  
            pass
    
    def _start_recording(self) -> None:
        """Start audio recording."""
        try:
            from .simple_audio import SimpleAudioRecorder
            self.audio_recorder = SimpleAudioRecorder(self.config)
            self.audio_recorder.start_recording()
        except Exception as e:
            print(f"Error starting recording: {e}")
    
    def _stop_recording(self) -> None:
        """Stop recording and process audio."""
        try:
            if hasattr(self, 'audio_recorder'):
                # Add post-release buffer
                time.sleep(self.config.post_release_ms / 1000)
                
                audio_data = self.audio_recorder.stop_recording()
                
                if audio_data:
                    print("🔄 Processing speech...")
                    
                    # Process with speech recognition
                    from .speech_recognizer import SpeechRecognizer
                    recognizer = SpeechRecognizer(self.config)
                    text = recognizer.recognize(audio_data)
                    
                    if text.strip():
                        print(f"📝 Transcribed: '{text}'")
                        
                        # Type the text
                        from .text_output import TextOutput
                        text_output = TextOutput(self.config)
                        text_output.type_text(text)
                    else:
                        print("❌ No speech detected")
                else:
                    print("❌ No audio data to process")
            else:
                print("❌ No audio recorder found")
        except Exception as e:
            print(f"Error stopping recording: {e}")
            import traceback
            traceback.print_exc()