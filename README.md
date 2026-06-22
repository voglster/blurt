# blurt

Fast personal Linux dictation. Audio is captured locally and streamed to a remote Wyoming faster-whisper instance (typically `llmbox` over Tailscale). On finalization, the transcript runs through a fast Ollama model for capitalization, punctuation, and tech-term fixes (GitHub, kubectl, JSON, etc.) with a strict 500ms budget — if cleanup is slow or unreachable, you keep the raw whisper output.

## How it works

Tap the dictate key (default: KEY_CALC). A small overlay window appears near the bottom of your screen and fills in with your live transcript as you talk. When you're done:

- **Tap the dictate key again** or press **Enter** — the overlay closes and the text is typed into the window you were originally focused on.
- **Press Esc** — the overlay closes and nothing is typed.
- **Press C** — the overlay closes and the text is copied to the clipboard instead of typed.

Right-click the tray icon for "Copy last transcript" (retrieves the last commit / copy / cancel), "Pause" (suspends the dictate hotkey), and "Quit".

## Requirements

- X11 or Wayland — input injection is auto-detected per session:
    - **X11:** types via `xdotool`; clipboard via `xclip` (`sudo apt install xclip`)
    - **Wayland:** types via a `/dev/uinput` virtual keyboard (compositor-agnostic, works on GNOME/Mutter); clipboard via `wl-copy` (`sudo apt install wl-clipboard`)
- `pw-cat` (PipeWire utils)
- Python 3.12+
- User in the `input` group, and read/write access to `/dev/uinput` (logind grants this to the active seat; needed for the Wayland typer)
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
