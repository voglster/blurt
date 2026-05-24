# blurt v2 — Overlay UX Redesign

**Date:** 2026-05-23 (decisions locked 2026-05-24)
**Status:** Approved — open questions resolved; ready for plan
**Predecessor spec:** `2026-05-23-blurt-design.md`

## Why v2

The v1 design types directly into the focused window as whisper emits partials, using a diff-and-backspace rewrite as the transcript evolves. In practice this has three real problems:

1. **No verification before commit.** You can't see what whisper thinks you said until it's already in the document. Misrecognitions land in real files / Slack / commit messages.
2. **Focus fragility.** If anything steals focus mid-dictation (notifications, popups, window manager), backspaces eat the wrong text.
3. **No escape hatch.** Once you start dictating, the only "abort" option is to keep talking until done, then manually delete.

The v2 model: live transcript appears in a frameless overlay window while you speak; on commit, the daemon restores focus to the originally-focused window and types (or copies) the text. The cursor is never touched until you confirm.

## UX

**Activation:** Same as v1 — calc key toggles `idle ↔ recording`.

**While recording:**
- A small frameless always-on-top overlay window appears centered near the screen bottom (configurable).
- The overlay shows the live transcript as whisper emits partials. Big, readable, monospace or large sans.
- Tray icon turns red.
- Focus stays on whatever window the user was using (we capture its window ID at start and never change focus during dictation).

**Stopping / committing:**
- **Tap calc key** OR press **Enter** (the overlay grabs Enter while it's open) → overlay closes, focus is restored to the captured window, text is typed via `xdotool type` (one-shot, no diff/backspace).
- **Press Esc** → overlay closes, nothing is typed. State returns to idle.
- **Press C** (single keypress, no modifiers) → overlay closes, text is copied to clipboard via `xclip` instead of typed. Focus is restored but no keystrokes are sent. A small toast / tray title update confirms ("copied").

**Tray right-click menu:**
- **Copy last transcript** — pastes the last committed/cancelled transcript to clipboard.
- **Pause** — disables the calc-key hotkey temporarily.
- **Quit**.

**Notifications:** None on the happy path. On error (whisper unreachable, etc.) show a desktop notification.

## What gets ripped out

- The entire diff/backspace rewrite logic in `injector.py` (the `Injector` class and the `diff` function are no longer needed during streaming — only a simple one-shot `type` call on commit).
- The `injector` state machine inside the daemon (no `last_typed`, no `reset`).
- The streaming `commit()` calls in `_run_session`.

What stays: the `Injector` *concept* gets simplified to a one-shot `inject_text(text)` and `copy_text(text)` pair.

## What gets added

### `overlay.py` (new module)

Owns the frameless transparent-ish always-on-top window. Built on **Tk** (stdlib, no extra dep) unless we run into rendering issues on GNOME, in which case PyQt6.

Responsibilities:
- `show()` — create/raise the overlay window. Position: bottom-center, ~60% screen width, ~120px tall. Background semi-transparent or dark.
- `set_text(text: str)` — update the displayed transcript. Called from the daemon as partials arrive.
- `hide()` — destroy/withdraw the overlay.
- Capture keys while shown:
  - `Return` → emit `CommitEvent`
  - `Escape` → emit `CancelEvent`
  - `c` (no mods) → emit `CopyEvent`
- Communicates back to the daemon via a thread-safe `asyncio.Queue` (overlay runs in its own thread because Tk's mainloop is blocking).

Key implementation note: Tk on X11 needs `wm_attributes("-type", "splash")` or `-topmost` + `overrideredirect(True)` for true frameless. The window must have focus to grab keys, but we DON'T want to steal focus from the user's target window. Solution: position the overlay, mark it `-topmost`, but **don't grab focus** — instead listen to the calc key globally (already done via evdev) and listen to Esc/C/Enter via a second evdev grab. So the overlay is purely visual; all input is via the existing evdev path.

### Focus capture/restore in `daemon.py`

- At session start (calc tap in idle): record `xdotool getactivewindow` → store as `_target_window`.
- At commit: `xdotool windowactivate $_target_window`, wait a few ms, then `xdotool type --clearmodifiers --delay 0 <text>`.
- At copy: pipe text into `xclip -selection clipboard`. No focus change.
- At cancel: no action.

### Key handling expansion in `hotkey.py`

Currently emits one event stream: `KEY_CALC` toggles. Extend so:
- During idle: only `KEY_CALC` is observed.
- During recording: `KEY_CALC`, `KEY_ENTER`, `KEY_ESC`, `KEY_C` are all observed; daemon interprets them per the UX above.

Simplest implementation: `HotkeyListener` yields `KeyEvent` enum members (`TOGGLE`, `COMMIT`, `CANCEL`, `COPY`) instead of bare toggles. The daemon's state machine maps key→action by current state.

A subtlety: `KEY_C` is a normal letter the user might be using elsewhere — we MUST only react to it when the overlay is open. The daemon's state already gates this. Equally important: when we react to KEY_C, we must consume the keystroke so it doesn't reach the focused app. Evdev grabbing accomplishes this — the listener already does `dev.grab()` implicitly via `async_read_loop`, but we need to verify. If it doesn't, we add explicit `dev.grab()` during recording state and `dev.ungrab()` when returning to idle.

### New state machine in `daemon.py`

```
        ┌─ KEY_CALC → start_session ──────────────────┐
        │                                              ▼
   ┌─ IDLE ◄─── COMMIT done ──── ┌─── FINALIZING ──┐
   │   ▲                          │                  │
   │   │ CANCEL                   │ Esc             │
   │   │                          ▼                  │
   │   └────── RECORDING ◄──── KEY_CALC | Enter ────┘
   │                │
   │                │ C
   │                ▼
   │             COPYING ── copied ──┐
   │                                  │
   └──────────────────────────────────┘
```

Three terminal-ish states from recording: COMMIT (→ type), COPY (→ clipboard), CANCEL (→ discard). All three return to IDLE.

### `Daemon._last_text`

Simple field updated whenever a session completes (committed, copied, or cancelled — yes, even cancelled, so "copy last" still works to retrieve what you just abandoned).

### Tray menu changes in `tray.py`

Add menu items: "Copy last transcript" (calls back to daemon to read `_last_text` and put it in the clipboard), "Pause", "Quit".

## Streaming

Still useful for the overlay — you see text appearing as you talk, which is the WhisperFlow feel. Requires the WhisperLive backend (or equivalent streaming-capable Wyoming server) on llmbox. If only batch is available, the overlay will pop up empty and only fill in at the end — still a usable UX, just less magical.

## Configuration additions

`~/.config/blurt/config.toml`:

```toml
[overlay]
enabled = true
position = "bottom-center"      # only supported value initially
width_fraction = 0.6            # of screen width
min_height_px = 120             # starting height before content forces growth
max_height_fraction = 0.33      # of screen height; beyond this, overlay scrolls
opacity = 0.85
font = "monospace 18"

[clipboard]
tool = "xclip"                  # only supported value initially
```

## Dependencies

- **Tk** (stdlib) — no new dep
- **xclip** (system) — `apt install xclip` if not present

Already present: `xdotool`, `evdev`, `pystray`, `pillow`.

## Implementation plan summary (rough)

1. Add overlay module with `show/set_text/hide` + a simple Tk mainloop running in a thread; expose a thread-safe `update(text)` and `close()` API.
2. Add focus capture: store window ID at session start.
3. Extend hotkey listener to emit semantic events (TOGGLE/COMMIT/CANCEL/COPY) and to grab additional keys during recording.
4. Add `clipboard.py` with `copy(text)` using `xclip`.
5. Rewrite `daemon.py` state machine for COMMIT / COPY / CANCEL outcomes.
6. Delete `Injector` class; replace with two functions `type_at_window(window_id, text)` and `copy(text)`.
7. Update tray menu with "Copy last", "Pause", "Quit".
8. Delete `test_injector_diff.py` and `test_injector_driver.py`. Add tests for the new state transitions and clipboard glue.
9. Update README + the v1 spec → mark superseded.

## Resolved brainstorm decisions

These were the open questions; all are now settled.

| # | Question | Decision |
|---|---|---|
| 1 | Overlay content model | **Current utterance only.** Cleared at the start of each session; no cross-session history rendered in the overlay. |
| 2 | Overlay position | **Fixed bottom-center.** No cursor-following. Configurable via `[overlay].position` later. |
| 3 | Long-dictation overflow | **Auto-grow then scroll.** Overlay grows vertically up to `max_height_px` (default ≈ screen_h / 3), then switches to a scrolling Text widget pinned to the latest line. |
| 4 | Interim vs settled styling | **No distinction.** All text rendered identically; whisper rewrites in place. |
| 5 | "C → copy" clipboard integration | **Plain `xclip` only.** Writes to `clipboard` selection. No greenclip or clipboard-manager-specific code. `[clipboard].tool` stays configurable but `xclip` is the only supported value initially. |
| 6 | Tray "Copy last transcript" history depth | **Just the most recent transcript.** Daemon keeps a single `_last_text`; no ring buffer, no submenu. |

Implementation-level confirmations from the same session:

- **Pause** is a soft pause: hotkey listener keeps running but ignores calc taps while paused. Tray menu toggles it.
- `_last_text` is updated on **all** session terminations (commit, copy, *and* cancel), so a cancelled dictation can still be retrieved via tray.
- Evdev grab of `KEY_C` / `KEY_ENTER` / `KEY_ESC` is explicit: `dev.grab()` on entering RECORDING, `dev.ungrab()` on returning to IDLE. Must be verified during implementation by recording, pressing `c`, and confirming the focused app receives no `c` keystroke.

## Migration

Keep the v1 spec and v1 implementation on disk as reference. New session should:
1. Read this v2 spec and the v1 spec.
2. Use the brainstorming skill to refine open questions.
3. Use writing-plans to lay out the migration.
4. Use subagent-driven-development to execute.

WhisperLive on llmbox is a hard prerequisite for the streaming overlay experience. If it's not running yet, the v2 work can still proceed against the existing batch Wyoming server — the overlay will just stay empty until the final transcript arrives.
