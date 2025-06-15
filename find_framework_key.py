#!/usr/bin/env python3
"""Find the Framework key by detecting unusual keycodes."""

import datetime
from Xlib import X, XK, display
from Xlib.ext import record
from Xlib.protocol import rq


def find_framework_key():
    """Find the Framework key by monitoring all key events."""
    log_file = "framework_key.log"
    
    def log_and_print(message):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        log_entry = f"[{timestamp}] {message}"
        print(log_entry)
        with open(log_file, "a") as f:
            f.write(log_entry + "\n")
    
    # Clear log file
    with open(log_file, "w") as f:
        f.write(f"Framework key detection started at {datetime.datetime.now()}\n")
        f.write("="*60 + "\n")
    
    log_and_print("🔍 Framework Key Detective!")
    log_and_print("This will show ALL key events to find your Framework button")
    log_and_print("")
    log_and_print("Test plan:")
    log_and_print("1. First, press some normal keys (a, b, c) to see typical keycodes")
    log_and_print("2. Then press your Framework button")
    log_and_print("3. Look for unusual keycodes/keysyms")
    log_and_print("")
    log_and_print("Press Ctrl+C to exit when done")
    log_and_print("-" * 50)
    
    # Track known keys to highlight unusual ones
    common_keycodes = set()
    
    try:
        # Connect to displays
        local_dpy = display.Display()
        record_dpy = display.Display()
        
        # Check if record extension is available
        if not record_dpy.has_extension("RECORD"):
            log_and_print("❌ RECORD extension not available")
            return
        
        log_and_print("✅ RECORD extension available")
        
        # Create record context for all key events
        ctx = record_dpy.record_create_context(
            0,
            [record.AllClients],
            [{
                'core_requests': (0, 0),
                'core_replies': (0, 0),
                'ext_requests': (0, 0, 0, 0),
                'ext_replies': (0, 0, 0, 0),
                'delivered_events': (0, 0),
                'device_events': (X.KeyPress, X.KeyRelease),
                'errors': (0, 0),
                'client_started': False,
                'client_died': False,
            }]
        )
        
        def record_callback(reply):
            nonlocal common_keycodes
            
            if reply.category != record.FromServer:
                return
            if reply.client_swapped:
                return
            if not len(reply.data) or reply.data[0] < 2:
                return
            
            data = reply.data
            while len(data):
                event, data = rq.EventField(None).parse_binary_value(data, record_dpy.display, None, None)
                
                if event.type == X.KeyPress:  # Only log press events to reduce noise
                    keycode = event.detail
                    
                    # Try to get keysym and key name
                    try:
                        keysym = local_dpy.keycode_to_keysym(keycode, 0)
                        key_name = XK.keysym_to_string(keysym) if keysym else "unknown"
                    except:
                        keysym = 0
                        key_name = "unknown"
                    
                    # Check if this is unusual
                    is_unusual = (
                        keycode > 200 or  # High keycodes are often special
                        (keysym and keysym > 0xFFFF) or  # Vendor-specific keysyms
                        key_name == "unknown" or
                        keycode not in common_keycodes
                    )
                    
                    if keycode < 200 and keysym and keysym < 0xFFFF:
                        common_keycodes.add(keycode)
                    
                    # Build info string
                    info = f"keycode={keycode:3d}, keysym=0x{keysym:04x}, name='{key_name}'"
                    
                    if is_unusual:
                        log_and_print(f"🚨 UNUSUAL: {info}")
                        if keycode > 200:
                            log_and_print(f"   ⭐ HIGH KEYCODE - this might be your Framework key!")
                        if keysym and keysym > 0xFFFF:
                            log_and_print(f"   ⭐ VENDOR KEYSYM - this might be your Framework key!")
                    else:
                        log_and_print(f"    normal: {info}")
        
        log_and_print("Starting key monitoring...")
        log_and_print("Now press some normal keys (a, b, c) then your Framework button...")
        
        record_dpy.record_enable_context(ctx, record_callback)
        
    except KeyboardInterrupt:
        log_and_print("\nExiting...")
        log_and_print("=" * 50)
        log_and_print("SUMMARY:")
        log_and_print("Look for entries marked with 🚨 UNUSUAL")
        log_and_print("The Framework key likely has:")
        log_and_print("  - High keycode (>200)")
        log_and_print("  - Vendor-specific keysym (>0xFFFF)")
        log_and_print("  - Unknown name")
    except Exception as e:
        log_and_print(f"Error: {e}")
        import traceback
        log_and_print(f"Traceback: {traceback.format_exc()}")
    finally:
        if 'ctx' in locals():
            record_dpy.record_free_context(ctx)
        log_and_print("Check framework_key.log for full details.")


if __name__ == "__main__":
    find_framework_key()