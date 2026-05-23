# blurt

Fast personal Linux dictation. Tap the calc key, talk, tap the calc key, text appears in your focused window.

Audio is captured locally and streamed to a remote Wyoming faster-whisper instance (typically `llmbox` over Tailscale). On finalization, the transcript runs through a fast Ollama model for capitalization, punctuation, and tech-term fixes (GitHub, kubectl, JSON, etc.) with a strict 500ms budget — if cleanup is slow or unreachable, you keep the raw whisper output.

## Requirements

- X11 (not Wayland)
- `xdotool`, `pw-cat` (PipeWire utils)
- Python 3.12+
- User in the `input` group (for evdev key access)
- Remote `llmbox` running:
    - Wyoming faster-whisper on TCP 10300
    - Ollama on HTTP 11434

## Install

    uv tool install -e .
    mkdir -p ~/.config/blurt
    # Copy example config + corrections (see docs/superpowers/specs/...)
    cp systemd/blurt.service ~/.config/systemd/user/
    systemctl --user daemon-reload
    systemctl --user enable --now blurt.service

## Benchmark + tune

    blurt bench-cleanup           # pick fastest acceptable model
    # Edit ~/.config/blurt/config.toml [cleanup] model = "..."
    systemctl --user restart blurt

## Design

See `docs/superpowers/specs/2026-05-23-blurt-design.md`.

## License

Personal use. No license granted.
