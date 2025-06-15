#!/usr/bin/env python3
"""Simple test to validate X11 key detection."""

import time
import datetime
from Xlib import X, XK, display
from Xlib.ext import record
from Xlib.protocol import rq


def test_key_detection():
    """Test basic key detection."""
    log_file = "key_events.log"
    
    def log_and_print(message):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        log_entry = f"[{timestamp}] {message}"
        print(log_entry)
        with open(log_file, "a") as f:
            f.write(log_entry + "\n")
    
    # Clear log file
    with open(log_file, "w") as f:
        f.write(f"Key detection test started at {datetime.datetime.now()}\n")
        f.write("="*50 + "\n")
    
    log_and_print("Testing X11 key detection...")
    log_and_print("First, let's find your Windows key modifier...")
    log_and_print("Press Windows+Z and we'll see what modifier it uses")
    log_and_print("Press Ctrl+C to exit")
    
    try:
        # Connect to X server
        dpy = display.Display()
        root = dpy.screen().root
        
        # Get keycodes
        z_keycode = dpy.keysym_to_keycode(XK.string_to_keysym('z'))
        
        log_and_print(f"Z keycode: {z_keycode}")
        log_and_print(f"Possible modifiers:")
        log_and_print(f"  Mod1Mask (Alt): {X.Mod1Mask}")
        log_and_print(f"  Mod2Mask: {X.Mod2Mask}")  
        log_and_print(f"  Mod3Mask: {X.Mod3Mask}")
        log_and_print(f"  Mod4Mask (usually Super): {X.Mod4Mask}")
        log_and_print(f"  Mod5Mask: {X.Mod5Mask}")
        
        # Try grabbing with all possible modifiers
        modifiers_to_try = [X.Mod1Mask, X.Mod2Mask, X.Mod3Mask, X.Mod4Mask, X.Mod5Mask]
        
        for i, mod in enumerate(modifiers_to_try, 1):
            try:
                root.grab_key(z_keycode, mod, 1, X.GrabModeAsync, X.GrabModeAsync)
                log_and_print(f"✅ Grabbed Z with Mod{i}Mask ({mod})")
            except Exception as e:
                log_and_print(f"❌ Failed to grab Z with Mod{i}Mask ({mod}): {e}")
        
        log_and_print("\nNow press Windows+Z and see what we detect...")
        log_and_print("Also try just pressing Z to see the difference")
        
        while True:
            event = dpy.next_event()
            
            if event.type == X.KeyPress:
                log_and_print(f"KeyPress: detail={event.detail}, state={event.state}")
                if event.detail == z_keycode:
                    modifier_names = []
                    if event.state & X.Mod1Mask: modifier_names.append("Mod1")
                    if event.state & X.Mod2Mask: modifier_names.append("Mod2") 
                    if event.state & X.Mod3Mask: modifier_names.append("Mod3")
                    if event.state & X.Mod4Mask: modifier_names.append("Mod4")
                    if event.state & X.Mod5Mask: modifier_names.append("Mod5")
                    if event.state & X.ControlMask: modifier_names.append("Ctrl")
                    if event.state & X.ShiftMask: modifier_names.append("Shift")
                    
                    mods = "+".join(modifier_names) if modifier_names else "none"
                    log_and_print(f"🎯 Z PRESSED with modifiers: {mods}")
                    
            elif event.type == X.KeyRelease:
                log_and_print(f"KeyRelease: detail={event.detail}, state={event.state}")
                if event.detail == z_keycode:
                    modifier_names = []
                    if event.state & X.Mod1Mask: modifier_names.append("Mod1")
                    if event.state & X.Mod2Mask: modifier_names.append("Mod2")
                    if event.state & X.Mod3Mask: modifier_names.append("Mod3") 
                    if event.state & X.Mod4Mask: modifier_names.append("Mod4")
                    if event.state & X.Mod5Mask: modifier_names.append("Mod5")
                    if event.state & X.ControlMask: modifier_names.append("Ctrl")
                    if event.state & X.ShiftMask: modifier_names.append("Shift")
                    
                    mods = "+".join(modifier_names) if modifier_names else "none"
                    log_and_print(f"🎯 Z RELEASED with modifiers: {mods}")
                    
    except KeyboardInterrupt:
        log_and_print("\nExiting...")
    except Exception as e:
        log_and_print(f"Error: {e}")
        log_and_print("Make sure you're running under X11 (not Wayland)")
    
    log_and_print(f"Test completed. Check key_events.log for full details.")


if __name__ == "__main__":
    test_key_detection()