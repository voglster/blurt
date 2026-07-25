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

Benchmarked 2026-07-25 on `llmbox` (RTX 3080) with `blurt bench-stt` against recorded
fixtures, then re-tested under noise and on short clips.
**Result: `deepdml/faster-whisper-large-v3-turbo-ct2`.**

Two findings drove it. First, **prompting matters more than model size**: with
`[stt] initial_prompt` + `hotwords` set, `base.en` went from 0.054 WER to 0.000 on clean
audio, and no larger model beat it there. Second, **clean-room results do not generalise** —
adding noise to the same recordings separated the models clearly:

| SNR | base.en | large-v3-turbo |
|---|---|---|
| 20 dB (quiet office) | 0.000 | 0.000 |
| 10 dB (busy room) | 0.037 | **0.000** |
| 5 dB (hostile) | 0.111 – 0.167 | **0.000 – 0.083** |

`base.en` degrades as noise rises; turbo holds at 0.000 until 5 dB and is still half the
error rate there. Turbo is also unaffected by prompt changes (0.000 even with no prompt)
and did not hallucinate on 2.6–3.0 s clips, clean or noisy — the one failure mode it is
reputed to have.

What turbo costs, all measured:

- ~~800 ms slower to first partial~~ — **eliminated** by pinning the model server-side (see
  below). Turbo now reaches first partial in ~1.1s, faster than base.en managed without
  pinning.
- **~2.5 GB VRAM while a session is active** vs `base.en`'s ~0.5 GB. Released when the
  session ends, so it only contends with other GPU services during actual dictation.
- 1.6 GB on disk vs 141 MB, and a slower first load after a whisperlive restart.

**The model is pinned server-side.** `llmbox`'s whisperlive is launched with
`-fw deepdml/faster-whisper-large-v3-turbo-ct2` (see `command:` in
`/home/jvogel/compose/whisperlive/docker-compose.yml`). That activates WhisperLive's
single-model mode so one instance is reused across connections instead of being rebuilt per
dictation — which cut time-to-first-partial from ~1.6-2.1s to a flat ~1.1s.

**Do not expect to feel this.** ~1.1s appears to be an architectural floor, not a model
limit: WhisperLive's STT loop does not process audio until >=1s is buffered, and base.en
(74M params) and large-v3-turbo (809M) both reach first partial at ~1.1s once the model is
resident. An 11x parameter difference producing identical latency means inference is not the
limiter. Pinning removed the only slack that existed; in live use the floor is further
dwarfed by the time it takes to start speaking. The value of turbo is noise robustness, not
speed.

Two consequences:

- **`[whisper] model` in blurt's config is advisory.** `-fw` overrides whatever a client
  requests. To change models, edit `command:` in that compose file and `docker compose up -d`.
- The first dictation after a whisperlive restart pays a one-time ~1.7s model load. Every
  session after that is ~1.1s to first partial.

Avoid `small.en`: under a shorter `initial_prompt` it silently stopped transcribing after
the first sentence of a test utterance — 20 partials instead of 43, two thirds of the words
gone, no error raised. Deterministic, and non-monotonic (both the longer prompt and no
prompt are fine). Avoid `distil-large-v3.5` too: distil models largely ignore
`initial_prompt`/`hotwords`, so it scored 0.025 where the others scored 0.000.

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
