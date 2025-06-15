#!/usr/bin/env python3
"""Check and manage Framework key bindings."""

import subprocess
import sys


def check_framework_bindings():
    """Check what the Framework key is currently bound to."""
    print("🔍 Checking Framework key bindings...")
    
    # Check gsettings for media keys
    try:
        print("\n📋 Checking GNOME media key bindings:")
        result = subprocess.run([
            'gsettings', 'list-recursively', 'org.gnome.settings-daemon.plugins.media-keys'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if any(keyword in line.lower() for keyword in ['video', 'media', 'play', 'totem']):
                    print(f"  📺 {line}")
        else:
            print("  ❌ Could not read media key settings")
    except Exception as e:
        print(f"  ❌ Error checking media keys: {e}")
    
    # Check custom keybindings
    try:
        print("\n📋 Checking custom keybindings:")
        result = subprocess.run([
            'gsettings', 'get', 'org.gnome.settings-daemon.plugins.media-keys', 'custom-keybindings'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            bindings = result.stdout.strip()
            print(f"  Custom bindings: {bindings}")
            
            if bindings != "@as []":
                # Parse and check each binding
                import re
                paths = re.findall(r"'([^']+)'", bindings)
                for path in paths:
                    print(f"\n  Checking binding: {path}")
                    for attr in ['name', 'command', 'binding']:
                        try:
                            result = subprocess.run([
                                'gsettings', 'get', 
                                f'org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:{path}',
                                attr
                            ], capture_output=True, text=True)
                            if result.returncode == 0:
                                print(f"    {attr}: {result.stdout.strip()}")
                        except:
                            pass
        else:
            print("  ❌ Could not read custom keybindings")
    except Exception as e:
        print(f"  ❌ Error checking custom keybindings: {e}")
    
    print("\n🔧 To disable Framework key binding:")
    print("1. Open 'Settings' -> 'Keyboard' -> 'Keyboard Shortcuts'")
    print("2. Look for any binding that mentions video/media")
    print("3. Click on it and press Backspace to disable")
    print("4. Or run the commands shown above to disable via gsettings")


def disable_media_bindings():
    """Attempt to disable common media key bindings."""
    print("🔧 Attempting to disable media key bindings...")
    
    # Common media key settings that might use the Framework key
    media_keys = [
        'video-out',
        'video-out-static',
        'play',
        'pause',
        'stop',
        'previous',
        'next'
    ]
    
    for key in media_keys:
        try:
            # Get current value
            result = subprocess.run([
                'gsettings', 'get', 'org.gnome.settings-daemon.plugins.media-keys', key
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                current = result.stdout.strip()
                print(f"  {key}: {current}")
                
                # If it's not already disabled, offer to disable it
                if current not in ["''", "@as []", "['']"]:
                    response = input(f"    Disable {key}? (y/n): ")
                    if response.lower() == 'y':
                        subprocess.run([
                            'gsettings', 'set', 'org.gnome.settings-daemon.plugins.media-keys', 
                            key, "''"
                        ])
                        print(f"    ✅ Disabled {key}")
        except Exception as e:
            print(f"    ❌ Error with {key}: {e}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == 'disable':
        disable_media_bindings()
    else:
        check_framework_bindings()
        print("\nRun with 'disable' argument to attempt automatic disabling:")
        print("  uv run python check_bindings.py disable")