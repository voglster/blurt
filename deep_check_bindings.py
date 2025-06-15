#!/usr/bin/env python3
"""Deep check for Framework key bindings in all possible places."""

import subprocess
import os


def run_command(cmd):
    """Run a command and return output."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except Exception as e:
        return "", str(e), 1


def check_all_bindings():
    """Check everywhere for the Framework key binding."""
    print("🔍 Deep search for Framework key bindings...")
    print("=" * 60)
    
    # Check dconf directly
    print("\n1. 📋 Checking dconf database:")
    stdout, stderr, code = run_command("dconf dump /org/gnome/settings-daemon/plugins/media-keys/")
    if stdout:
        print("Media keys dconf:")
        print(stdout)
    else:
        print("No media keys in dconf")
    
    # Check for XF86 key bindings
    print("\n2. 🎹 Checking XF86 key mappings:")
    stdout, stderr, code = run_command("xmodmap -pke | grep -i 'video\\|media\\|play'")
    if stdout:
        print("XF86 key mappings:")
        print(stdout)
    else:
        print("No obvious media key mappings")
    
    # Check systemd user services
    print("\n3. 🔧 Checking systemd user services:")
    stdout, stderr, code = run_command("systemctl --user list-units | grep -i 'media\\|key'")
    if stdout:
        print("Media-related services:")
        print(stdout)
    
    # Check for acpi events
    print("\n4. ⚡ Checking ACPI events:")
    if os.path.exists("/etc/acpi/events/"):
        stdout, stderr, code = run_command("ls -la /etc/acpi/events/ | grep -v '^total'")
        if stdout:
            print("ACPI event files:")
            print(stdout)
    
    # Check desktop files that might handle media keys
    print("\n5. 🖥️ Checking desktop applications that handle media:")
    stdout, stderr, code = run_command("find ~/.local/share/applications /usr/share/applications -name '*.desktop' -exec grep -l 'MimeType.*video\\|audio' {} \\; 2>/dev/null | head -5")
    if stdout:
        print("Applications that handle media:")
        for app in stdout.split('\n'):
            if app:
                print(f"  {app}")
    
    # Check what process might be listening for the key
    print("\n6. 👂 Checking what might be listening for media keys:")
    stdout, stderr, code = run_command("ps aux | grep -i 'media\\|totem\\|video' | grep -v grep")
    if stdout:
        print("Media-related processes:")
        print(stdout)
    
    # Check if it's a kernel/hardware mapping
    print("\n7. ⌨️ Checking kernel input events:")
    print("Try: sudo evtest")
    print("This will show raw input events when you press the Framework key")
    
    # Check for hardcoded keysym mappings
    print("\n8. 🔗 Checking if keysym 0x1008ff32 has a standard meaning:")
    stdout, stderr, code = run_command("grep -r '1008ff32\\|XF86Video' /usr/include/ 2>/dev/null | head -3")
    if stdout:
        print("Keysym definitions:")
        print(stdout)
    
    print("\n" + "=" * 60)
    print("🎯 SOLUTIONS TO TRY:")
    print("1. The binding might be hardcoded in the kernel/hardware")
    print("2. Try temporarily remapping the key:")
    print("   xmodmap -e 'keycode 234 = NoSymbol'")
    print("3. Or disable the specific keysym:")
    print("   xmodmap -e 'keysym XF86VideoOut = NoSymbol'")
    print("4. Check if systemd is handling it:")
    print("   systemctl --user mask org.gnome.SettingsDaemon.MediaKeys")
    

def try_disable_framework_key():
    """Try various methods to disable the Framework key."""
    print("🔧 Trying to disable Framework key binding...")
    
    methods = [
        ("xmodmap keycode", "xmodmap -e 'keycode 234 = NoSymbol'"),
        ("xmodmap keysym", "xmodmap -e 'keysym XF86VideoOut = NoSymbol'"),
        ("gsettings video-out", "gsettings set org.gnome.settings-daemon.plugins.media-keys video-out \"\""),
        ("disable media keys service", "systemctl --user stop org.gnome.SettingsDaemon.MediaKeys"),
    ]
    
    for name, cmd in methods:
        print(f"\nTrying {name}:")
        print(f"Command: {cmd}")
        stdout, stderr, code = run_command(cmd)
        if code == 0:
            print(f"✅ Success")
        else:
            print(f"❌ Failed: {stderr}")
        
        input("Press Framework key to test, then press Enter to continue...")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'disable':
        try_disable_framework_key()
    else:
        check_all_bindings()
        print("\nRun with 'disable' to try various disable methods:")
        print("  uv run python deep_check_bindings.py disable")