# Blurt - Voice to Text PTT Application

## Project Overview

Blurt is a push-to-talk voice transcription app for Linux developers and LLM users. The primary use case is quickly dictating text that you don't want to type - like long prompts, documentation, or notes while coding.

**Current state**: Alpha - core functionality works but needs polish.

## Key Design Decisions

1. **Target Users**: Developers and LLM users who want fast voice input
2. **Installation**: `pip install blurt` (when ready)
3. **Platform**: GNOME/Ubuntu primary, others if simple to support
4. **Configuration**: File-based in `~/.config/blurt/config.toml`
5. **Hotkey**: Configurable, default is Ctrl+Space (press to start, hold Ctrl, release to stop)
6. **Speech Model**: Auto-download Vosk English model, configurable path
7. **Privacy**: Completely offline, no telemetry

## Technical Architecture

### Current Implementation
- **Entry point**: `src/blurt/main.py`
- **Hotkey handling**: `simple_hotkey.py` - uses pynput for cross-platform key detection
- **Audio recording**: `simple_audio.py` - uses PvRecorder (no system dependencies)
- **Speech recognition**: `speech_recognizer.py` - uses Vosk for offline transcription
- **Text output**: `text_output.py` - uses pynput to simulate keyboard
- **Audio feedback**: `sound_player.py` - uses system audio players
- **Config**: `config.py` - TOML-based configuration

### Key Features Working
- Push-to-talk with Ctrl+Space
- Audio feedback (start/stop sounds)
- Offline speech recognition
- Types transcribed text to any application
- No sudo required

## Immediate TODOs

See [DEV-TODO.md](./DEV-TODO.md) for the complete development roadmap.

Priority order:
1. **Phase 1**: CLI & Process Management (daemon mode, better process handling)
2. **Phase 2**: Installation & Packaging (pip install support)
3. **Phase 3**: User Experience (error handling, better feedback)
4. **Phase 4**: Quality & Release (testing, docs, PyPI)

Key tasks:
- Implement proper daemon mode with logging
- Create Python package structure for `pip install blurt`
- Move config to `~/.config/blurt/`
- Add better error messages and user feedback
- Auto-download Vosk model on first run

## Code Style Guidelines

- Modern Python with type hints
- No async unless necessary (keep it simple)
- Clear error messages for users
- Fail gracefully (no crashes)
- Minimal dependencies

## Known Issues

1. **X11 only**: Doesn't work on Wayland yet
2. **Audio devices**: PvRecorder sometimes has issues with device selection
3. **Key detection**: Some hotkey combinations conflict with system shortcuts
4. **Model size**: First run downloads 50MB model

## Testing

Manual test checklist:
1. `blurt start` - should start daemon
2. `blurt status` - should show running
3. Press Ctrl+Space - should hear start sound
4. Speak clearly - hold Ctrl
5. Release Ctrl - should hear stop sound and see text typed
6. `blurt stop` - should stop daemon

## Future Ideas (Not Now)

- System tray icon
- Multiple language support
- Custom wake words
- Wayland support
- Voice commands (e.g., "new line", "period")
- Integration with specific apps (VS Code, terminals)

## Development Commands

```bash
# Current way to run
uv run python -m blurt.main

# Test key detection
uv run python test_keys.py

# Test audio devices
uv run python -c "from pvrecorder import PvRecorder; print(PvRecorder.get_audio_devices())"

# Future way
pip install -e .
blurt start
```

## Important Context

- Renamed from "tab_voice" to "blurt" throughout codebase
- The Framework laptop key detection code can be removed
- The complex async audio recorder can be simplified
- The X11 hotkey handler didn't work well, pynput is better
- Sound files are from the Quip project
- Config migrated from `~/.config/tab_voice/` to `~/.config/blurt/`

## Questions/Decisions Needed

1. Should we support other hotkeys like "hold right ctrl" only?
2. Should the daemon show any UI (systray) or stay completely hidden?
3. How to handle multiple instances (error or attach to existing)?
4. Should we add a `--verbose` flag for debugging?

Remember: Keep it simple, make it work well for the primary use case first.
