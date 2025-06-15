"""Push-to-talk hotkey handler using X11 key monitoring."""

import asyncio
import time
import threading
from typing import Callable, Optional

from Xlib import X, XK, display
from Xlib.ext import record
from Xlib.protocol import rq

from .config import Config


class HotkeyHandler:
    """Handles push-to-talk voice recording using X11 key monitoring."""
    
    def __init__(self, config: Config, on_voice_callback: Callable[[bytes], None]) -> None:
        self.config = config
        self.on_voice_callback = on_voice_callback
        self.is_recording = False
        self.press_time: Optional[float] = None
        self.target_keycode = 65  # Space key
        self.target_modifier = X.ControlMask  # Ctrl modifier
        
    async def start(self) -> None:
        """Start the push-to-talk handler."""
        print("🎙️ Tab Voice ready! Hold Ctrl+Space for push-to-talk")
        print("Hold Ctrl+Space, speak, then release to transcribe")
        
        # Start X11 key monitoring in a separate thread
        monitor_thread = threading.Thread(target=self._monitor_keys, daemon=True)
        monitor_thread.start()
        
        # Keep the main loop running
        try:
            while True:
                await asyncio.sleep(0.1)
        except KeyboardInterrupt:
            print("\n👋 Tab Voice stopped")
    def _monitor_keys(self) -> None:
        """Monitor X11 key events for Super+Z press/release."""
        try:
            # Connect to X server
            dpy = display.Display()
            root = dpy.screen().root
            
            # Set up key grab for Ctrl+Space
            space_keycode = self.target_keycode
            ctrl_modifier = self.target_modifier
            
            # Grab Ctrl+Space
            root.grab_key(space_keycode, ctrl_modifier, 1, X.GrabModeAsync, X.GrabModeAsync)
            
            print(f"✅ Monitoring Ctrl+Space for push-to-talk (keycode: {space_keycode})")
            
            while True:
                event = dpy.next_event()
                
                if event.type == X.KeyPress:
                    print(f"DEBUG: KeyPress detected - keycode: {event.detail}, state: {event.state}")
                    if (event.detail == space_keycode and event.state & ctrl_modifier):
                        print(f"🎯 Ctrl+Space pressed! (keycode: {event.detail})")
                        if not self.is_recording:
                            self.press_time = time.time()
                            asyncio.run_coroutine_threadsafe(
                                self._handle_keypress(), 
                                asyncio.get_event_loop()
                            )
                        else:
                            print("Already recording, ignoring press")
                
                elif event.type == X.KeyRelease:
                    print(f"DEBUG: KeyRelease detected - keycode: {event.detail}, state: {event.state}")
                    if (event.detail == space_keycode and event.state & ctrl_modifier and self.press_time):
                        print(f"🎯 Ctrl+Space released! (keycode: {event.detail})")
                        press_duration = time.time() - self.press_time
                        print(f"Press duration: {press_duration:.3f}s")
                        
                        # Only process if held for minimum time
                        if press_duration >= (self.config.hold_threshold_ms / 1000):
                            print("Duration met, processing...")
                            asyncio.run_coroutine_threadsafe(
                                self._handle_keyrelease(), 
                                asyncio.get_event_loop()
                            )
                        else:
                            print(f"Too short ({press_duration:.3f}s < {self.config.hold_threshold_ms/1000:.3f}s)")
                        
                        self.press_time = None
                    elif event.detail == space_keycode and event.state & ctrl_modifier:
                        print("Ctrl+Space released but no press_time recorded")
                        
        except Exception as e:
            print(f"Error monitoring keys: {e}")
            print("Try running without X11 forwarding or check display permissions")
    
    async def _handle_keypress(self) -> None:
        """Handle keypress - start recording if not already recording."""
        if not self.is_recording:
            # Start recording
            self.is_recording = True
            print("🎤 Recording started... (hold Ctrl+Space)")
            
            from .audio_recorder import AudioRecorder
            self.audio_recorder = AudioRecorder(self.config)
            await self.audio_recorder.start_recording()
    
    async def _handle_keyrelease(self) -> None:
        """Handle key release - stop recording and process."""
        if self.is_recording:
            # Stop recording
            self.is_recording = False
            if hasattr(self, 'audio_recorder'):
                # Add post-release buffer
                await asyncio.sleep(self.config.post_release_ms / 1000)
                
                audio_data = await self.audio_recorder.stop_recording()
                print("🎤 Recording stopped, processing...")
                
                # Process the audio
                self.on_voice_callback(audio_data)