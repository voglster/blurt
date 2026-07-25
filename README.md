# blurt

Fast personal Linux dictation. Audio is captured locally and streamed to a remote
speech-to-text server on `llmbox` over Tailscale, with live partial transcripts shown in
an overlay as you talk. Two backends are supported: **WhisperLive** (WebSocket, streaming
partials — the default) and **Wyoming faster-whisper** (batch). An optional Ollama cleanup
pass can fix capitalization and punctuation under a strict latency budget; it is off by
default because `initial_prompt` + `hotwords` handle vocabulary at decode time instead.

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
- Python 3.12+ with an **Xft-enabled Tk** for the overlay font. The system
  `python3` + `python3-tk` (`sudo apt install python3-tk`) qualifies; uv's
  standalone Python bundles a Tk built *without* Xft, which renders the overlay
  in a non-anti-aliased bitmap font. Install on the system interpreter (see below).
- User in the `input` group, and read/write access to `/dev/uinput` (logind grants this to the active seat; needed for the Wayland typer)
- Remote `llmbox` running one of:
    - **WhisperLive** on TCP 9091 (default; `[whisper] backend = "whisperlive"`)
    - Wyoming faster-whisper on TCP 10300 (`backend = "wyoming"`)
- Optionally, Ollama on HTTP 11434 for the cleanup pass (`[cleanup] enabled = true`)

## Install

    # Install on the system interpreter so the overlay gets an Xft (anti-aliased) Tk.
    uv tool install --python /usr/bin/python3 --editable .
    mkdir -p ~/.config/blurt
    cp docs/config.example.toml ~/.config/blurt/config.toml
    cp docs/corrections.example.yaml ~/.config/blurt/corrections.yaml
    cp systemd/blurt.service ~/.config/systemd/user/
    systemctl --user daemon-reload
    systemctl --user enable --now blurt.service

## Benchmark + tune

    blurt bench-stt               # compare STT models on latency + word error rate
    blurt bench-cleanup           # pick fastest acceptable cleanup model
    # Edit ~/.config/blurt/config.toml, then:
    systemctl --user restart blurt

`bench-stt` reads `<name>.wav` + `<name>.txt` fixture pairs from `tests/fixtures/` — real
recordings of your own voice, not synthesized speech, since TTS audio is too clean to
separate the candidates.

## Model selection

Benchmarked 2026-07-25 on `llmbox` (RTX 3080) against four recorded fixtures, using
`blurt bench-stt`. **Result: `base.en` with `[stt] initial_prompt` + `hotwords` set.**

| model | WER (prompted) | partials/s | on disk | VRAM |
|---|---|---|---|---|
| **base.en** | **0.000** | **3.7** | **141 MB** | **527 MiB** |
| small.en | 0.000 | 3.7 | 464 MB | 975 MiB |
| distil-large-v3.5 | 0.025 | 3.7 | 1.5 GB | — |
| large-v3-turbo | 0.000 | 2.9 | 1.6 GB | — |

The accuracy win came from **prompting, not model size**: `base.en` goes from 0.054
unprompted to 0.000 prompted, and no larger model beat it. Bigger models cost partial
cadence, which is what makes the live overlay feel live.

Two caveats worth knowing before changing `model`:

- **`small.en` silently truncates.** Under a shorter `initial_prompt` it stopped
  transcribing after the first sentence of a test utterance — 20 partials instead of 43,
  two-thirds of the words gone, no error. Deterministic, and non-monotonic (the longer
  prompt and no prompt are both fine). Avoid it.
- **`large-v3-turbo` needs no prompt at all** (0.000 even unprompted), which makes it the
  better choice for noisy or offsite use where per-environment prompt tuning is impractical.
  It is ~25% slower in partial cadence, so it is not the better desktop default.

These fixtures are clean, close-miked, read speech — the regime where small models do best.
Published LibriSpeech WER shows the gap widening on hard audio: base.en 10.2% vs large-v3
5.2% on test-other. Expect to want a bigger model in noisy conditions.

## Configuration notes

- `[whisper] use_vad` has **no effect**. WhisperLive takes VAD as a server launch flag
  (`use_vad=self.use_vad` in its `handle_new_connection`) and ignores whatever the client
  sends in its config payload. To change VAD behavior, change how the WhisperLive
  container is started on `llmbox`.
- `[whisper] model` accepts either a Whisper size name (`base.en`, `small.en`) or a
  HuggingFace CTranslate2 repo id. Any model must already be present in the WhisperLive
  container's HuggingFace cache — otherwise the first connection stalls on a multi-GB
  download while you are mid-sentence.
- `[stt] initial_prompt` and `[stt] hotwords` bias decoding toward your vocabulary at no
  latency cost, and are the preferred fix for mis-transcribed technical terms.
  `corrections.yaml` remains as a deterministic backstop.
- `[overlay] monitor` selects where the overlay appears: `"primary"` (default), an output
  name like `"DP-4"`, or `"pointer"`. Prefer an explicit choice on Wayland — pointer
  resolution needs `xdotool getmouselocation`, which under XWayland only sees the pointer
  while it is over an X11 surface and otherwise returns a stale position.

## Design

- Original design: `docs/superpowers/specs/2026-05-23-blurt-design.md`
- Overlay UX: `docs/superpowers/specs/2026-05-23-blurt-v2-overlay-ux-design.md`
- Accuracy + placement: `docs/superpowers/specs/2026-07-25-blurt-accuracy-and-placement-design.md`

## License

Personal use. No license granted.
