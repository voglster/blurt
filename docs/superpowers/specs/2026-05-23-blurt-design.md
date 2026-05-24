# blurt — Design Spec

> **Status: SUPERSEDED** by `2026-05-23-blurt-v2-overlay-ux-design.md` on 2026-05-24. The live-into-cursor UX described here was replaced by the overlay UX before final adoption. Retained for historical context only.

**Date:** 2026-05-23
**Status:** Approved for planning
**Author:** Matt (with Claude)

## Summary

`blurt` is a personal Linux dictation daemon that replaces nerd-dictation. It captures audio locally, streams it to a remote Wyoming faster-whisper instance on `llmbox` for transcription, types partials live into the focused window via `xdotool`, and applies a fast LLM cleanup pass (Ollama on `llmbox`) on finalization to fix capitalization, punctuation, and tech terms (GitHub, kubectl, Postgres, etc.). Activation is a toggle bound to the calculator key; state is shown via a system tray icon. Hard replacement for nerd-dictation; this is v2.

## Goals

- **Fast.** Sub-second perceived latency from "stop speaking" to "text appears."
- **Accurate on tech terms.** "GitHub" not "git hub"; "kubectl" not "cube cuttle."
- **Effortless.** Toggle, dictate, toggle. No fiddling. Visible recording state.
- **Resilient.** Failures in LLM cleanup never block transcription; whisper output is always the floor.

## Non-Goals

- Wayland support (X11 only).
- Local model fallback (llmbox is always reachable via Tailscale; if not, we surface an error and stop).
- Focus guarding. Known limitation: if the user clicks into another window mid-dictation, backspaces may eat unrelated text.
- Multi-user / multi-language. Single-user, English only for v1.
- Voice commands / macros (nerd-dictation's specialty). Out of scope.

## Architecture

```
┌─ local machine ─────────────────────────────┐      ┌─ llmbox (Tailscale) ────┐
│                                             │      │                         │
│  XF86Calculator ──► hotkey listener         │      │  Wyoming faster-whisper │
│                       │                     │      │  :10300                 │
│                       ▼                     │      │                         │
│  audio (pw-cat) ──► daemon ──► Wyoming ─────┼─────►│  (streams partials)     │
│                       │  client             │      │                         │
│                       │     ◄───── partials ┼──────┤                         │
│                       │                     │      │                         │
│                       │     ──── final ─────┼─────►│  Ollama :11434          │
│                       │     ◄── cleaned ────┼──────┤  (small, no-thinking)   │
│                       ▼                     │      └─────────────────────────┘
│  text injector (xdotool) ──► focused app    │
│         ▲                                   │
│         │                                   │
│  tray icon (AppIndicator)                   │
└─────────────────────────────────────────────┘
```

Single Python daemon. Heavy ML on `llmbox`. Two network connections: persistent Wyoming TCP for whisper; on-demand HTTP for Ollama cleanup.

## Components

1. **`daemon.py`** — long-running process. State machine: `idle → recording → finalizing → idle`. Started via `systemd --user` unit.
2. **Hotkey listener** — `python-evdev` grabbing the keyboard device, watches for `KEY_CALC`. Toggle on each press. Avoids X-grab conflicts.
3. **Audio capture** — `pw-cat --record --format=s16 --rate=16000 --channels=1` subprocess, stdout piped into the daemon.
4. **Wyoming client** — uses the `wyoming` Python package. Connects to `llmbox:10300`. Streams audio chunks; receives `transcript` events (partial + final).
5. **LLM cleanup client** — async `httpx` POST to `http://llmbox:11434/api/generate` with a fixed system prompt. Hard 500ms timeout. No streaming, no thinking models.
6. **Text injector** — pure function `commit(last_typed, candidate) -> (n_backspaces, tail_to_type)`. Sends `BackSpace × N` then `xdotool type --clearmodifiers --delay 0 <tail>`. Maintains `last_typed` across partials within a session; cleared on session end.
7. **Corrections layer** — optional `~/.config/blurt/corrections.yaml` with simple `pattern: replacement` substitutions applied after LLM cleanup (or instead of it if disabled). Cheap insurance for edge cases.
8. **Tray icon** — `pystray` with three states: idle (mic outline), recording (red filled mic), processing (yellow dot). Right-click menu: pause toggle, last transcript, open log file, quit.

**(v1.5, deferred):**
- Live transcript overlay window.
- Hardware PTT button (ESP32 + arcade switch → MQTT or HTTP webhook → daemon).

## Data Flow

### Happy path

```
t=0     calc key down
        → state idle→recording
        → tray: red
        → start pw-cat subprocess
        → open Wyoming connection, send AudioStart

t=0..N  audio chunks stream to llmbox (100ms frames)
        ← partial transcripts arrive every ~200-400ms
        for each partial:
          injector.commit(partial.text)   # diff + backspace + type tail
          (no LLM during streaming — too slow)

t=N     calc key down again
        → state recording→finalizing
        → tray: yellow
        → send AudioStop, await final transcript
        ← final arrives
        injector.commit(final.text)        # rewrite to whisper's final

        fire LLM cleanup async (500ms budget)
        if returns in time AND text differs:
          injector.commit(cleaned.text)

        apply corrections.yaml subs (always, cheap)
        injector.commit(after_subs)

        → state finalizing→idle
        → tray: gray
        → last_typed cleared
```

### Edge cases

| Case | Behavior |
|---|---|
| Empty utterance / single-word | Wyoming returns final, same flow. Injector no-op if final is empty. |
| Calc key during `finalizing` | Ignored (debounce). |
| Wyoming connection fails / drops mid-stream | Abort to idle, desktop notification "whisper unreachable", leave typed text alone. |
| Ollama timeout / down | Silently skip cleanup. Raw whisper output remains. Log warning. |
| User types during recording | Backspaces will eat their keystrokes. Known limitation, accepted. |
| pw-cat fails to start | Abort to idle, notification "audio capture failed". |
| Very long dictation | Wyoming streams indefinitely; no length cap in v1. |

## Latency Targets

- **Live partial typing:** keystrokes appear within ~400ms of utterance (Wyoming partial cadence).
- **Stop → final typed:** ≤ 300ms after key release for raw whisper final.
- **Stop → cleaned typed:** ≤ 800ms total (raw appears at 300ms, cleaned overwrites at ≤800ms).
- **If cleanup exceeds 500ms budget:** abandoned, raw remains.

## Model Selection

Bench step (precedes daemon work):
1. **Whisper:** confirm Wyoming endpoint at `llmbox:10300` accepts streams and returns partials at ≤500ms cadence. Measure final latency on a 5s utterance. If unacceptable, evaluate switching the Wyoming server's underlying model size.
2. **Cleanup LLM:** measure median `/api/generate` latency on `qwen2.5:1.5b`, `llama3.2:1b`, `phi3:mini` over 5 sample transcripts. Pick lowest median under 300ms with acceptable quality. Bake into default config. No thinking models.

## LLM Cleanup Prompt (initial draft)

```
You are a transcription post-processor. Fix capitalization, punctuation,
and the spelling of well-known technical terms (e.g., GitHub, GitLab,
kubectl, Postgres, PostgreSQL, npm, JSON, YAML, AWS, Docker, Kubernetes,
Python, JavaScript, TypeScript). Do NOT paraphrase, summarize, expand,
or change wording. Do NOT add or remove content. Return ONLY the
corrected text with no quotes, no commentary, no explanation.

Input: {transcript}
Output:
```

Tunable in config.

## Configuration

`~/.config/blurt/config.toml`:

```toml
[whisper]
host = "llmbox"
port = 10300

[cleanup]
enabled = true
host = "llmbox"
port = 11434
model = "qwen2.5:1.5b"   # set by bench step
timeout_ms = 500

[hotkey]
keycode = "KEY_CALC"
device = "auto"          # or explicit /dev/input/eventN

[audio]
command = "pw-cat"       # captured args fixed; configurable host override only

[corrections]
file = "~/.config/blurt/corrections.yaml"

[tray]
enabled = true
```

`corrections.yaml`:

```yaml
- pattern: "(?i)git\\s*hub"
  replacement: "GitHub"
- pattern: "(?i)cube\\s*cuttle"
  replacement: "kubectl"
# ...
```

## Testing

**Unit:**
- `injector.commit()` — pure function, table-driven tests on `(last_typed, candidate)` → `(n_backspaces, tail)`.
- `corrections.apply()` — string in, string out, against a fixture YAML.
- Wyoming framing — mocked socket.

**Integration:**
- End-to-end with a recorded WAV piped to a mock Wyoming server, verify the injector receives the right sequence.
- Live test against real `llmbox` services with a known fixture utterance.

**Manual golden-path:**
1. Tap calc, say "open github dot com", tap calc → "Open GitHub.com" typed.
2. Tap calc, say "git clone the repo and run kubectl apply", tap calc → tech terms correctly cased.
3. Live partials visibly appear in a terminal during dictation.
4. Disconnect llmbox network mid-recording → daemon recovers cleanly, notification shown.
5. Stop Ollama only → whisper still works, no cleanup applied, no user-visible error.

## Installation & Rollout

- Project lives at `~/src/personal/blurt`.
- Packaged with `uv`; installed via `uv tool install -e .` (editable).
- Systemd `--user` unit at `~/.config/systemd/user/blurt.service` for auto-start.
- nerd-dictation is removed / its calc-key binding deleted. Hard replace.

## Open Questions

None blocking; bench step will resolve model choices.

## Future Work (v1.5+)

- Live transcript overlay window (Tk frameless, bottom-center).
- Hardware PTT button (ESP32 → MQTT or HTTP).
- Optional streaming LLM cleanup (chunked partials through LLM if latency allows).
- Per-application corrections profiles (e.g., different terms in IDE vs. chat).
