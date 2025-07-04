# Blurt

**Push-to-talk voice transcription for Linux** - Hold Ctrl+Space, speak, release to type.

## What is Blurt?

Blurt is a lightweight, offline voice-to-text application designed for developers and LLM users who need to quickly dictate text. Perfect for:

- Dictating long LLM prompts without typing
- Taking quick notes while coding
- Writing documentation or comments
- Any text you're too lazy to type

## Features

- **Simple PTT**: Ctrl+Space to start, release Ctrl to stop and transcribe
- **Offline**: Uses Vosk speech recognition - no internet required
- **Lightweight**: Minimal dependencies, fast startup
- **Audio feedback**: Clear start/stop sounds
- **GNOME-first**: Optimized for GNOME desktop environment
- **No sudo required**: Uses standard user permissions

## Quick Start

```bash
# Install (coming soon)
pip install blurt

# Or run from source
git clone https://github.com/voglster/blurt.git
cd blurt
uv run python -m tab_voice.main

# Usage:
# 1. Press Ctrl+Space to start recording
# 2. Speak while holding Ctrl
# 3. Release Ctrl to transcribe and type
```

## Current Status

=� **Alpha Development** - Core functionality works, but rough around the edges.

**Working:**
-  Push-to-talk recording with Ctrl+Space
-  Offline speech recognition (Vosk)
-  Audio feedback sounds
-  Text typing to any application
-  No system dependencies (pure Python)

**Coming Soon:**
- = Proper CLI interface (`blurt start/stop/restart`)
- = Background daemon mode
- = Easy installation and autostart
- = Better error handling and user feedback
- = System tray integration (optional)

## Roadmap

### Phase 1: CLI & Process Management (Current)
- Single `blurt` command with start/stop/restart
- Background daemon with proper process management
- Better configuration and error handling

### Phase 2: Installation & Packaging
- PyPI release: `pip install blurt`
- GNOME autostart integration
- One-command install script
- Clean uninstall process

### Phase 3: User Experience Polish
- Professional audio feedback
- System tray icon (optional)
- Hotkey conflict detection
- Multiple speech model support

### Phase 4: Open Source Release
- Complete documentation
- CI/CD and testing
- Community features and templates

## Requirements

- **OS**: Linux (Ubuntu/Debian tested, others should work)
- **Desktop**: X11 (GNOME tested, others should work)
- **Python**: 3.12+ with uv
- **Audio**: Working microphone and speakers
- **Memory**: ~100MB for speech model

## Architecture

```
blurt/
   src/tab_voice/           # Core application
      main.py             # Entry point
      simple_hotkey.py    # PTT key handling
      simple_audio.py     # Audio recording
      speech_recognizer.py # Vosk integration
      text_output.py      # Keyboard simulation
      sound_player.py     # Audio feedback
      config.py           # Configuration
   sounds/                 # Audio feedback files
   models/                 # Vosk speech models (auto-downloaded)
   pyproject.toml          # Dependencies
```

## Development

Currently using [uv](https://github.com/astral-sh/uv) for fast Python package management:

```bash
# Setup
git clone https://github.com/voglster/blurt.git
cd blurt
uv sync

# Run
uv run python -m tab_voice.main

# Test
uv run python test_keys.py  # Debug key detection
```

## Configuration

Config stored in `~/.config/blurt/config.toml`:

```toml
[audio]
sample_rate = 16000
hold_threshold_ms = 400    # Min hold time
post_release_ms = 300      # Record after release
channels = 1

[model]
path = "models/vosk-model-small-en-us-0.15"

[output]
typing_delay = 0.01        # Delay between characters
```

## Troubleshooting

**No audio detected:**
- Check microphone permissions
- Test with: `uv run python -c "from pvrecorder import PvRecorder; print(PvRecorder.get_audio_devices())"`

**Key detection not working:**
- Ensure X11 (not Wayland): `echo $XDG_SESSION_TYPE`
- Test with: `uv run python test_keys.py`

**Model download fails:**
- Check internet connection
- Manual download: Models available at https://alphacephei.com/vosk/models

## Contributing

This project is in early development. Contributions welcome!

**Priority areas:**
- CLI interface improvement
- Installation and packaging
- Cross-platform testing
- Documentation

## License

[MIT License](LICENSE) - Feel free to use, modify, and distribute.

## Credits

- Speech recognition: [Vosk](https://github.com/alphacep/vosk-api)
- Audio recording: [PvRecorder](https://github.com/Picovoice/pvrecorder)
- Key handling: [pynput](https://github.com/moses-palmer/pynput)
- Audio feedback sounds: [Quip](https://github.com/voglster/quip)

---

*"Speak your mind, type at the speed of thought."*
