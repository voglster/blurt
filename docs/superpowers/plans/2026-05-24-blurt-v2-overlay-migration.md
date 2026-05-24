# blurt v2 — Overlay UX Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the live-into-cursor diff/backspace dictation UX with a frameless always-on-top overlay that shows the live transcript, then types/copies/discards on commit, cancel, or copy.

**Architecture:** A new `overlay.py` module owns a Tk window in a worker thread. `hotkey.py` is extended to emit a semantic `KeyEvent` enum and to grab `Enter`/`Esc`/`C` while recording (so they don't reach the focused app). `daemon.py` gets a new state machine with three terminal transitions from RECORDING: COMMIT (→ type at captured window), COPY (→ xclip), CANCEL (→ discard). A small `clipboard.py` module wraps `xclip`. The old `Injector` diff/backspace machinery is deleted and replaced with a single `type_at_window(window_id, text)` function.

**Tech Stack:** Python 3.12, asyncio, evdev (X11 hotkeys), Tk (stdlib, overlay), `xdotool` (type + window activate), `xclip` (clipboard), `pystray` (tray).

**Spec:** `docs/superpowers/specs/2026-05-23-blurt-v2-overlay-ux-design.md`

---

## File Structure

**New files:**
- `src/blurt/overlay.py` — Tk overlay window, runs in own thread; thread-safe `show()`/`set_text()`/`hide()`.
- `src/blurt/clipboard.py` — Thin `copy(text)` wrapper around `xclip -selection clipboard`.
- `tests/test_overlay.py` — Smoke + behavior tests (some skipped on headless).
- `tests/test_clipboard.py` — Subprocess-mocked unit tests.
- `tests/test_hotkey.py` — KeyEvent emission tests with a fake evdev device.
- `tests/test_daemon_state.py` — State machine transition tests with all collaborators faked.

**Modified files:**
- `src/blurt/injector.py` — Stripped to a single `type_at_window(window_id: int, text: str)` function plus the `Runner` protocol & `SubprocessRunner` (kept for testability). Class `Injector` and `diff()` removed.
- `src/blurt/hotkey.py` — `HotkeyListener` now yields `KeyEvent` enum members; supports `set_grab_keys(extra_keys)` to grab additional keys (and ungrab) for the recording state.
- `src/blurt/daemon.py` — New state machine: IDLE → RECORDING → {COMMIT|COPY|CANCEL} → IDLE. Captures target window at session start; wires overlay; updates `_last_text` on every terminal transition; routes tray Pause/CopyLast callbacks.
- `src/blurt/tray.py` — Adds menu items: "Copy last transcript", "Pause", "Quit". New constructor params: `on_copy_last`, `on_toggle_pause`.
- `src/blurt/config.py` — Adds `OverlayConfig` and `ClipboardConfig` dataclasses; threaded through `Config` and `load()`.

**Deleted files:**
- `tests/test_injector_diff.py` (diff function removed)
- `tests/test_injector_driver.py` (Injector class removed)

**Untouched:**
- `audio.py`, `whisper_client.py`, `cleanup_client.py`, `corrections.py`, `cli.py`, `__main__.py`.

---

## Task 1: Add `ClipboardConfig` + `OverlayConfig` to `config.py`

**Files:**
- Modify: `src/blurt/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write failing test** — append to `tests/test_config.py`:

```python
def test_overlay_and_clipboard_defaults(tmp_path):
    from blurt.config import load
    cfg = load(tmp_path / "missing.toml")  # nonexistent → defaults
    assert cfg.overlay.enabled is True
    assert cfg.overlay.position == "bottom-center"
    assert cfg.overlay.width_fraction == 0.6
    assert cfg.overlay.min_height_px == 120
    assert cfg.overlay.max_height_fraction == 0.33
    assert cfg.overlay.opacity == 0.85
    assert cfg.overlay.font == "monospace 18"
    assert cfg.clipboard.tool == "xclip"


def test_overlay_and_clipboard_overrides(tmp_path):
    from blurt.config import load
    p = tmp_path / "config.toml"
    p.write_text(
        "[overlay]\nopacity = 0.5\nwidth_fraction = 0.8\n"
        "[clipboard]\ntool = \"xclip\"\n"
    )
    cfg = load(p)
    assert cfg.overlay.opacity == 0.5
    assert cfg.overlay.width_fraction == 0.8
    assert cfg.clipboard.tool == "xclip"
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `cd ~/src/personal/blurt && uv run pytest tests/test_config.py -v`
Expected: FAIL — `cfg.overlay` attribute does not exist.

- [ ] **Step 3: Add dataclasses to `src/blurt/config.py`**

Add to `src/blurt/config.py` before the `Config` dataclass:

```python
@dataclass(frozen=True)
class OverlayConfig:
    enabled: bool = True
    position: str = "bottom-center"
    width_fraction: float = 0.6
    min_height_px: int = 120
    max_height_fraction: float = 0.33
    opacity: float = 0.85
    font: str = "monospace 18"


@dataclass(frozen=True)
class ClipboardConfig:
    tool: str = "xclip"
```

Update the `Config` dataclass:

```python
@dataclass(frozen=True)
class Config:
    whisper: WhisperConfig = field(default_factory=WhisperConfig)
    cleanup: CleanupConfig = field(default_factory=CleanupConfig)
    hotkey: HotkeyConfig = field(default_factory=HotkeyConfig)
    corrections: CorrectionsConfig = field(default_factory=CorrectionsConfig)
    tray: TrayConfig = field(default_factory=TrayConfig)
    overlay: OverlayConfig = field(default_factory=OverlayConfig)
    clipboard: ClipboardConfig = field(default_factory=ClipboardConfig)
```

Update `load()` to pass them through:

```python
    return Config(
        whisper=WhisperConfig(**data.get("whisper", {})),
        cleanup=CleanupConfig(**data.get("cleanup", {})),
        hotkey=HotkeyConfig(**data.get("hotkey", {})),
        corrections=CorrectionsConfig(**data.get("corrections", {})),
        tray=TrayConfig(**data.get("tray", {})),
        overlay=OverlayConfig(**data.get("overlay", {})),
        clipboard=ClipboardConfig(**data.get("clipboard", {})),
    )
```

- [ ] **Step 4: Run test, expect PASS**

Run: `cd ~/src/personal/blurt && uv run pytest tests/test_config.py -v`
Expected: PASS for both new tests.

- [ ] **Step 5: Commit**

```bash
cd ~/src/personal/blurt
git add src/blurt/config.py tests/test_config.py
git commit -m "Config: add overlay and clipboard sections"
```

---

## Task 2: Add `clipboard.py` module

**Files:**
- Create: `src/blurt/clipboard.py`
- Test: `tests/test_clipboard.py`

- [ ] **Step 1: Write failing test** — create `tests/test_clipboard.py`:

```python
from blurt.clipboard import copy


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], bytes]] = []

    def run(self, args: list[str], stdin_bytes: bytes) -> None:
        self.calls.append((args, stdin_bytes))


def test_copy_invokes_xclip_with_clipboard_selection() -> None:
    runner = FakeRunner()
    copy("hello world", runner=runner)
    assert runner.calls == [
        (["xclip", "-selection", "clipboard"], b"hello world"),
    ]


def test_copy_handles_empty_text() -> None:
    runner = FakeRunner()
    copy("", runner=runner)
    assert runner.calls == []


def test_copy_handles_unicode() -> None:
    runner = FakeRunner()
    copy("héllo", runner=runner)
    assert runner.calls[0][1] == "héllo".encode("utf-8")
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `cd ~/src/personal/blurt && uv run pytest tests/test_clipboard.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `src/blurt/clipboard.py`**

```python
from __future__ import annotations

import logging
import subprocess
from typing import Protocol

log = logging.getLogger(__name__)


class Runner(Protocol):
    def run(self, args: list[str], stdin_bytes: bytes) -> None: ...


class SubprocessRunner:
    def run(self, args: list[str], stdin_bytes: bytes) -> None:
        try:
            subprocess.run(args, input=stdin_bytes, check=False, timeout=2.0)
        except subprocess.TimeoutExpired:
            log.warning("xclip timed out")


def copy(text: str, runner: Runner | None = None) -> None:
    """Place `text` on the X11 CLIPBOARD selection via xclip."""
    if not text:
        return
    runner = runner or SubprocessRunner()
    runner.run(["xclip", "-selection", "clipboard"], text.encode("utf-8"))
```

- [ ] **Step 4: Run test, expect PASS**

Run: `cd ~/src/personal/blurt && uv run pytest tests/test_clipboard.py -v`
Expected: PASS, 3 tests.

- [ ] **Step 5: Commit**

```bash
cd ~/src/personal/blurt
git add src/blurt/clipboard.py tests/test_clipboard.py
git commit -m "Clipboard: add xclip wrapper"
```

---

## Task 3: Strip `injector.py` to one-shot `type_at_window`

**Files:**
- Modify: `src/blurt/injector.py`
- Delete: `tests/test_injector_diff.py`, `tests/test_injector_driver.py`
- Create: `tests/test_injector.py`

This task deletes the diff/backspace machinery that the spec explicitly removes. The `Injector` class and `diff()` function go away; only a one-shot type function remains.

- [ ] **Step 1: Write failing test** — create `tests/test_injector.py`:

```python
from blurt.injector import type_at_window


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def run(self, args: list[str]) -> None:
        self.calls.append(args)


def test_type_at_window_activates_then_types() -> None:
    runner = FakeRunner()
    type_at_window(12345, "hello world", runner=runner, settle_ms=0)
    assert runner.calls == [
        ["xdotool", "windowactivate", "--sync", "12345"],
        ["xdotool", "type", "--clearmodifiers", "--delay", "0", "hello world"],
    ]


def test_type_at_window_skips_when_empty() -> None:
    runner = FakeRunner()
    type_at_window(12345, "", runner=runner, settle_ms=0)
    assert runner.calls == []


def test_type_at_window_without_window_id_just_types() -> None:
    runner = FakeRunner()
    type_at_window(None, "hi", runner=runner, settle_ms=0)
    assert runner.calls == [
        ["xdotool", "type", "--clearmodifiers", "--delay", "0", "hi"],
    ]
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `cd ~/src/personal/blurt && uv run pytest tests/test_injector.py -v`
Expected: FAIL — `type_at_window` not importable.

- [ ] **Step 3: Replace `src/blurt/injector.py`** with:

```python
from __future__ import annotations

import subprocess
import time
from typing import Protocol


class Runner(Protocol):
    def run(self, args: list[str]) -> None: ...


class SubprocessRunner:
    def run(self, args: list[str]) -> None:
        subprocess.run(args, check=False)


def type_at_window(
    window_id: int | None,
    text: str,
    runner: Runner | None = None,
    settle_ms: int = 30,
) -> None:
    """Restore focus to `window_id` (if given) and type `text` via xdotool.

    One-shot: no diff, no backspaces. The overlay UX guarantees the caller
    only invokes this on commit, after the user has visually verified the text.
    """
    if not text:
        return
    runner = runner or SubprocessRunner()
    if window_id is not None:
        runner.run(["xdotool", "windowactivate", "--sync", str(window_id)])
        if settle_ms > 0:
            time.sleep(settle_ms / 1000.0)
    runner.run(["xdotool", "type", "--clearmodifiers", "--delay", "0", text])
```

- [ ] **Step 4: Delete obsolete test files**

```bash
cd ~/src/personal/blurt
git rm tests/test_injector_diff.py tests/test_injector_driver.py
```

- [ ] **Step 5: Run tests, expect PASS**

Run: `cd ~/src/personal/blurt && uv run pytest tests/test_injector.py -v`
Expected: PASS, 3 tests.

Run full suite: `cd ~/src/personal/blurt && uv run pytest -v`
Expected: All non-daemon tests pass. The daemon module currently imports `Injector` and will fail at import — that is fixed in Task 6. For now, you can confirm by running `uv run pytest tests/test_injector.py tests/test_config.py tests/test_clipboard.py -v` — all should pass.

- [ ] **Step 6: Commit**

```bash
cd ~/src/personal/blurt
git add src/blurt/injector.py tests/test_injector.py
git commit -m "Injector: strip to one-shot type_at_window; remove diff/backspace"
```

---

## Task 4: `overlay.py` — Tk window in a worker thread

**Files:**
- Create: `src/blurt/overlay.py`
- Create: `tests/test_overlay.py`

The overlay runs Tk's blocking mainloop on a dedicated thread. The daemon (asyncio main thread) calls `show()`/`set_text()`/`hide()`; the overlay marshals those onto the Tk thread via `tk.after(0, ...)`. The overlay does **not** handle input — `evdev` (in `hotkey.py`) owns that. The overlay is purely a display.

Auto-grow-then-scroll behavior: a `tk.Text` widget is sized based on its rendered content's required height up to `max_height_px`; beyond that, the widget switches to scrolling and auto-pins to the bottom (`see("end")`).

- [ ] **Step 1: Write failing test** — create `tests/test_overlay.py`:

```python
import os

import pytest

# Tk needs a display. Skip the whole module on headless CI.
pytest.importorskip("tkinter")
if not os.environ.get("DISPLAY"):
    pytest.skip("no DISPLAY", allow_module_level=True)

from blurt.overlay import Overlay, OverlayConfig


def test_overlay_lifecycle_smoke() -> None:
    """Construct, show, set_text, hide, stop — without crashing."""
    ov = Overlay(OverlayConfig())
    ov.start()
    try:
        ov.show()
        ov.set_text("hello")
        ov.set_text("hello world")
        ov.hide()
    finally:
        ov.stop()


def test_overlay_set_text_before_show_buffers() -> None:
    ov = Overlay(OverlayConfig())
    ov.start()
    try:
        ov.set_text("buffered")  # before show: must not raise
        ov.show()
        ov.set_text("after show")
        ov.hide()
    finally:
        ov.stop()
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `cd ~/src/personal/blurt && uv run pytest tests/test_overlay.py -v`
Expected: FAIL — module not found (or SKIP if no DISPLAY).

- [ ] **Step 3: Implement `src/blurt/overlay.py`**

```python
from __future__ import annotations

import logging
import threading
import tkinter as tk
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class OverlayConfig:
    enabled: bool = True
    position: str = "bottom-center"
    width_fraction: float = 0.6
    min_height_px: int = 120
    max_height_fraction: float = 0.33
    opacity: float = 0.85
    font: str = "monospace 18"


class Overlay:
    """Frameless always-on-top text overlay backed by Tk.

    Public API is thread-safe. Internally, all Tk calls are marshalled onto
    the Tk mainloop thread via `root.after(0, ...)`.
    """

    def __init__(self, cfg: OverlayConfig) -> None:
        self._cfg = cfg
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._root: tk.Tk | None = None
        self._text_widget: tk.Text | None = None
        self._pending_text: str | None = None
        self._visible: bool = False

    # --- lifecycle ---

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=2.0)

    def stop(self) -> None:
        if self._root is not None:
            self._root.after(0, self._root.quit)
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    # --- public (thread-safe) ---

    def show(self) -> None:
        if self._root is None:
            return
        self._root.after(0, self._show_impl)

    def hide(self) -> None:
        if self._root is None:
            return
        self._root.after(0, self._hide_impl)

    def set_text(self, text: str) -> None:
        if self._root is None:
            self._pending_text = text
            return
        self._root.after(0, lambda: self._set_text_impl(text))

    # --- Tk-thread internals ---

    def _run(self) -> None:
        self._root = tk.Tk()
        self._root.withdraw()
        self._root.overrideredirect(True)
        self._root.attributes("-topmost", True)
        try:
            self._root.attributes("-alpha", self._cfg.opacity)
        except tk.TclError:
            pass
        self._root.configure(bg="#1a1a1a")

        self._text_widget = tk.Text(
            self._root,
            font=self._cfg.font,
            wrap="word",
            bg="#1a1a1a",
            fg="#f0f0f0",
            insertontime=0,
            highlightthickness=0,
            borderwidth=0,
            padx=12,
            pady=10,
        )
        self._text_widget.pack(fill="both", expand=True)
        self._text_widget.configure(state="disabled")

        self._ready.set()
        try:
            self._root.mainloop()
        finally:
            try:
                self._root.destroy()
            except tk.TclError:
                pass
            self._root = None

    def _show_impl(self) -> None:
        assert self._root is not None and self._text_widget is not None
        screen_w = self._root.winfo_screenwidth()
        screen_h = self._root.winfo_screenheight()
        w = int(screen_w * self._cfg.width_fraction)
        h = self._cfg.min_height_px
        x = (screen_w - w) // 2
        y = screen_h - h - 80  # 80px above bottom edge
        self._root.geometry(f"{w}x{h}+{x}+{y}")
        self._root.deiconify()
        self._root.lift()
        self._visible = True
        if self._pending_text is not None:
            self._set_text_impl(self._pending_text)
            self._pending_text = None

    def _hide_impl(self) -> None:
        assert self._root is not None and self._text_widget is not None
        self._visible = False
        self._pending_text = None
        self._root.withdraw()
        self._text_widget.configure(state="normal")
        self._text_widget.delete("1.0", "end")
        self._text_widget.configure(state="disabled")

    def _set_text_impl(self, text: str) -> None:
        assert self._root is not None and self._text_widget is not None
        self._text_widget.configure(state="normal")
        self._text_widget.delete("1.0", "end")
        self._text_widget.insert("1.0", text)
        self._text_widget.configure(state="disabled")
        self._maybe_resize()
        self._text_widget.see("end")

    def _maybe_resize(self) -> None:
        """Auto-grow up to max_height_fraction; beyond that, let it scroll."""
        assert self._root is not None and self._text_widget is not None
        if not self._visible:
            return
        screen_h = self._root.winfo_screenheight()
        max_h = int(screen_h * self._cfg.max_height_fraction)
        # Force layout so we can ask for required height.
        self._text_widget.update_idletasks()
        # Count display lines; multiply by line height for a height estimate.
        line_count = int(self._text_widget.count("1.0", "end", "displaylines") or 1)
        font_metrics = self._text_widget.tk.call("font", "metrics", self._cfg.font, "-linespace")
        line_h = int(font_metrics)
        desired = line_count * line_h + 24  # padding
        new_h = min(max(desired, self._cfg.min_height_px), max_h)
        geom = self._root.geometry()  # "WxH+X+Y"
        size, _, rest = geom.partition("+")
        w_str, _, _ = size.partition("x")
        x_str, _, y_str = rest.partition("+")
        try:
            screen_w = self._root.winfo_screenwidth()
            w = int(w_str)
            new_y = screen_h - new_h - 80
            new_x = (screen_w - w) // 2
            self._root.geometry(f"{w}x{new_h}+{new_x}+{new_y}")
        except ValueError:
            pass
```

- [ ] **Step 4: Run test, expect PASS** (on a machine with `DISPLAY` set)

Run: `cd ~/src/personal/blurt && uv run pytest tests/test_overlay.py -v`
Expected: PASS (or SKIP on headless).

- [ ] **Step 5: Commit**

```bash
cd ~/src/personal/blurt
git add src/blurt/overlay.py tests/test_overlay.py
git commit -m "Overlay: add frameless Tk overlay running in worker thread"
```

---

## Task 5: Extend `hotkey.py` with `KeyEvent` enum + multi-key grab

**Files:**
- Modify: `src/blurt/hotkey.py`
- Create: `tests/test_hotkey.py`

`HotkeyListener` currently yields `None` on every calc-key down. Replace with a generator that yields `KeyEvent` members. While "recording", the listener also watches `KEY_ENTER`, `KEY_ESC`, `KEY_C` and emits the corresponding `COMMIT`/`CANCEL`/`COPY`. Switch via `set_recording(bool)`. When entering recording, the listener calls `dev.grab()` to consume those keys before the focused app sees them; when leaving, `dev.ungrab()`.

The default `keycode` config field still maps to TOGGLE; the extra recording-mode keys are hardcoded (no need to make them configurable now).

- [ ] **Step 1: Write failing test** — create `tests/test_hotkey.py`:

```python
import asyncio

import pytest
from evdev import ecodes

from blurt.hotkey import HotkeyListener, KeyEvent


class FakeKeyEvent:
    """Mimic evdev.KeyEvent enough for categorize() round-trip."""
    key_down = 1

    def __init__(self, keystate: int) -> None:
        self.keystate = keystate


class FakeInputEvent:
    def __init__(self, code: int, value: int) -> None:
        self.type = ecodes.EV_KEY
        self.code = code
        self.value = value


class FakeDevice:
    def __init__(self, events: list[FakeInputEvent]) -> None:
        self._events = events
        self.grabbed = False
        self.path = "/dev/input/fake"
        self.name = "fake"

    def capabilities(self) -> dict:
        return {ecodes.EV_KEY: list(ecodes.ecodes.values())}

    def grab(self) -> None:
        self.grabbed = True

    def ungrab(self) -> None:
        self.grabbed = False

    def close(self) -> None:
        pass

    async def async_read_loop(self):
        for e in self._events:
            yield e
            await asyncio.sleep(0)


def _key_down(name: str) -> FakeInputEvent:
    return FakeInputEvent(ecodes.ecodes[name], 1)


@pytest.mark.asyncio
async def test_toggle_only_in_idle(monkeypatch) -> None:
    events = [_key_down("KEY_CALC"), _key_down("KEY_ENTER"), _key_down("KEY_C")]
    dev = FakeDevice(events)
    listener = HotkeyListener(device=dev)

    received: list[KeyEvent] = []
    async for ke in listener.events():
        received.append(ke)
        if len(received) == 1:
            break

    assert received == [KeyEvent.TOGGLE]


@pytest.mark.asyncio
async def test_recording_mode_emits_all_four(monkeypatch) -> None:
    events = [_key_down("KEY_CALC"), _key_down("KEY_ENTER"), _key_down("KEY_C"), _key_down("KEY_ESC")]
    dev = FakeDevice(events)
    listener = HotkeyListener(device=dev)
    listener.set_recording(True)

    received: list[KeyEvent] = []
    async for ke in listener.events():
        received.append(ke)
        if len(received) == 4:
            break

    assert received == [KeyEvent.TOGGLE, KeyEvent.COMMIT, KeyEvent.COPY, KeyEvent.CANCEL]


@pytest.mark.asyncio
async def test_set_recording_grabs_and_ungrabs() -> None:
    dev = FakeDevice([])
    listener = HotkeyListener(device=dev)
    listener.set_recording(True)
    assert dev.grabbed is True
    listener.set_recording(False)
    assert dev.grabbed is False
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `cd ~/src/personal/blurt && uv run pytest tests/test_hotkey.py -v`
Expected: FAIL — `KeyEvent` / new constructor sig missing.

- [ ] **Step 3: Rewrite `src/blurt/hotkey.py`**

```python
from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from enum import Enum

from evdev import InputDevice, KeyEvent as EvdevKeyEvent, categorize, ecodes, list_devices

log = logging.getLogger(__name__)


class KeyEvent(Enum):
    TOGGLE = "toggle"
    COMMIT = "commit"
    CANCEL = "cancel"
    COPY = "copy"


def _find_keyboard_with(keycode: str) -> InputDevice:
    target = ecodes.ecodes[keycode]
    for path in list_devices():
        dev = InputDevice(path)
        caps = dev.capabilities().get(ecodes.EV_KEY, [])
        if target in caps:
            log.info("hotkey device: %s (%s)", dev.path, dev.name)
            return dev
        dev.close()
    raise RuntimeError(f"no input device exposes {keycode}; add user to 'input' group?")


class HotkeyListener:
    """Watches an input device for the toggle key plus, while recording,
    Enter/Esc/C. Emits semantic `KeyEvent` values."""

    def __init__(
        self,
        keycode: str = "KEY_CALC",
        device_path: str | None = None,
        device: object | None = None,
    ) -> None:
        self._keycode = keycode
        self._device_path = device_path
        self._toggle_code = ecodes.ecodes[keycode]
        self._commit_code = ecodes.ecodes["KEY_ENTER"]
        self._cancel_code = ecodes.ecodes["KEY_ESC"]
        self._copy_code = ecodes.ecodes["KEY_C"]
        self._recording = False
        self._paused = False
        self._dev = device  # for testing; if None, opened in events()

    def set_recording(self, value: bool) -> None:
        self._recording = value
        if self._dev is None:
            return
        if value:
            try:
                self._dev.grab()
            except Exception as exc:
                log.warning("dev.grab() failed: %s", exc)
        else:
            try:
                self._dev.ungrab()
            except Exception as exc:
                log.warning("dev.ungrab() failed: %s", exc)

    def set_paused(self, value: bool) -> None:
        self._paused = value

    async def events(self) -> AsyncIterator[KeyEvent]:
        if self._dev is None:
            if self._device_path and self._device_path != "auto":
                self._dev = InputDevice(self._device_path)
            else:
                self._dev = _find_keyboard_with(self._keycode)

        try:
            async for event in self._dev.async_read_loop():
                if event.type != ecodes.EV_KEY:
                    continue
                key_event = categorize(event)
                if not isinstance(key_event, EvdevKeyEvent):
                    continue
                if key_event.keystate != EvdevKeyEvent.key_down:
                    continue

                code = event.code
                if code == self._toggle_code:
                    if self._paused:
                        continue
                    yield KeyEvent.TOGGLE
                elif self._recording and code == self._commit_code:
                    yield KeyEvent.COMMIT
                elif self._recording and code == self._cancel_code:
                    yield KeyEvent.CANCEL
                elif self._recording and code == self._copy_code:
                    yield KeyEvent.COPY
        finally:
            try:
                self._dev.close()
            except Exception:
                pass
```

- [ ] **Step 4: Run test, expect PASS**

Run: `cd ~/src/personal/blurt && uv run pytest tests/test_hotkey.py -v`
Expected: PASS, 3 tests.

- [ ] **Step 5: Commit**

```bash
cd ~/src/personal/blurt
git add src/blurt/hotkey.py tests/test_hotkey.py
git commit -m "Hotkey: emit semantic KeyEvent enum; grab Enter/Esc/C while recording"
```

---

## Task 6: Rewrite `daemon.py` state machine

**Files:**
- Modify: `src/blurt/daemon.py`
- Create: `tests/test_daemon_state.py`

Largest single task. The daemon now:
- Holds an `Overlay` instance (constructed eagerly, mainloop running) and a `_last_text` string.
- On `KeyEvent.TOGGLE` from IDLE → `_start_session()`: capture `_target_window` via `xdotool getactivewindow`, show overlay, set recording on hotkey listener, start `_run_session()`.
- During RECORDING: `_run_session()` consumes Whisper partials and calls `overlay.set_text(partial)`. Stores `_current_text`.
- On `KeyEvent.TOGGLE` or `KeyEvent.COMMIT` during RECORDING → finalize: stop audio, await any remaining final from whisper, hide overlay, run cleanup+corrections, call `type_at_window(_target_window, _current_text)`, set `_last_text`.
- On `KeyEvent.COPY` during RECORDING → finalize same, but call `clipboard.copy(_current_text)` instead of typing.
- On `KeyEvent.CANCEL` during RECORDING → cancel audio + session task, hide overlay, set `_last_text` to whatever the last partial was (or empty), do nothing else.
- Always: ungrab hotkey, set state IDLE, set tray IDLE.

Tray callbacks: `on_copy_last` calls `clipboard.copy(self._last_text)`; `on_toggle_pause` flips `_hotkey.set_paused()` and updates tray title.

- [ ] **Step 1: Write failing test** — create `tests/test_daemon_state.py`:

```python
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from blurt.daemon import Daemon, Outcome, State
from blurt.hotkey import KeyEvent


def _make_daemon_with_mocks() -> Daemon:
    """Build a Daemon with all I/O collaborators faked."""
    d = Daemon.__new__(Daemon)  # bypass real __init__
    d._cfg = MagicMock()
    d._cfg.cleanup.enabled = False
    d._cfg.tray.enabled = False
    d._corrections = MagicMock()
    d._corrections.apply.side_effect = lambda s: s
    d._cleanup = MagicMock()
    d._cleanup.aclose = AsyncMock()
    d._whisper_server = MagicMock()
    d._hotkey = MagicMock()
    d._tray = None
    d._overlay = MagicMock()
    d._type_at_window = MagicMock()
    d._clipboard_copy = MagicMock()
    d._get_active_window = MagicMock(return_value=42)
    d._state = State.IDLE
    d._session_task = None
    d._audio = None
    d._stop_event = asyncio.Event()
    d._loop = None
    d._target_window = None
    d._last_text = ""
    d._current_text = ""
    return d


@pytest.mark.asyncio
async def test_commit_types_at_captured_window() -> None:
    d = _make_daemon_with_mocks()
    d._current_text = "hello"
    d._target_window = 42
    await d._finalize(Outcome.COMMIT)
    d._type_at_window.assert_called_once_with(42, "hello")
    d._clipboard_copy.assert_not_called()
    assert d._last_text == "hello"
    assert d._state == State.IDLE


@pytest.mark.asyncio
async def test_copy_writes_to_clipboard_no_typing() -> None:
    d = _make_daemon_with_mocks()
    d._current_text = "yo"
    d._target_window = 42
    await d._finalize(Outcome.COPY)
    d._clipboard_copy.assert_called_once_with("yo")
    d._type_at_window.assert_not_called()
    assert d._last_text == "yo"
    assert d._state == State.IDLE


@pytest.mark.asyncio
async def test_cancel_neither_types_nor_copies_but_remembers() -> None:
    d = _make_daemon_with_mocks()
    d._current_text = "discarded"
    d._target_window = 42
    await d._finalize(Outcome.CANCEL)
    d._type_at_window.assert_not_called()
    d._clipboard_copy.assert_not_called()
    assert d._last_text == "discarded"
    assert d._state == State.IDLE


@pytest.mark.asyncio
async def test_finalize_always_hides_overlay_and_ungrabs() -> None:
    for outcome in (Outcome.COMMIT, Outcome.COPY, Outcome.CANCEL):
        d = _make_daemon_with_mocks()
        d._current_text = "x"
        d._target_window = 42
        await d._finalize(outcome)
        d._overlay.hide.assert_called()
        d._hotkey.set_recording.assert_called_with(False)


def test_copy_last_uses_stored_text() -> None:
    d = _make_daemon_with_mocks()
    d._last_text = "previously"
    d._on_copy_last()
    d._clipboard_copy.assert_called_once_with("previously")


def test_toggle_pause_flips_hotkey() -> None:
    d = _make_daemon_with_mocks()
    d._paused = False
    d._on_toggle_pause()
    assert d._paused is True
    d._hotkey.set_paused.assert_called_with(True)
    d._on_toggle_pause()
    assert d._paused is False
    d._hotkey.set_paused.assert_called_with(False)
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `cd ~/src/personal/blurt && uv run pytest tests/test_daemon_state.py -v`
Expected: FAIL — `Outcome` not importable, `_finalize` missing.

- [ ] **Step 3: Rewrite `src/blurt/daemon.py`**

```python
from __future__ import annotations

import asyncio
import logging
import signal
import subprocess
from enum import Enum
from pathlib import Path

from blurt import clipboard
from blurt.audio import AudioCapture
from blurt.cleanup_client import CleanupClient
from blurt.config import load as load_config
from blurt.corrections import load as load_corrections
from blurt.hotkey import HotkeyListener, KeyEvent
from blurt.injector import type_at_window
from blurt.overlay import Overlay, OverlayConfig
from blurt.tray import Tray, TrayState
from blurt.whisper_client import WhisperLiveServer, WhisperSession, WyomingServer

log = logging.getLogger(__name__)


class State(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    FINALIZING = "finalizing"


class Outcome(Enum):
    COMMIT = "commit"
    COPY = "copy"
    CANCEL = "cancel"


def _xdotool_get_active_window() -> int | None:
    try:
        out = subprocess.run(
            ["xdotool", "getactivewindow"],
            capture_output=True, text=True, check=True, timeout=1.0,
        )
        return int(out.stdout.strip())
    except (subprocess.SubprocessError, ValueError) as exc:
        log.warning("getactivewindow failed: %s", exc)
        return None


class Daemon:
    def __init__(self) -> None:
        self._cfg = load_config()
        self._corrections = load_corrections(Path(self._cfg.corrections.file).expanduser())
        self._cleanup = CleanupClient(
            base_url=f"http://{self._cfg.cleanup.host}:{self._cfg.cleanup.port}",
            model=self._cfg.cleanup.model,
            timeout_ms=self._cfg.cleanup.timeout_ms,
        )
        if self._cfg.whisper.backend == "whisperlive":
            self._whisper_server = WhisperLiveServer(
                host=self._cfg.whisper.host,
                port=self._cfg.whisper.port,
                model=self._cfg.whisper.model,
                use_vad=self._cfg.whisper.use_vad,
            )
        else:
            self._whisper_server = WyomingServer(
                host=self._cfg.whisper.host,
                port=self._cfg.whisper.port,
            )
        self._hotkey = HotkeyListener(
            keycode=self._cfg.hotkey.keycode,
            device_path=self._cfg.hotkey.device,
        )
        self._overlay = Overlay(OverlayConfig(
            enabled=self._cfg.overlay.enabled,
            position=self._cfg.overlay.position,
            width_fraction=self._cfg.overlay.width_fraction,
            min_height_px=self._cfg.overlay.min_height_px,
            max_height_fraction=self._cfg.overlay.max_height_fraction,
            opacity=self._cfg.overlay.opacity,
            font=self._cfg.overlay.font,
        ))
        self._tray = (
            Tray(
                on_quit=self._request_stop,
                on_copy_last=self._on_copy_last,
                on_toggle_pause=self._on_toggle_pause,
            )
            if self._cfg.tray.enabled else None
        )
        self._type_at_window = type_at_window
        self._clipboard_copy = clipboard.copy
        self._get_active_window = _xdotool_get_active_window

        self._state = State.IDLE
        self._session_task: asyncio.Task[None] | None = None
        self._audio: AudioCapture | None = None
        self._stop_event = asyncio.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._target_window: int | None = None
        self._last_text: str = ""
        self._current_text: str = ""
        self._paused: bool = False
        self._outcome: Outcome | None = None

    # --- callbacks (may be invoked from tray thread) ---

    def _request_stop(self) -> None:
        if self._loop is not None and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._stop_event.set)
        else:
            self._stop_event.set()

    def _on_copy_last(self) -> None:
        if self._last_text:
            self._clipboard_copy(self._last_text)

    def _on_toggle_pause(self) -> None:
        self._paused = not self._paused
        self._hotkey.set_paused(self._paused)
        if self._tray is not None:
            self._tray.set_paused(self._paused)

    def _set_tray(self, state: State) -> None:
        if self._tray is None:
            return
        mapping = {
            State.IDLE: TrayState.IDLE,
            State.RECORDING: TrayState.RECORDING,
            State.FINALIZING: TrayState.PROCESSING,
        }
        self._tray.set_state(mapping[state])

    # --- session ---

    async def _start_session(self) -> None:
        log.info("session start")
        self._state = State.RECORDING
        self._set_tray(self._state)
        self._target_window = self._get_active_window()
        self._current_text = ""
        self._outcome = None
        self._overlay.show()
        self._overlay.set_text("")
        self._hotkey.set_recording(True)
        self._audio = AudioCapture()
        await self._audio.start()
        self._session_task = asyncio.create_task(self._run_session())

    async def _run_session(self) -> None:
        assert self._audio is not None
        session = WhisperSession(server=self._whisper_server)
        try:
            async for event in session.run(self._audio.chunks()):
                self._current_text = event.text
                self._overlay.set_text(event.text)
                if event.is_final:
                    break
        except Exception as exc:
            log.warning("session error: %s", exc)

    async def _finalize(self, outcome: Outcome) -> None:
        """Terminal transition out of RECORDING. Always returns daemon to IDLE."""
        log.info("finalize outcome=%s", outcome)
        self._state = State.FINALIZING
        self._set_tray(self._state)

        # Let trailing audio reach whisper before we tear down.
        await asyncio.sleep(0.3)
        if self._audio is not None:
            await self._audio.stop()
            self._audio = None
        if self._session_task is not None:
            try:
                await self._session_task
            except Exception as exc:
                log.warning("session task failed during finalize: %s", exc)
            self._session_task = None

        text = self._current_text

        # Cleanup + corrections only apply on COMMIT and COPY (not CANCEL).
        if outcome in (Outcome.COMMIT, Outcome.COPY) and text:
            if self._cfg.cleanup.enabled:
                cleaned = await self._cleanup.cleanup(text)
                if cleaned:
                    text = cleaned
            text = self._corrections.apply(text)

        self._overlay.hide()
        self._hotkey.set_recording(False)

        if outcome == Outcome.COMMIT:
            self._type_at_window(self._target_window, text)
        elif outcome == Outcome.COPY:
            self._clipboard_copy(text)
        # CANCEL: do nothing.

        self._last_text = text
        self._state = State.IDLE
        self._set_tray(self._state)
        self._target_window = None

    async def _handle_key(self, ke: KeyEvent) -> None:
        if self._state == State.IDLE:
            if ke == KeyEvent.TOGGLE:
                await self._start_session()
            return

        if self._state == State.RECORDING:
            if ke in (KeyEvent.TOGGLE, KeyEvent.COMMIT):
                await self._finalize(Outcome.COMMIT)
            elif ke == KeyEvent.COPY:
                await self._finalize(Outcome.COPY)
            elif ke == KeyEvent.CANCEL:
                await self._finalize(Outcome.CANCEL)
            return

        log.info("key %s ignored in state=%s", ke, self._state)

    # --- main loop ---

    async def run(self) -> int:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
        self._overlay.start()
        if self._tray is not None:
            self._tray.start()
        self._set_tray(self._state)

        self._loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            self._loop.add_signal_handler(sig, self._request_stop)

        events = self._hotkey.events()
        try:
            while not self._stop_event.is_set():
                next_event = asyncio.create_task(events.__anext__())
                stop_task = asyncio.create_task(self._stop_event.wait())
                done, pending = await asyncio.wait(
                    {next_event, stop_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for p in pending:
                    p.cancel()
                if stop_task in done:
                    break
                try:
                    ke = next_event.result()
                except StopAsyncIteration:
                    break
                await self._handle_key(ke)
        finally:
            if self._session_task is not None and not self._session_task.done():
                self._session_task.cancel()
                try:
                    await self._session_task
                except (asyncio.CancelledError, Exception):
                    pass
            if self._audio is not None:
                await self._audio.stop()
            await self._cleanup.aclose()
            self._overlay.stop()
            if self._tray is not None:
                self._tray.stop()
        return 0


def run() -> int:
    return asyncio.run(Daemon().run())
```

- [ ] **Step 4: Run tests, expect PASS**

Run: `cd ~/src/personal/blurt && uv run pytest tests/test_daemon_state.py -v`
Expected: PASS, 6 tests.

Run full suite: `cd ~/src/personal/blurt && uv run pytest -v`
Expected: All tests pass. `test_overlay.py` may SKIP on headless.

- [ ] **Step 5: Commit**

```bash
cd ~/src/personal/blurt
git add src/blurt/daemon.py tests/test_daemon_state.py
git commit -m "Daemon: new state machine with COMMIT/COPY/CANCEL outcomes and overlay"
```

---

## Task 7: Update `tray.py` with Copy-last, Pause, Quit

**Files:**
- Modify: `src/blurt/tray.py`

`Tray` now accepts `on_copy_last` and `on_toggle_pause` callbacks. The menu gains two items. `set_paused(bool)` reflects state in the title.

- [ ] **Step 1: Update `src/blurt/tray.py`**

```python
from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from enum import Enum

import pystray
from PIL import Image, ImageDraw

log = logging.getLogger(__name__)


class TrayState(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"


def _make_icon(state: TrayState) -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    color = {
        TrayState.IDLE: (180, 180, 180, 255),
        TrayState.RECORDING: (220, 40, 40, 255),
        TrayState.PROCESSING: (220, 180, 40, 255),
    }[state]
    draw.ellipse((12, 12, 52, 52), fill=color)
    return img


class Tray:
    def __init__(
        self,
        on_quit: Callable[[], None],
        on_copy_last: Callable[[], None] | None = None,
        on_toggle_pause: Callable[[], None] | None = None,
    ) -> None:
        self._on_quit = on_quit
        self._on_copy_last = on_copy_last
        self._on_toggle_pause = on_toggle_pause
        self._state = TrayState.IDLE
        self._paused = False
        self._icon = pystray.Icon(
            "blurt",
            icon=_make_icon(TrayState.IDLE),
            title="blurt (idle)",
            menu=pystray.Menu(
                pystray.MenuItem("Copy last transcript", self._handle_copy_last),
                pystray.MenuItem(
                    "Pause", self._handle_toggle_pause, checked=lambda _: self._paused
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit", self._handle_quit),
            ),
        )
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()

    def set_state(self, state: TrayState) -> None:
        self._state = state
        self._icon.icon = _make_icon(state)
        self._refresh_title()

    def set_paused(self, paused: bool) -> None:
        self._paused = paused
        self._refresh_title()
        self._icon.update_menu()

    def stop(self) -> None:
        self._icon.stop()

    def _refresh_title(self) -> None:
        suffix = " — paused" if self._paused else ""
        self._icon.title = f"blurt ({self._state.value}){suffix}"

    def _handle_copy_last(self) -> None:
        if self._on_copy_last is not None:
            self._on_copy_last()

    def _handle_toggle_pause(self) -> None:
        if self._on_toggle_pause is not None:
            self._on_toggle_pause()

    def _handle_quit(self) -> None:
        log.info("tray quit requested")
        self._on_quit()
```

- [ ] **Step 2: Run full test suite**

Run: `cd ~/src/personal/blurt && uv run pytest -v`
Expected: All tests pass. No tests exercise Tray directly; the daemon tests use a mock tray.

- [ ] **Step 3: Commit**

```bash
cd ~/src/personal/blurt
git add src/blurt/tray.py
git commit -m "Tray: add Copy last transcript, Pause toggle, and refresh logic"
```

---

## Task 8: Update README and mark v1 spec superseded

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-05-23-blurt-design.md` (v1 spec) — prepend a "Superseded" banner.

- [ ] **Step 1: Add a banner to the v1 spec**

Edit `docs/superpowers/specs/2026-05-23-blurt-design.md`. Add immediately after the H1 title line:

```markdown
> **Status: SUPERSEDED** by `2026-05-23-blurt-v2-overlay-ux-design.md` on 2026-05-24. The live-into-cursor UX described here was replaced by the overlay UX before final adoption. Retained for historical context only.
```

- [ ] **Step 2: Update README**

Open `README.md` and locate the section that describes the dictation UX. Replace any "types directly into the focused window" / "diff and backspace" wording with a short description of the overlay flow:

```markdown
## How it works

Tap the dictate key (default: KEY_CALC). A small overlay window appears near the bottom of your screen and fills in with your live transcript as you talk. When you're done:

- **Tap the dictate key again** or press **Enter** — the overlay closes and the text is typed into the window you were originally focused on.
- **Press Esc** — the overlay closes and nothing is typed.
- **Press C** — the overlay closes and the text is copied to the clipboard instead of typed.

Right-click the tray icon for "Copy last transcript" (retrieves the last commit / copy / cancel), "Pause" (suspends the dictate hotkey), and "Quit".
```

Add a short "Dependencies" line noting `xclip` is required.

- [ ] **Step 3: Commit**

```bash
cd ~/src/personal/blurt
git add README.md docs/superpowers/specs/2026-05-23-blurt-design.md
git commit -m "Docs: describe v2 overlay flow; mark v1 spec superseded"
```

---

## Task 9: Manual verification

Automated tests cover state transitions but not the actual user experience. Do these by hand on the X11 desktop.

- [ ] **Step 1: Ensure blurt v1 isn't running**

```bash
pgrep -fa blurt || true
# Kill any running instance you find.
```

- [ ] **Step 2: Install xclip if missing**

```bash
which xclip || sudo apt install -y xclip
```

- [ ] **Step 3: Launch blurt**

```bash
cd ~/src/personal/blurt
uv run blurt
```

- [ ] **Step 4: Verify COMMIT golden path**

1. Focus a text editor (e.g., gedit or a terminal).
2. Tap the dictate key (calc).
3. Speak: *"this is a commit test"*.
4. Confirm the overlay appears at bottom-center and shows the live transcript.
5. Tap calc (or press Enter).
6. Confirm overlay disappears, focus returns to your editor, and text is typed in.

- [ ] **Step 5: Verify COPY path**

1. Focus a terminal with a prompt waiting.
2. Tap calc, speak *"copy test"*.
3. Press **C** (single tap, no modifiers).
4. Confirm overlay disappears, *no `c`* appears in the terminal, and `xclip -o -selection clipboard` returns the transcript.

- [ ] **Step 6: Verify CANCEL path**

1. Tap calc, speak *"discard this"*.
2. Press **Esc**.
3. Confirm overlay disappears, nothing is typed, nothing on clipboard changes.
4. Right-click tray → "Copy last transcript" → verify the cancelled text comes back via paste.

- [ ] **Step 7: Verify Pause**

1. Right-click tray → "Pause".
2. Tap calc; confirm nothing happens.
3. Right-click → "Pause" again to unpause.
4. Tap calc; confirm dictation starts normally.

- [ ] **Step 8: Verify long-dictation auto-grow**

1. Tap calc and dictate ~90 seconds of continuous speech.
2. Watch the overlay grow vertically until it caps at ~1/3 screen, then scroll keeping the latest line in view.

- [ ] **Step 9: Verify key consumption during recording**

1. Focus a terminal.
2. Tap calc to start recording.
3. While recording, type `c`, `Enter`, `Esc` on the physical keyboard. None of those should reach the terminal — `c` should trigger COPY, `Enter` should trigger COMMIT, `Esc` should trigger CANCEL.

- [ ] **Step 10: Commit any final tweaks**

If any of steps 4–9 require fixes (e.g., tuning `settle_ms` for window-activate, fixing focus restoration on a specific WM), apply them and commit.

```bash
cd ~/src/personal/blurt
git status
# commit any fixes with descriptive messages
```

---

## Self-review

**Spec coverage:**
- Overlay module + show/set_text/hide → Task 4. ✓
- Focus capture/restore → Task 6 (`_target_window`, `_xdotool_get_active_window`, `type_at_window`). ✓
- Hotkey expansion (KeyEvent enum, multi-key during recording, grab/ungrab) → Task 5. ✓
- New state machine (COMMIT / COPY / CANCEL) → Task 6. ✓
- `_last_text` updated on all three outcomes → Task 6 (`_finalize` always assigns). ✓
- Tray menu (Copy last / Pause / Quit) → Task 7. ✓
- Config additions (`[overlay]`, `[clipboard]`) → Task 1. ✓
- `clipboard.py` with xclip → Task 2. ✓
- Stripped injector → Task 3. ✓
- Deleted old injector tests → Task 3. ✓
- README + v1 spec marked superseded → Task 8. ✓
- Manual verification of golden + edge paths → Task 9. ✓
- Auto-grow then scroll overlay behavior → Task 4 (`_maybe_resize`). ✓
- Plain xclip, no clipboard-manager integration → Task 2. ✓
- Single `_last_text`, not a ring buffer → Task 6. ✓

**Placeholder scan:** No "TBD" / "TODO" / "appropriate error handling" left in the plan. All steps include the actual code or commands.

**Type consistency:**
- `KeyEvent` enum members: `TOGGLE`, `COMMIT`, `CANCEL`, `COPY` — used identically in Tasks 5 & 6. ✓
- `Outcome` enum: `COMMIT`, `COPY`, `CANCEL` — defined Task 6, only used Task 6. ✓
- `Overlay` public API: `start`, `stop`, `show`, `hide`, `set_text` — same signatures Task 4 & Task 6. ✓
- `type_at_window(window_id, text, runner=None, settle_ms=30)` — signature in Task 3 matches usage in Task 6 (positional `window_id, text`). ✓
- `clipboard.copy(text, runner=None)` — Task 2 matches `self._clipboard_copy(text)` in Task 6. ✓
- `HotkeyListener` API: `events()`, `set_recording(bool)`, `set_paused(bool)` — Task 5 matches usage in Task 6. ✓
- `Tray` constructor: `on_quit`, `on_copy_last`, `on_toggle_pause` — Task 7 matches Task 6 instantiation. ✓
- `Tray.set_paused(bool)` — added Task 7, used in `_on_toggle_pause` (Task 6). ✓
