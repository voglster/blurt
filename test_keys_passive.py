#!/usr/bin/env python3
"""Test to detect ALL key events without grabbing."""

import datetime
from Xlib import X, XK, display
from Xlib.ext import record
from Xlib.protocol import rq


def test_passive_detection():
    """Test passive key detection using record extension."""
    log_file = "key_events_passive.log"
    
    def log_and_print(message):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        log_entry = f"[{timestamp}] {message}"
        print(log_entry)
        with open(log_file, "a") as f:
            f.write(log_entry + "\n")
    
    # Clear log file
    with open(log_file, "w") as f:
        f.write(f"Passive key detection test started at {datetime.datetime.now()}\n")
        f.write("="*60 + "\n")
    
    log_and_print("Testing passive X11 key detection...")
    log_and_print("This will detect ALL key events without interfering")
    log_and_print("Try pressing:")
    log_and_print("  1. Just 'z'")
    log_and_print("  2. Windows+z")
    log_and_print("  3. Framework button")
    log_and_print("  4. Framework+z")
    log_and_print("Press Ctrl+C to exit")
    
    try:
        # Connect to displays
        local_dpy = display.Display()
        record_dpy = display.Display()
        
        # Check if record extension is available
        if not record_dpy.has_extension("RECORD"):
            log_and_print("❌ RECORD extension not available")
            return
        
        log_and_print("✅ RECORD extension available")
        
        # Create record context
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
            if reply.category != record.FromServer:
                return
            if reply.client_swapped:
                return
            if not len(reply.data) or reply.data[0] < 2:
                return
            
            data = reply.data
            while len(data):
                event, data = rq.EventField(None).parse_binary_value(data, record_dpy.display, None, None)
                
                if event.type in (X.KeyPress, X.KeyRelease):
                    event_type = "KeyPress" if event.type == X.KeyPress else "KeyRelease"
                    
                    # Decode modifiers
                    modifier_names = []
                    if event.state & X.ShiftMask: modifier_names.append("Shift")
                    if event.state & X.LockMask: modifier_names.append("Lock")
                    if event.state & X.ControlMask: modifier_names.append("Ctrl")
                    if event.state & X.Mod1Mask: modifier_names.append("Mod1")
                    if event.state & X.Mod2Mask: modifier_names.append("Mod2")
                    if event.state & X.Mod3Mask: modifier_names.append("Mod3")
                    if event.state & X.Mod4Mask: modifier_names.append("Mod4")
                    if event.state & X.Mod5Mask: modifier_names.append("Mod5")
                    
                    mods = "+".join(modifier_names) if modifier_names else "none"
                    
                    # Try to get keysym
                    try:
                        keysym = local_dpy.keycode_to_keysym(event.detail, 0)
                        key_name = XK.keysym_to_string(keysym) if keysym else "unknown"
                    except:
                        key_name = "unknown"
                    
                    log_and_print(f"{event_type}: keycode={event.detail}, state={event.state}, key='{key_name}', modifiers={mods}")
                    
                    # Special highlight for interesting keys
                    if key_name == 'z':
                        log_and_print(f"🎯 Z {event_type.upper()} with modifiers: {mods}")
                    elif keysym and keysym > 0xFFFF:  # Vendor-specific keys
                        log_and_print(f"🔧 SPECIAL KEY {event_type.upper()}: {key_name} (keysym: 0x{keysym:x})")
        
        log_and_print("Starting passive monitoring...")
        record_dpy.record_enable_context(ctx, record_callback)
        
    except KeyboardInterrupt:
        log_and_print("\nExiting...")
    except Exception as e:
        log_and_print(f"Error: {e}")
        import traceback
        log_and_print(f"Traceback: {traceback.format_exc()}")
    finally:
        if 'ctx' in locals():
            record_dpy.record_free_context(ctx)
        log_and_print("Test completed. Check key_events_passive.log for full details.")


if __name__ == "__main__":
    test_passive_detection()