# blurt

Fast personal Linux dictation. Audio is captured locally and streamed to a remote
speech-to-text server over the network (Tailscale, in my case), with live partial
transcripts shown in
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
    - **X11:** types via `xdotool`; clipboard via `xclip`
    - **Wayland:** types via a `/dev/uinput` virtual keyboard (compositor-agnostic — no
      wlroots virtual-keyboard protocol needed, so GNOME/Mutter and Hyprland both work);
      clipboard via `wl-copy` (`wl-clipboard`)
- `pw-cat` (PipeWire utils)
- Monitor layout comes from `hyprctl` under Hyprland and from `xrandr` (`x11-xserver-utils`
  / `xorg-xrandr`) everywhere else
- Python 3.12+ with an **Xft-enabled Tk** for the overlay font — install against the
  system interpreter, not uv's. See [Known issues](#known-issues).
- User in the `input` group, and read/write access to `/dev/uinput` (logind grants this to the active seat; needed for the Wayland typer)
- A reachable STT host running one of:
    - **WhisperLive** on TCP 9091 (default; `[whisper] backend = "whisperlive"`)
    - Wyoming faster-whisper on TCP 10300 (`backend = "wyoming"`)
- Optionally, Ollama on HTTP 11434 for the cleanup pass (`[cleanup] enabled = true`)

## Install

**Debian / Ubuntu:**

    sudo apt install python3-tk xclip wl-clipboard x11-xserver-utils
    # Install on the system interpreter so the overlay gets an Xft (anti-aliased) Tk.
    uv tool install --python /usr/bin/python3 --editable .

**Arch (incl. Omarchy):** take the deps from the repos rather than PyPI — the system
Python is well ahead of what `evdev` and `pillow` ship wheels for, and building them is
pointless when packages exist. A `--system-site-packages` venv is what makes those
visible, and it solves two other things at once: Arch's `tk` is Xft-enabled, and
`python-gobject` is what lets pystray pick its **SNI/appindicator** backend instead of the
X11 one — SNI is what the Hyprland status bars actually implement, so the tray icon shows
up.

    sudo pacman -S --needed tk wl-clipboard \
      python-evdev python-pillow python-websockets python-httpx python-yaml \
      python-xlib python-gobject python-pystray libayatana-appindicator
    python3 -m venv --system-site-packages ~/.local/share/blurt/venv
    ~/.local/share/blurt/venv/bin/pip install -e .
    ln -sf ~/.local/share/blurt/venv/bin/blurt ~/.local/bin/blurt

**Both**, once `blurt` is on PATH:

    mkdir -p ~/.config/blurt
    cp docs/config.example.toml ~/.config/blurt/config.toml
    cp docs/corrections.example.yaml ~/.config/blurt/corrections.yaml
    cp systemd/blurt.service ~/.config/systemd/user/
    systemctl --user daemon-reload
    systemctl --user enable --now blurt.service

The Wayland typer writes to `/dev/uinput`. logind hands that to the active seat on some
distros and not others — if `ls -l /dev/uinput` shows `root:root 0600`, grant it to the
`input` group (which you are already in, for `/dev/input/*`):

    # /etc/udev/rules.d/99-blurt-uinput.rules
    KERNEL=="uinput", GROUP="input", MODE="0660", OPTIONS+="static_node=uinput"

## Benchmark + tune

    blurt bench-stt               # compare STT models on latency + word error rate
    blurt bench-cleanup           # pick fastest acceptable cleanup model
    # Edit ~/.config/blurt/config.toml, then:
    systemctl --user restart blurt

`bench-stt` reads `<name>.wav` + `<name>.txt` fixture pairs from `tests/fixtures/` — real
recordings of your own voice, not synthesized speech, since TTS audio is too clean to
separate the candidates. Record your own with `scripts/record-fixtures.sh`.

Both benchmarks default to the `[stt]` prompting in your own config, so they measure the
setup you actually dictate under. Override with `--initial-prompt` / `--hotwords`, or pass
`--no-prompt` for a bare baseline.

## Model selection

Benchmarked 2026-07-25 on an RTX 3080 with `blurt bench-stt` against recorded
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

**Pin the model server-side.** These numbers are with whisperlive launched with
`-fw deepdml/faster-whisper-large-v3-turbo-ct2` (the `command:` in its compose file).
That activates WhisperLive's
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

- **`[whisper] use_vad` should stay `true`.** Current WhisperLive honours it from the
  client config (`self.use_vad = options.get('use_vad')` in `handle_new_connection`,
  reaching faster-whisper as `vad_filter`). With it off, silence is decoded, and Whisper
  answers dead air by inventing text — measured here as 6.5s of silence producing a
  *completed* segment reading `Claude,Claude Code,Claude Code,Claude Code.`, i.e. this
  config's own `hotwords` string fed back. Completed segments are what gets typed, so
  thinking mid-sentence would commit that garbage into your document. With VAD on, the
  same silence yields nothing and speech either side of the pause is unaffected.
  (One VAD path genuinely *is* ignored: the frame-drop in `process_audio_frames` sits
  behind an `is_tensorrt()` check, so it never applies to the faster-whisper backend.
  Earlier versions of this note over-generalised from that.)
- `[whisper] model` accepts either a Whisper size name (`base.en`, `small.en`) or a
  HuggingFace CTranslate2 repo id. Any model must already be present in the WhisperLive
  container's HuggingFace cache — otherwise the first connection stalls on a multi-GB
  download while you are mid-sentence.
- `[stt] initial_prompt` and `[stt] hotwords` bias decoding toward your vocabulary at no
  latency cost, and are the preferred fix for mis-transcribed technical terms.
  `corrections.yaml` remains as a deterministic backstop.
- `[hotkey]` binds one key on one device. For several keyboards use `[[hotkeys]]`, one
  block per `keycode` + `device` pair; it takes precedence over `[hotkey]`. Every listed
  device is grabbed while recording, so Enter/Esc/C work from whichever keyboard you
  reached for, and a keyboard unplugged mid-session no longer stops the others.
  Prefer a stable `/dev/input/by-id/` or `by-path/` symlink over `eventN`, which renumbers.
- `[[actions]]` binds extra keys that, while recording, hand the transcript to a command on
  stdin instead of typing it — one block per `keycode` + `command` pair. The text is cleaned
  and corrected exactly as a committed one would be, nothing is typed into the focused window,
  and the command is launched detached so a slow sink never holds the keyboard grab. A command
  that cannot start raises a desktop notification rather than stopping the daemon.
- `[overlay] position` is `"center"` (default), `"top-center"`, or `"bottom-center"`. The
  two edge positions sit the same distance in from their edge, and the anchored edge
  decides which way the box grows as the transcript lengthens — down from the top, up
  from the bottom, or both ways from the centre.
- `[overlay] corner_radius` rounds the window via the X11 SHAPE extension; `0` is square.
  SHAPE masks are 1-bit, so the curve is hard-edged rather than anti-aliased. If shaping
  fails the overlay falls back to square corners and logs a warning.
- `[overlay] monitor` selects which monitor the overlay appears on: `"primary"` (default),
  `"focused"`, an output name like `"DP-4"`, or `"pointer"`. Wayland has no primary output,
  so under Hyprland `"primary"` and `"focused"` both mean the focused monitor.
- **Monitor layout comes from `hyprctl monitors -j` under Hyprland**, and from
  `xrandr --listmonitors` elsewhere (still the fallback if hyprctl is unreachable). Two
  reasons, both of which bite on a HiDPI laptop: hyprctl reports each mode in *physical*
  pixels next to a `scale`, and the overlay is an XWayland window laid out in Hyprland's
  *logical* coordinates — a 2880x1920 panel at scale 2 is a 1440x960 box, and the raw mode
  would size the overlay off-screen. And `"pointer"` is only trustworthy through hyprctl:
  the xdotool fallback asks XQueryPointer, which under XWayland sees the pointer only while
  it is over an X11 surface and otherwise returns a stale position.

## Known issues

**The overlay font renders as a blocky bitmap.** The overlay needs a Tk built with Xft.
uv's standalone Python bundles a Tk built *without* it, so `monospace` never resolves and
Tk falls back to the X11 `fixed` bitmap. blurt detects this at startup and logs a warning
naming the fix (`journalctl --user -u blurt`). To fix it, install against the system
interpreter, which has an Xft-enabled Tk:

    sudo apt install python3-tk        # Arch: sudo pacman -S tk
    uv tool install --force --python /usr/bin/python3 --editable .

This is why the install instructions pass `--python /usr/bin/python3`, and why the Arch
path builds a `--system-site-packages` venv instead. Everything else works fine under
uv's Python; the overlay font is the only casualty.

**`[whisper] model` may be ignored** — a server pinned with `-fw` overrides whatever the
client requests. See [Configuration notes](#configuration-notes).

## License

MIT — see [LICENSE](LICENSE).
