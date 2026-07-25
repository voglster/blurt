# blurt: accuracy, placement, and profiles — design

**Date:** 2026-07-25
**Status:** approved, implementation in `docs/superpowers/plans/2026-07-25-blurt-accuracy-and-placement.md`

## Motivation

Two independent pressures prompted this round of work.

**The overlay lands on a random monitor.** Reported in daily use. Commit `017c34e`
("place on the monitor under the pointer when there's no window id") did not fix it.

**Transcription accuracy is leaving a lot on the table.** blurt runs `base.en`, the
second-smallest Whisper model, against an RTX 3080 with 10 GB of idle VRAM. A survey
of two open-source SuperWhisper clones (`TakanariShimbo/open-super-whisper`, an
OpenAI-API clipboard tool; `shaneholloman/open-super-whisper`, a macOS whisper.cpp +
Parakeet app) surfaced three ideas worth adopting: better models, decode-time
vocabulary biasing, and per-invocation profiles.

## Current state (verified 2026-07-25)

Environment facts established by inspection, not assumption:

- Desktop: GNOME Shell 46.0, `XDG_SESSION_TYPE=wayland`, Ubuntu.
- Monitors: 3 × 2560×1440 — `HDMI-1` at +0+0, `DP-4` (primary) at +2560+0, `DP-9` at
  +5120+0. XWayland root window spans 7680×1440.
- `llmbox`: RTX 3080, 10240 MiB, driver 580.159.03. Container `whisperlive`
  (`whisperlive-gpu-cu12:local`) publishes 9091→9090. WhisperLive 0.8.0,
  faster-whisper 1.2.0. Model cache holds only `faster-whisper-base.en` and
  `faster-whisper-small.en`.
- Live config: `backend = "whisperlive"`, `model = "base.en"`, `cleanup.enabled = false`.

### Why the overlay placement is random

`_resolve_monitor()` (`src/blurt/overlay.py`) resolves in this order: monitor under the
target window's center → monitor under the pointer → `monitors[0]`.

On Wayland, `Daemon._get_active_window` is hardwired to `lambda: None`
(`src/blurt/daemon.py:106-108`), because Wayland exposes no global window activation.
So the first branch never runs and placement always depends on `_pointer_xy()`, which
shells out to `xdotool getmouselocation`.

Under XWayland, `XQueryPointer` reports the pointer only while it is over an **X11**
surface. `xlsclients` lists just `Discord`, `bambu-studio`, `gsd-xsettings`, `ibus-x11`,
and `mutter-x11-frames` — nearly every application in use is a native Wayland client.
The query therefore returns the pointer's last position over one of those few X11
windows, frozen indefinitely. Three consecutive queries returned an identical stale
`X=6170 Y=1336`. The monitor choice is effectively arbitrary, and changes only when the
user happens to cross an X11 window.

Both compositor-side alternatives are unavailable:

- `org.gnome.Shell.Introspect.GetWindows` → `GDBus.Error:...AccessDenied: GetWindows is
  not allowed` (restricted to portals/privileged callers on GNOME 46).
- `org.gnome.Mutter.DisplayConfig.GetCurrentState` returns monitor geometry but carries
  no pointer or focus information.

There is no unprivileged API on GNOME 46 Wayland for either the pointer position or the
focused window's monitor.

**Consequence for the design:** stop inferring. A deterministic, configured monitor is
strictly better than a heuristic that resolves at random. The overlay is a transient
display surface — the transcript is typed into whichever window the user already had
focused, so overlay placement never affects correctness, only where the user looks.

### What WhisperLive 0.8.0 actually accepts

Read from `/app/whisper_live/server.py` in the running container. The per-client
options dict is forwarded to `ServeClientFasterWhisper` as:

```
language, task, uid, model, initial_prompt, vad_parameters, send_last_n_segments,
no_speech_thresh, clip_audio, same_output_threshold, hotwords, word_timestamps
```

Two findings that contradict blurt's current assumptions:

- **`use_vad` is server-side, not per-client.** The server passes
  `use_vad=self.use_vad` — its own launch flag — and ignores any `use_vad` the client
  sends. blurt's `whisper.use_vad` config key has never had any effect.
- **`initial_prompt` and `hotwords` are both supported** and are forwarded straight to
  faster-whisper. `hotwords` is a comma-separated keyword-boosting string.

`model` accepts either a size name (`small.en`) or a HuggingFace repo id, so
`deepdml/faster-whisper-large-v3-turbo-ct2` and `distil-whisper/distil-large-v3.5-ct2`
are selectable without rebuilding the container. Both must be pre-pulled into the
container's HF cache, or the first connection stalls on a multi-GB download.

Audio framing is also server-side: `raw_pcm_input` is a launch flag, so blurt must keep
converting s16 → float32 client-side. Not worth changing.

## Goals

1. The overlay appears on a predictable monitor, every time.
2. Transcription accuracy improves measurably, chosen by evidence rather than by vibes.
3. Domain vocabulary (GitHub, kubectl, Postgres, JSON, YAML, …) is fixed during decode
   rather than patched afterwards by regex.
4. Documentation describes the system that actually runs.

## Non-goals

- Replacing WhisperLive, or adding a Parakeet/NeMo backend. WhisperLive does not serve
  Parakeet; adopting it would mean a second server. Revisit only if turbo is too slow.
- Local (on-device) inference. Remote-over-Tailscale is a deliberate choice for the
  desktop, which is always on the same LAN as `llmbox`. This becomes an open question
  again for laptop support (tracked as the last Phase 2 item in the plan), where `llmbox`
  may be far away or unreachable — but it is out of scope here.
- Running blurt on the laptop. Tracked as the last Phase 2 item; it needs its own
  brainstorming pass because the hotkey, the latency budget, and the offline story are all
  different there.
- A settings GUI. The config file plus the tray menu is the intended surface.
- Removing `corrections.yaml`. It stays as a deterministic backstop even once
  `initial_prompt`/`hotwords` reduce its workload.

## Design

### Overlay monitor selection

Add `overlay.monitor` to config, a string with three accepted forms:

- `"primary"` (default) — the monitor xrandr marks with `*` in `--listmonitors`.
- an output name, e.g. `"DP-4"` — that monitor.
- `"pointer"` — today's behavior, retained for X11 sessions where it works.

`_list_monitors()` must start returning output names and the primary flag, so the
parser gains a name and a primary bit per monitor. Resolution order becomes:

1. If `overlay.monitor` names an output that exists → use it.
2. If `"primary"` → the primary monitor; if xrandr marks none, the first.
3. If `"pointer"` → target-window monitor, then pointer, then first (today's chain).
4. Anything unresolvable → first monitor, warn once.

Unknown output names must warn rather than crash, since monitors get unplugged.

### Model selection, by measurement

Extend the bench CLI to cover WhisperLive and to report accuracy, not just latency.
`blurt bench-stt` streams a fixture WAV at real-time pace against a list of candidate
models and prints, per model: time to first partial, number of partials, time to final,
final text, and WER against a reference transcript.

Candidates: `base.en` (incumbent), `small.en`, `distil-large-v3.5`,
`large-v3-turbo`. The winner is the most accurate model whose time-to-final stays
within the interactive budget — the overlay already shows text live, so the number that
matters is how long the user waits *after* pressing commit.

The fixture needs a known reference transcript containing the technical vocabulary that
`corrections.yaml` exists to repair, so the bench measures the thing being optimized.

### Decode-time vocabulary biasing

Add an `[stt]` config section carrying `initial_prompt` and `hotwords`, threaded through
`WhisperLiveServer` into the connect payload. Seed both from the terms already listed in
`corrections.yaml` and `cleanup_client.SYSTEM_PROMPT`.

`initial_prompt` biases decoding style and vocabulary; `hotwords` boosts specific tokens.
Neither costs latency — they are decode parameters, not an extra pass.

### Profiles (deferred to phase 2)

OSW's "pipelines" idea: a named bundle of (model, initial_prompt, hotwords, cleanup
instruction) selected per invocation — e.g. `prose` for prod writing, `code` for
identifiers, `raw` for no post-processing. Selection via a modifier held while tapping
the dictate key, readable from evdev's `active_keys()`.

Deliberately deferred: it is worth building only once there is a measured-best model and
working prompt plumbing for a profile to *vary*.

### Hold-to-record (deferred to phase 2)

Record while the dictate key is held, finalize on release, for short utterances.
`HotkeyListener` currently drops every non-`key_down` event, so this needs key_up
plumbing plus a hold-vs-tap discrimination threshold. Independent of everything above.

## Risks

- **`large-v3-turbo` may not keep up with streaming.** WhisperLive re-transcribes a
  growing buffer on each pass; a slower model means sparser partials. Mitigation: the
  bench measures partial cadence explicitly, and `model` is one config line to revert.
- **Model pull is multi-GB.** Must be pre-pulled into the container cache and the cache
  must be a persistent volume, or it re-downloads on container recreate.
- **`initial_prompt` can induce hallucination** on silence — Whisper will sometimes emit
  prompt-adjacent text when given nothing to transcribe. Mitigation: keep the prompt
  short and factual; verify against a silence fixture during the bench.
- **Pinning the overlay is a behavior change.** If the user is working on HDMI-1, the
  overlay appears on DP-4. Accepted: predictable beats random, and it is configurable.
