# blurt Accuracy & Placement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Raise transcription accuracy using the idle capacity of llmbox's RTX 3080 — with the model chosen by measurement rather than assumption — and make the overlay appear on a predictable monitor.

**Architecture:** Five independent slices after a docs pass, each landing as its own commit. Documentation is corrected first because it is the entry point for anyone (human or agent) picking this up, and it currently describes a system that is not running. Then: a stdlib WER helper; `initial_prompt`/`hotwords` threaded into the WhisperLive connect payload so domain vocabulary is fixed at decode time rather than by post-hoc regex; a WhisperLive-aware `bench-stt` that turns model choice into an experiment; the winning model as one config line; and finally, config-driven overlay monitor selection replacing a pointer query that cannot work on this machine.

**Tech Stack:** Python 3.12, asyncio, evdev, Tk, websockets, httpx, pytest (`asyncio_mode = "auto"`), ruff (line-length 100), uv. Remote: WhisperLive 0.8.0 + faster-whisper 1.2.0 on `llmbox:9091`, Ollama on `llmbox:11434`.

**Design doc:** `docs/superpowers/specs/2026-07-25-blurt-accuracy-and-placement-design.md` — read it before Task 1. It records the verified environment facts and why the pointer heuristic cannot work on this machine.

## Global Constraints

- Python `>=3.12`. No new runtime dependencies — WER must be implemented with the stdlib (no `jiwer`, no `numpy`).
- ruff: `line-length = 100`, `target-version = "py312"`. Run `.venv/bin/python -m ruff check src tests` before every commit. The tree was **not** ruff-clean before this plan (4 pre-existing F401/F841); Task 1 fixed those so later tasks inherit a passing gate.
- All 62 existing tests must stay green. Run `.venv/bin/python -m pytest -q`.
- Tests never touch the network or a real device. `llmbox` is reachable only from bench commands and manual verification steps.
- `tests/test_overlay.py` skips without `DISPLAY`; do not add DISPLAY-dependent assertions to `tests/test_overlay_monitor.py` — it must stay pure.
- Comments follow the repo's user-level rule: prefer expressive naming over commentary. A comment is justified only for a non-obvious external fact (e.g. "WhisperLive ignores per-client `use_vad`") or a deliberate performance trick.
- Config keys are additive and backward-compatible: an existing `~/.config/blurt/config.toml` must keep working untouched.
- Commit messages: imperative, no Claude attribution lines.
- Working tree was clean at `017c34e` when this plan was written. If `git status` is dirty at resume time, resolve that before starting a task.

---

## Session Resume Protocol

This plan is written to survive a cleared context. Nothing needed to continue lives in
conversation history — it lives in this file, in the git log, and in the test suite.

### When to clear context

Clear at a **task boundary**, never mid-task. A task boundary means: the task's final
commit exists, `pytest -q` is green, and this file's checkboxes and Progress Log are
updated and committed. Clear when any of these is true:

- A task just completed (the default — one task per context is the ideal cadence).
- Context is past roughly 60% and the next task is non-trivial.
- You have been debugging one thing for more than ~3 failed attempts and are looping —
  record what you learned in the Progress Log, commit, clear, restart fresh.

### How to resume in a clean context

Run this, in order, before touching anything:

```bash
cd ~/src/personal/blurt
git log --oneline -8                      # what has actually landed
git status --short                        # must be clean
.venv/bin/python -m pytest -q             # must be green; note the test count
```

Then read, in order:

1. This plan's **Progress Log** (bottom of file) — the authoritative record of where work stopped.
2. The first task whose steps are not all `- [x]` — that is the next task.
3. The design doc, if the task involves WhisperLive options or monitor resolution.

Do **not** re-derive environment facts (GPU model, WhisperLive option names, why the
pointer query fails). They are recorded in the design doc, verified 2026-07-25. Re-verify
only if a step fails in a way that contradicts them.

### Before clearing

1. Tick the checkboxes you completed in this file.
2. Add a Progress Log row: date, task, commit sha, and anything surprising you learned.
3. Commit this file: `git add docs/superpowers/plans/ && git commit -m "docs: update plan progress"`.
4. State in the final message which task is next.

---

## Task Order

Tasks are numbered in execution order, which differs from value order:

| Task | Slice | Why here |
|---|---|---|
| 1 | Documentation truth-up | Entry point for every later reader; trivial to fix |
| 2 | WER helper | Pure function the bench depends on |
| 3 | `initial_prompt` + `hotwords` | Must land before the bench so the bench can measure prompted vs unprompted |
| 4 | `bench-stt` | Needs Tasks 2 and 3 |
| 5 | Model choice | Needs Task 4's measurements |
| 6 | Overlay monitor pinning | Highest daily value but fully independent — deliberately sequenced after the accuracy work |

Tasks 2–6 touch disjoint files, so a failure in one does not block the others.

---

## File Structure

**Created:**
- `docs/config.example.toml` — a checked-in config matching what actually runs.
- `src/blurt/wer.py` — word error rate between a reference and a hypothesis. Pure, stdlib-only, no I/O.
- `src/blurt/bench/stt_bench.py` — streams fixture WAVs to WhisperLive across candidate models; reports partial cadence, time-to-final, and WER.
- `tests/test_wer.py` — WER unit tests.
- `tests/fixtures/` — recorded WAV + reference transcript pairs for the bench. **Does not exist today**, which is why `blurt bench-whisper` is currently broken (`src/blurt/bench/whisper_bench.py:54` points at a nonexistent default path).

**Modified:**
- `README.md` — describe the system that actually runs.
- `src/blurt/whisper_client.py` — `WhisperLiveServer` accepts and sends `initial_prompt` and `hotwords`.
- `src/blurt/config.py` — new `SttConfig` (`initial_prompt`, `hotwords`); `OverlayConfig.monitor`.
- `src/blurt/daemon.py` — pass the new config through to `WhisperLiveServer` and `Overlay`.
- `src/blurt/cli.py` — register the `bench-stt` subcommand.
- `src/blurt/overlay.py` — add `MonitorInfo` + `_list_monitors_detailed()`; `_resolve_monitor()` gains a `preference` argument; `OverlayConfig` gains `monitor`.
- `tests/test_whisper_client.py` — assert the connect payload carries the new options.
- `tests/test_config.py` — cover the new config keys.
- `tests/test_overlay_monitor.py` — cover named/primary/pointer preference resolution.

**Responsibility boundaries:** `wer.py` stays free of bench concerns so it is trivially
testable. Monitor *discovery* (parsing xrandr) stays separate from monitor *choice*
(applying the preference), because only the latter is worth unit-testing. Config only
carries values; all interpretation lives in the module that consumes them.

---

### Task 1: Documentation truth-up

The README describes a system that is not running: it names Wyoming faster-whisper on
10300 as the transcription path and presents Ollama cleanup as the headline feature,
while the live config uses WhisperLive on 9091 with `cleanup.enabled = false`. It also
documents `whisper.use_vad`, which WhisperLive ignores.

**Files:**
- Modify: `README.md`
- Create: `docs/config.example.toml`
- Create: `docs/superpowers/specs/2026-07-25-blurt-accuracy-and-placement-design.md` (already written — verify it is committed)

No tests: this task changes prose only.

- [x] **Step 1: Confirm the design doc and this plan are on disk**

Run: `ls docs/superpowers/specs/2026-07-25-*.md docs/superpowers/plans/2026-07-25-*.md`
Expected: both files listed.

- [x] **Step 2: Rewrite the README's opening and "Requirements" sections**

Replace the opening paragraph so it leads with the real path and presents cleanup as
optional:

```markdown
# blurt

Fast personal Linux dictation. Audio is captured locally and streamed to a remote
speech-to-text server on `llmbox` over Tailscale, with live partial transcripts shown in
an overlay as you talk. Two backends are supported: **WhisperLive** (WebSocket, streaming
partials — the default) and **Wyoming faster-whisper** (batch). An optional Ollama
cleanup pass can fix capitalization and punctuation under a strict latency budget; it is
off by default because `initial_prompt` + `hotwords` handle vocabulary at decode time
instead.
```

Under Requirements, replace the `llmbox` bullet with:

```markdown
- Remote `llmbox` running one of:
    - **WhisperLive** on TCP 9091 (default; `[whisper] backend = "whisperlive"`)
    - Wyoming faster-whisper on TCP 10300 (`backend = "wyoming"`)
- Optionally, Ollama on HTTP 11434 for the cleanup pass (`[cleanup] enabled = true`)
```

- [x] **Step 3: Document the `use_vad` no-op and the model-cache trap**

Add a "Configuration notes" section near the bottom of the README:

```markdown
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
```

- [x] **Step 4: Create a checked-in example config matching reality**

Create `docs/config.example.toml`:

```toml
# Copy to ~/.config/blurt/config.toml and edit.

[whisper]
backend = "whisperlive"   # "whisperlive" (streaming) or "wyoming" (batch)
host = "llmbox"
port = 9091
model = "base.en"         # size name or HF CTranslate2 repo id
use_vad = false           # NO-OP: WhisperLive takes VAD as a server launch flag

[stt]
# Biases decoding toward this vocabulary. Costs no extra latency.
initial_prompt = ""
hotwords = ""

[cleanup]
enabled = false           # optional Ollama post-pass
host = "llmbox"
port = 11434
model = "llama3.2:latest"
timeout_ms = 500

[hotkey]
keycode = "KEY_CALC"
device = "auto"

[corrections]
file = "~/.config/blurt/corrections.yaml"

[overlay]
monitor = "primary"       # "primary", an output name like "DP-4", or "pointer"

[tray]
enabled = true
```

The `[stt]` and `[overlay] monitor` keys are consumed by Tasks 3 and 6. Shipping them in
the example now keeps this file from needing three separate edits, and an unrecognized
key in an older blurt would simply be ignored.

- [x] **Step 5: Verify the README no longer contradicts the live config**

Run: `grep -n "10300\|use_vad\|Wyoming" README.md`
Expected: every remaining mention presents Wyoming as the alternate backend or documents
`use_vad` as a no-op. No line implies Wyoming is the default.

- [x] **Step 6: Commit**

```bash
git add README.md docs/config.example.toml docs/superpowers/
git commit -m "docs: describe the WhisperLive path that actually runs; add design + plan"
```

---

### Task 2: Word error rate helper

**Files:**
- Create: `src/blurt/wer.py`
- Test: `tests/test_wer.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `wer.normalize(text: str) -> list[str]` — lowercase, strip punctuation, split on whitespace
  - `wer.wer(reference: str, hypothesis: str) -> float` — word edit distance ÷ reference word count; `0.0` when both normalize to empty, `1.0` when the reference is empty but the hypothesis is not

- [x] **Step 1: Write the failing tests**

Create `tests/test_wer.py`:

```python
import pytest

from blurt.wer import normalize, wer


def test_normalize_strips_case_and_punctuation():
    assert normalize("Hello, World! It's JSON.") == ["hello", "world", "its", "json"]


def test_identical_text_scores_zero():
    assert wer("open github and run kubectl", "Open GitHub, and run kubectl.") == 0.0


def test_one_substitution_in_four_words():
    assert wer("run kubectl apply now", "run cube cuttle now") == 0.5


def test_deletion_and_insertion_are_counted():
    assert wer("a b c d", "a c d") == 0.25
    assert wer("a b c", "a b x c") == pytest.approx(1 / 3)


def test_empty_reference_and_hypothesis_is_zero():
    assert wer("", "") == 0.0


def test_empty_reference_with_output_is_one():
    assert wer("", "spurious text") == 1.0
```

`test_one_substitution_in_four_words` is the interesting case: the reference has 4 words
and the hypothesis replaces `kubectl apply` with `cube cuttle` — 2 substitutions over 4
reference words = 0.5. That is exactly the failure mode `corrections.yaml` exists to
patch, so it belongs in the suite.

- [x] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_wer.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'blurt.wer'`

- [x] **Step 3: Implement**

Create `src/blurt/wer.py`:

```python
"""Word error rate, stdlib-only, for comparing STT candidates in the bench."""

from __future__ import annotations

import re

_NOT_WORD_CHARS = re.compile(r"[^\w\s]")


def normalize(text: str) -> list[str]:
    return _NOT_WORD_CHARS.sub("", text.lower()).split()


def wer(reference: str, hypothesis: str) -> float:
    ref = normalize(reference)
    hyp = normalize(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    return _edit_distance(ref, hyp) / len(ref)


def _edit_distance(a: list[str], b: list[str]) -> int:
    previous = list(range(len(b) + 1))
    for i, a_word in enumerate(a, start=1):
        current = [i]
        for j, b_word in enumerate(b, start=1):
            current.append(min(
                previous[j] + 1,                              # deletion
                current[j - 1] + 1,                           # insertion
                previous[j - 1] + (a_word != b_word),         # substitution
            ))
        previous = current
    return previous[-1]
```

- [x] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_wer.py -q`
Expected: PASS, 6 tests.

- [x] **Step 5: Commit**

```bash
git add src/blurt/wer.py tests/test_wer.py
git commit -m "wer: add stdlib word error rate helper for STT benchmarking"
```

---

### Task 3: Decode-time vocabulary biasing

**Files:**
- Modify: `src/blurt/whisper_client.py:101-133`
- Modify: `src/blurt/config.py`
- Modify: `src/blurt/daemon.py:68-74`
- Test: `tests/test_whisper_client.py`, `tests/test_config.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `WhisperLiveServer(host, port, model="small.en", language="en", use_vad=True, initial_prompt: str | None = None, hotwords: str | None = None)`
  - `config.SttConfig` — `initial_prompt: str = ""`, `hotwords: str = ""`
  - `config.Config.stt: SttConfig`

Empty config strings must become `None` in the payload, not `""` — faster-whisper treats
an empty-string prompt differently from an absent one.

- [x] **Step 1: Write the failing test for the connect payload**

Add to `tests/test_whisper_client.py`:

```python
import json

from blurt.whisper_client import WhisperLiveServer


class FakeWebSocket:
    """Captures the config payload, then reports the connection closed."""

    def __init__(self) -> None:
        self.sent: list[str | bytes] = []

    async def send(self, data):
        self.sent.append(data)

    async def recv(self):
        raise ConnectionError("closed by test")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


async def _no_audio():
    return
    yield b""


@pytest.mark.asyncio
async def test_connect_payload_carries_prompt_and_hotwords(monkeypatch):
    ws = FakeWebSocket()
    monkeypatch.setattr("websockets.asyncio.client.connect", lambda *a, **k: ws)
    server = WhisperLiveServer(
        host="h", port=1, model="small.en",
        initial_prompt="kubectl, Postgres", hotwords="kubectl,Postgres",
    )

    async for _ in server.stream(_no_audio()):
        pass

    config = json.loads(ws.sent[0])
    assert config["initial_prompt"] == "kubectl, Postgres"
    assert config["hotwords"] == "kubectl,Postgres"
    assert config["model"] == "small.en"


@pytest.mark.asyncio
async def test_connect_payload_omits_blank_prompt(monkeypatch):
    ws = FakeWebSocket()
    monkeypatch.setattr("websockets.asyncio.client.connect", lambda *a, **k: ws)
    server = WhisperLiveServer(host="h", port=1, initial_prompt="", hotwords="")

    async for _ in server.stream(_no_audio()):
        pass

    config = json.loads(ws.sent[0])
    assert config["initial_prompt"] is None
    assert config["hotwords"] is None
```

- [x] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_whisper_client.py -q`
Expected: FAIL — `WhisperLiveServer.__init__() got an unexpected keyword argument 'initial_prompt'`

- [x] **Step 3: Implement**

In `src/blurt/whisper_client.py`, extend `WhisperLiveServer.__init__`:

```python
    def __init__(
        self,
        host: str,
        port: int,
        model: str = "small.en",
        language: str = "en",
        use_vad: bool = True,
        initial_prompt: str | None = None,
        hotwords: str | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._model = model
        self._language = language
        self._use_vad = use_vad
        self._initial_prompt = initial_prompt or None
        self._hotwords = hotwords or None
```

and extend the config payload in `stream()`:

```python
            # use_vad is sent for completeness only: WhisperLive 0.8.0 passes its own
            # server launch flag to the backend and ignores this field.
            await ws.send(json.dumps({
                "uid": uid,
                "language": self._language,
                "task": "transcribe",
                "model": self._model,
                "use_vad": self._use_vad,
                "send_last_n_segments": 10,
                "initial_prompt": self._initial_prompt,
                "hotwords": self._hotwords,
            }))
```

- [x] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_whisper_client.py -q`
Expected: PASS, including the pre-existing session test.

- [x] **Step 5: Write the failing config test**

Add to `tests/test_config.py`:

```python
def test_stt_defaults_are_blank(tmp_path):
    cfg = load(tmp_path / "missing.toml")
    assert cfg.stt.initial_prompt == ""
    assert cfg.stt.hotwords == ""


def test_stt_overrides(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text('[stt]\ninitial_prompt = "kubectl"\nhotwords = "kubectl,JSON"\n')
    cfg = load(p)
    assert cfg.stt.initial_prompt == "kubectl"
    assert cfg.stt.hotwords == "kubectl,JSON"
```

- [x] **Step 6: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_config.py -q`
Expected: FAIL — `AttributeError: 'Config' object has no attribute 'stt'`

- [x] **Step 7: Add the config section**

In `src/blurt/config.py`, add the dataclass next to `WhisperConfig`:

```python
@dataclass(frozen=True)
class SttConfig:
    initial_prompt: str = ""
    hotwords: str = ""
```

add the field to `Config`:

```python
    stt: SttConfig = field(default_factory=SttConfig)
```

and to `load()`:

```python
        stt=SttConfig(**data.get("stt", {})),
```

- [x] **Step 8: Wire it into the daemon**

In `src/blurt/daemon.py`, extend the `WhisperLiveServer` construction:

```python
            self._whisper_server = WhisperLiveServer(
                host=self._cfg.whisper.host,
                port=self._cfg.whisper.port,
                model=self._cfg.whisper.model,
                use_vad=self._cfg.whisper.use_vad,
                initial_prompt=self._cfg.stt.initial_prompt,
                hotwords=self._cfg.stt.hotwords,
            )
```

- [x] **Step 9: Run the full suite and linter**

Run: `.venv/bin/python -m pytest -q && .venv/bin/python -m ruff check src tests`
Expected: green and clean.

- [x] **Step 10: Populate the live config**

Add to `~/.config/blurt/config.toml`, seeded from the terms already in
`corrections.yaml` and `cleanup_client.SYSTEM_PROMPT`:

```toml
[stt]
initial_prompt = "Technical dictation: GitHub, GitLab, kubectl, Postgres, PostgreSQL, JSON, YAML, npm, AWS, Docker, Kubernetes, Python, TypeScript, JavaScript."
hotwords = "GitHub,GitLab,kubectl,Postgres,PostgreSQL,JSON,YAML,npm,AWS,Docker,Kubernetes,TypeScript"
```

- [ ] **Step 11: Verify end to end by hand**

```bash
systemctl --user restart blurt
journalctl --user -u blurt -f    # in another terminal
```
Dictate: "open github and run kubectl apply then check the json output". Expect `GitHub`,
`kubectl`, and `JSON` to appear correctly in the overlay *before* any corrections pass
runs. Then dictate into silence for ~3 seconds and confirm nothing spurious appears — if
prompt-adjacent words leak in, the prompt is too list-like; shorten it to one natural
sentence. Task 4 measures this properly; this step is the smoke test.

- [ ] **Step 12: Commit**

```bash
git add src/blurt/whisper_client.py src/blurt/config.py src/blurt/daemon.py \
        tests/test_whisper_client.py tests/test_config.py
git commit -m "stt: send initial_prompt and hotwords to WhisperLive for decode-time biasing"
```

---

### Task 4: `blurt bench-stt` — measure candidate models

`blurt bench-whisper` today only speaks Wyoming, only reports latency, and defaults to
`tests/fixtures/sample.wav`, which does not exist. This task adds a WhisperLive-aware
bench that reports accuracy, driven by real recordings of the user's own voice.

**Do not synthesize the fixtures with TTS.** WhisperLive scores near-perfectly on clean
synthetic speech, so a TTS-based bench would rank all four candidates identically and
tell us nothing about the microphone, room, and accent the models actually face.

**Files:**
- Create: `src/blurt/bench/stt_bench.py`
- Create: `tests/fixtures/*.wav` + `tests/fixtures/*.txt`
- Modify: `src/blurt/cli.py:30-64`

**Interfaces:**
- Consumes: `wer.wer` (Task 2); `WhisperLiveServer(..., initial_prompt=, hotwords=)` (Task 3); `whisper_client.WhisperSession`.
- Produces: `bench.stt_bench.main() -> int`, registered as the `bench-stt` subcommand.

- [ ] **Step 1: Record the fixtures**

`tests/fixtures/` does not exist. Create it and record three clips, reading each script
aloud at a normal dictation pace:

```bash
mkdir -p ~/src/personal/blurt/tests/fixtures
cd ~/src/personal/blurt/tests/fixtures

cat > tech.txt <<'EOF'
Open GitHub and clone the repo, then run kubectl apply against the staging cluster and check the JSON output for a YAML parse error in the Postgres config.
EOF
pw-cat --record --rate 16000 --channels 1 --format s16 tech.wav   # Ctrl-C when done

cat > prose.txt <<'EOF'
I think the right move here is to ship the smaller change first, measure how it behaves for a week, and only then decide whether the larger refactor is worth the risk.
EOF
pw-cat --record --rate 16000 --channels 1 --format s16 prose.wav

cat > mixed.txt <<'EOF'
Can you review the pull request when you get a chance? The TypeScript types were wrong in the API client, so npm run build was failing in CI on Docker images built from the main branch.
EOF
pw-cat --record --rate 16000 --channels 1 --format s16 mixed.wav
```

Verify each recording:

```bash
.venv/bin/python -c "
import wave
for f in ('tech.wav', 'prose.wav', 'mixed.wav'):
    print(f, wave.open(f).getparams())
"
```
Each must be 16000 Hz, 1 channel, 2 bytes per sample — the bench asserts this.

Also record `silence.wav` (~3 s of room tone, say nothing) with an empty `silence.txt`.
It is the hallucination check: with an `initial_prompt` set, Whisper will sometimes emit
prompt-adjacent text when given nothing to transcribe.

- [ ] **Step 2: Write the bench**

Create `src/blurt/bench/stt_bench.py`:

```python
"""Compare WhisperLive candidate models on latency and accuracy.

Streams each fixture WAV at real-time pace and reports, per model: time to first
partial, partial count, time to final, and WER against the fixture's reference
transcript. Fixtures are `<name>.wav` + `<name>.txt` pairs in tests/fixtures/.
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time
import wave
from dataclasses import dataclass
from pathlib import Path

from blurt.wer import wer as word_error_rate
from blurt.whisper_client import WhisperLiveServer, WhisperSession

FIXTURES = Path(__file__).resolve().parents[3] / "tests" / "fixtures"


@dataclass
class Result:
    fixture: str
    first_partial_ms: float | None
    n_partials: int
    final_ms: float
    wer: float
    text: str


async def _wav_chunks(path: Path, chunk_ms: int = 100):
    with wave.open(str(path), "rb") as w:
        assert w.getframerate() == 16000, f"{path.name}: must be 16kHz"
        assert w.getsampwidth() == 2, f"{path.name}: must be s16"
        assert w.getnchannels() == 1, f"{path.name}: must be mono"
        frames = int(16000 * chunk_ms / 1000)
        while True:
            data = w.readframes(frames)
            if not data:
                return
            yield data
            await asyncio.sleep(chunk_ms / 1000)


async def _run_fixture(
    host: str, port: int, model: str, wav: Path, reference: str,
    initial_prompt: str | None, hotwords: str | None,
) -> Result:
    server = WhisperLiveServer(
        host=host, port=port, model=model,
        initial_prompt=initial_prompt, hotwords=hotwords,
    )
    session = WhisperSession(server=server)
    t0 = time.perf_counter()
    first_partial_ms: float | None = None
    n_partials = 0
    text = ""
    async for event in session.run(_wav_chunks(wav)):
        elapsed_ms = (time.perf_counter() - t0) * 1000
        text = event.text
        if event.is_final:
            break
        n_partials += 1
        if first_partial_ms is None:
            first_partial_ms = elapsed_ms
    return Result(
        fixture=wav.stem,
        first_partial_ms=first_partial_ms,
        n_partials=n_partials,
        final_ms=(time.perf_counter() - t0) * 1000,
        wer=word_error_rate(reference, text),
        text=text,
    )


async def _run(
    host: str, port: int, models: list[str], fixtures: Path,
    initial_prompt: str | None, hotwords: str | None,
) -> None:
    pairs = [(w, w.with_suffix(".txt")) for w in sorted(fixtures.glob("*.wav"))]
    pairs = [(w, t) for w, t in pairs if t.exists()]
    if not pairs:
        raise SystemExit(f"no <name>.wav + <name>.txt pairs in {fixtures}")

    for model in models:
        print(f"\n=== {model} ===")
        results: list[Result] = []
        for wav, txt in pairs:
            reference = txt.read_text().strip()
            r = await _run_fixture(
                host, port, model, wav, reference, initial_prompt, hotwords
            )
            results.append(r)
            first = f"{r.first_partial_ms:.0f}" if r.first_partial_ms else "  -"
            print(
                f"  {r.fixture:10s} wer={r.wer:5.3f} "
                f"first_partial={first:>6s}ms partials={r.n_partials:3d} "
                f"final={r.final_ms:7.0f}ms"
            )
            print(f"    {r.text!r}")
        scored = [r for r in results if r.fixture != "silence"]
        if scored:
            print(
                f"  ---> mean WER {statistics.mean(r.wer for r in scored):.3f}   "
                f"median final {statistics.median(r.final_ms for r in scored):.0f}ms"
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="llmbox")
    parser.add_argument("--port", type=int, default=9091)
    parser.add_argument(
        "--models", nargs="+",
        default=[
            "base.en",
            "small.en",
            "distil-whisper/distil-large-v3.5-ct2",
            "deepdml/faster-whisper-large-v3-turbo-ct2",
        ],
    )
    parser.add_argument("--fixtures", type=Path, default=FIXTURES)
    parser.add_argument("--initial-prompt", default=None)
    parser.add_argument("--hotwords", default=None)
    args = parser.parse_args()
    asyncio.run(_run(
        args.host, args.port, args.models, args.fixtures,
        args.initial_prompt, args.hotwords,
    ))
    return 0
```

- [ ] **Step 3: Register the subcommand**

In `src/blurt/cli.py`, after the `bench-cleanup` parser line, add:

```python
    sub.add_parser("bench-stt", help="Benchmark WhisperLive models on latency + WER")
```

and after the `bench-cleanup` dispatch block:

```python
    if args.cmd == "bench-stt":
        from blurt.bench.stt_bench import main as bench
        return bench()
```

- [ ] **Step 4: Verify the CLI wiring without touching the network**

Run: `.venv/bin/python -m blurt bench-stt --help`
Expected: usage text listing `--host`, `--port`, `--models`, `--fixtures`,
`--initial-prompt`, `--hotwords`.

- [ ] **Step 5: Verify fixture discovery fails loudly**

Run: `.venv/bin/python -m blurt bench-stt --fixtures /tmp/nope`
Expected: exits with `no <name>.wav + <name>.txt pairs in /tmp/nope`.

- [ ] **Step 6: Measure whether prompting actually helps**

```bash
.venv/bin/python -m blurt bench-stt --models base.en
.venv/bin/python -m blurt bench-stt --models base.en \
  --initial-prompt "Technical dictation: GitHub, kubectl, Postgres, JSON, YAML." \
  --hotwords "GitHub,kubectl,Postgres,JSON,YAML"
```
Expected: WER on `tech.wav` drops in the second run, and `silence.wav` still transcribes
to empty or near-empty text. Record both numbers in the Progress Log — this is the
evidence that Task 3 was worth doing, and if WER does *not* drop, say so rather than
assuming it did.

- [ ] **Step 7: Run the full suite and linter**

Run: `.venv/bin/python -m pytest -q && .venv/bin/python -m ruff check src tests`
Expected: green and clean. The bench itself has no unit tests — it is an I/O-bound
measurement tool whose only logic, WER, is tested in Task 2.

- [ ] **Step 8: Commit**

Add `tests/fixtures/*.wav` deliberately — they are small and make the bench reproducible.
Check `.gitignore` does not exclude them first: `grep -n "wav\|fixtures" .gitignore`

```bash
git add src/blurt/bench/stt_bench.py src/blurt/cli.py tests/fixtures
git commit -m "bench: add bench-stt comparing WhisperLive models on latency and WER"
```

---

### Task 5: Choose the model by measurement

Config-and-operations only — no application code changes.

**Files:**
- Modify: `~/.config/blurt/config.toml` (not in the repo)
- Modify: `docs/config.example.toml`
- Modify: `README.md`

- [ ] **Step 1: Confirm the model cache is a persistent volume**

Run: `ssh llmbox 'docker inspect whisperlive --format "{{json .Mounts}}"'`
Expected: a bind or named volume covering the HuggingFace cache. If the cache lives only
in the container filesystem, a 1.5 GB pull is lost on the next `docker rm`, and a volume
must be added before continuing.

- [ ] **Step 2: Pre-pull the candidate models**

```bash
ssh llmbox 'docker exec whisperlive python -c "
from huggingface_hub import snapshot_download
for repo in (\"distil-whisper/distil-large-v3.5-ct2\",
             \"deepdml/faster-whisper-large-v3-turbo-ct2\"):
    print(repo, snapshot_download(repo))
"'
```
Expected: both paths printed. A failure here means the repo id moved — search HuggingFace
for the current CTranslate2 conversion rather than guessing at a name.

- [ ] **Step 3: Verify VRAM headroom**

Run: `ssh llmbox 'docker exec whisperlive nvidia-smi --query-gpu=memory.used,memory.total --format=csv'`
Expected: room for a ~1.6 GB model on top of current usage, out of 10240 MiB. Note the
baseline — if something else on llmbox is holding most of the card, run the bench when it
is idle, or the latency numbers are meaningless.

- [ ] **Step 4: Run the bench across all four candidates**

Run: `.venv/bin/python -m blurt bench-stt 2>&1 | tee /tmp/bench-stt.txt`
Expected: a `mean WER` and `median final` line per model. The first connection to each
newly pulled model includes a one-time model load; if a model's first fixture looks
anomalous, re-run that model alone.

- [ ] **Step 5: Pick the winner and record the evidence**

Selection rule: the lowest mean WER whose **median final** stays under 1500 ms and which
still produces multiple partials per fixture — sparse partials mean the live overlay
stops feeling live, which is blurt's main advantage over the OSW clones.

Paste the bench table into the Progress Log along with the chosen model and the reasoning.

- [ ] **Step 6: Apply the winner**

Set `[whisper] model` in `~/.config/blurt/config.toml` to the winner, then:

```bash
systemctl --user restart blurt
```
Dictate three real sentences containing technical terms and confirm the overlay still
fills in while you speak. If partials feel noticeably sparser than before, revert the one
config line and pick the runner-up.

- [ ] **Step 7: Update docs with the measured result**

Update `docs/config.example.toml`'s `model` line to the winner, and add a short "Model
selection" section to the README naming the winner, its mean WER, its median final
latency, and the date measured — so the next reader does not re-litigate it.

- [ ] **Step 8: Commit**

```bash
git add docs/config.example.toml README.md
git commit -m "docs: record the benchmarked STT model choice"
```

---

### Task 6: Deterministic overlay monitor selection

The overlay lands on an arbitrary monitor because placement depends on
`xdotool getmouselocation`, which under XWayland reports a stale position on a
mostly-Wayland desktop. See the design doc for the full diagnosis and for why both
compositor-side alternatives are unavailable on GNOME 46.

**Files:**
- Modify: `src/blurt/overlay.py`
- Modify: `src/blurt/config.py`
- Modify: `src/blurt/daemon.py:84-92`
- Test: `tests/test_overlay_monitor.py`, `tests/test_config.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `overlay.MonitorInfo` — `NamedTuple(name: str, primary: bool, x: int, y: int, w: int, h: int)`
  - `overlay._parse_listmonitors(output: str) -> list[MonitorInfo]`
  - `overlay._list_monitors_detailed() -> list[MonitorInfo]`
  - `overlay._list_monitors() -> list[tuple[int, int, int, int]]` — unchanged signature, now derived from the detailed list
  - `overlay._resolve_monitor(window_id: int | None, preference: str = "primary") -> tuple[int, int, int, int] | None`
  - `overlay.OverlayConfig.monitor: str = "primary"` and `config.OverlayConfig.monitor: str = "primary"`

`_resolve_monitor` keeps returning a plain `(x, y, w, h)` tuple so `_show_impl` and the
existing tests are untouched. Names and the primary flag are used only during choice.

- [ ] **Step 1: Write the failing tests for detailed monitor parsing**

Add to `tests/test_overlay_monitor.py`:

```python
XRANDR_OUTPUT = """Monitors: 3
 0: +*DP-4 2560/700x1440/390+2560+0  DP-4
 1: +DP-9 2560/600x1440/340+5120+0  DP-9
 2: +HDMI-1 2560/600x1440/340+0+0  HDMI-1
"""


def test_parse_monitors_extracts_names_and_primary_flag():
    mons = overlay._parse_listmonitors(XRANDR_OUTPUT)
    assert [m.name for m in mons] == ["DP-4", "DP-9", "HDMI-1"]
    assert [m.primary for m in mons] == [True, False, False]
    assert mons[0][2:] == (2560, 0, 2560, 1440)


def test_list_monitors_stays_rect_only(monkeypatch):
    monkeypatch.setattr(
        overlay, "_list_monitors_detailed",
        lambda: overlay._parse_listmonitors(XRANDR_OUTPUT),
    )
    assert overlay._list_monitors() == [
        (2560, 0, 2560, 1440), (5120, 0, 2560, 1440), (0, 0, 2560, 1440),
    ]
```

`mons[0][2:]` works because `MonitorInfo` puts `name` and `primary` first, so index 2
onward is the rect. That field ordering is what makes the slice readable.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_overlay_monitor.py -q`
Expected: FAIL — `AttributeError: module 'blurt.overlay' has no attribute '_parse_listmonitors'`

- [ ] **Step 3: Implement parsing**

In `src/blurt/overlay.py`, add `NamedTuple` to the typing imports and replace
`_list_monitors` with:

```python
class MonitorInfo(NamedTuple):
    name: str
    primary: bool
    x: int
    y: int
    w: int
    h: int


_MONITOR_LINE = re.compile(
    r"^\s*\d+:\s+\+(?P<primary>\*?)(?P<name>\S+)\s+"
    r"(?P<w>\d+)/\d+x(?P<h>\d+)/\d+\+(?P<x>-?\d+)\+(?P<y>-?\d+)"
)


def _parse_listmonitors(output: str) -> list[MonitorInfo]:
    """Parse `xrandr --listmonitors`. Lines look like:

        0: +*DP-4 2560/700x1440/390+2560+0  DP-4

    The leading `+` marks an active monitor and `*` marks the primary one.
    """
    monitors: list[MonitorInfo] = []
    for line in output.splitlines():
        m = _MONITOR_LINE.match(line)
        if m:
            monitors.append(MonitorInfo(
                name=m.group("name"),
                primary=bool(m.group("primary")),
                x=int(m.group("x")),
                y=int(m.group("y")),
                w=int(m.group("w")),
                h=int(m.group("h")),
            ))
    return monitors


def _list_monitors_detailed() -> list[MonitorInfo]:
    try:
        out = subprocess.run(
            ["xrandr", "--listmonitors"],
            capture_output=True, text=True, check=True, timeout=1.0,
        ).stdout
    except (subprocess.SubprocessError, FileNotFoundError) as exc:
        log.warning("xrandr --listmonitors failed: %s", exc)
        return []
    return _parse_listmonitors(out)


def _list_monitors() -> list[tuple[int, int, int, int]]:
    """Return [(x, y, w, h), ...] for every monitor."""
    return [(m.x, m.y, m.w, m.h) for m in _list_monitors_detailed()]
```

Delete the old `_list_monitors` body and its inline `pat` regex — `_MONITOR_LINE`
replaces it and additionally anchors on the index prefix, so stray lines cannot match.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_overlay_monitor.py -q`
Expected: PASS, including the six pre-existing tests in that file.

- [ ] **Step 5: Write the failing tests for preference-based resolution**

Add to `tests/test_overlay_monitor.py`:

```python
DETAILED = [
    overlay.MonitorInfo("DP-4", True, 2560, 0, 2560, 1440),
    overlay.MonitorInfo("DP-9", False, 5120, 0, 2560, 1440),
    overlay.MonitorInfo("HDMI-1", False, 0, 0, 2560, 1440),
]


def _patch_monitors(monkeypatch):
    monkeypatch.setattr(overlay, "_list_monitors_detailed", lambda: DETAILED)
    monkeypatch.setattr(overlay, "_list_monitors", lambda: [m[2:] for m in DETAILED])


def test_resolve_monitor_primary_ignores_stale_pointer(monkeypatch):
    _patch_monitors(monkeypatch)
    monkeypatch.setattr(overlay, "_pointer_xy", lambda: (6000, 700))
    assert overlay._resolve_monitor(None, preference="primary") == (2560, 0, 2560, 1440)


def test_resolve_monitor_by_output_name(monkeypatch):
    _patch_monitors(monkeypatch)
    monkeypatch.setattr(overlay, "_pointer_xy", lambda: (6000, 700))
    assert overlay._resolve_monitor(None, preference="HDMI-1") == (0, 0, 2560, 1440)


def test_resolve_monitor_unknown_name_falls_back_to_primary(monkeypatch):
    _patch_monitors(monkeypatch)
    monkeypatch.setattr(overlay, "_pointer_xy", lambda: None)
    assert overlay._resolve_monitor(None, preference="DP-99") == (2560, 0, 2560, 1440)


def test_resolve_monitor_pointer_preference_keeps_old_behavior(monkeypatch):
    _patch_monitors(monkeypatch)
    monkeypatch.setattr(overlay, "_pointer_xy", lambda: (6000, 700))
    assert overlay._resolve_monitor(None, preference="pointer") == (5120, 0, 2560, 1440)


def test_resolve_monitor_primary_falls_back_to_first_when_none_marked(monkeypatch):
    unmarked = [overlay.MonitorInfo("DP-9", False, 5120, 0, 2560, 1440)]
    monkeypatch.setattr(overlay, "_list_monitors_detailed", lambda: unmarked)
    monkeypatch.setattr(overlay, "_list_monitors", lambda: [m[2:] for m in unmarked])
    assert overlay._resolve_monitor(None, preference="primary") == (5120, 0, 2560, 1440)
```

The first test is the regression test for the reported bug: a stale pointer reading on
DP-9 must not drag the overlay off the primary monitor.

- [ ] **Step 6: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_overlay_monitor.py -q`
Expected: FAIL — `_resolve_monitor() got an unexpected keyword argument 'preference'`

- [ ] **Step 7: Implement preference-based resolution**

Replace `_resolve_monitor` in `src/blurt/overlay.py` with:

```python
def _resolve_monitor(
    window_id: int | None, preference: str = "primary"
) -> tuple[int, int, int, int] | None:
    """Pick the monitor to show the overlay on.

    `preference` is an output name, "primary", or "pointer". Pointer resolution is
    only trustworthy on X11: under XWayland, XQueryPointer reports the pointer only
    while it sits over an X11 surface, so on a mostly-Wayland desktop it returns a
    stale position and the overlay lands on an arbitrary monitor.
    """
    detailed = _list_monitors_detailed()
    if not detailed:
        return None

    if preference == "pointer":
        return _resolve_monitor_by_signal(window_id, [m[2:] for m in detailed])

    if preference != "primary":
        for m in detailed:
            if m.name == preference:
                return m[2:]
        log.warning("overlay.monitor=%r matches no output; using primary", preference)

    for m in detailed:
        if m.primary:
            return m[2:]
    return detailed[0][2:]


def _resolve_monitor_by_signal(
    window_id: int | None, monitors: list[tuple[int, int, int, int]]
) -> tuple[int, int, int, int] | None:
    if window_id is not None:
        rect = _window_rect(window_id)
        if rect is not None:
            cx = rect[0] + rect[2] // 2
            cy = rect[1] + rect[3] // 2
            found = _monitor_containing(monitors, cx, cy)
            if found is not None:
                return found
    pos = _pointer_xy()
    if pos is not None:
        found = _monitor_containing(monitors, *pos)
        if found is not None:
            return found
    return monitors[0]
```

The five pre-existing `_resolve_monitor` tests call it with no `preference` and patch
`_list_monitors`, not `_list_monitors_detailed`. Update those five to pass
`preference="pointer"` and to patch via `_patch_monitors`, except
`test_resolve_monitor_none_when_no_monitors`, which should patch
`_list_monitors_detailed` to return `[]`.

- [ ] **Step 8: Run the full overlay monitor suite**

Run: `.venv/bin/python -m pytest tests/test_overlay_monitor.py -q`
Expected: PASS, including the updated pre-existing five.

- [ ] **Step 9: Write the failing config test**

Add to `tests/test_config.py`:

```python
def test_overlay_monitor_defaults_to_primary(tmp_path):
    cfg = load(tmp_path / "missing.toml")
    assert cfg.overlay.monitor == "primary"


def test_overlay_monitor_override(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text('[overlay]\nmonitor = "DP-4"\n')
    assert load(p).overlay.monitor == "DP-4"
```

- [ ] **Step 10: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_config.py -q`
Expected: FAIL — `AttributeError: 'OverlayConfig' object has no attribute 'monitor'`

- [ ] **Step 11: Add the config key and wire it through**

In `src/blurt/config.py`, add to `OverlayConfig`:

```python
    monitor: str = "primary"   # "primary", an output name (e.g. "DP-4"), or "pointer"
```

In `src/blurt/overlay.py`, add the same field to that module's own `OverlayConfig`
dataclass (deliberately decoupled from the config module's):

```python
    monitor: str = "primary"
```

and use it in `show()`:

```python
        self._monitor = _resolve_monitor(target_window, preference=self._cfg.monitor)
```

In `src/blurt/daemon.py`, add to the `Overlay(OverlayConfig(...))` construction:

```python
            monitor=self._cfg.overlay.monitor,
```

- [ ] **Step 12: Run the full suite and linter**

Run: `.venv/bin/python -m pytest -q && .venv/bin/python -m ruff check src tests`
Expected: all tests pass, ruff clean.

- [ ] **Step 13: Verify against the real display**

Run: `.venv/bin/python -c "from blurt import overlay; print(overlay._list_monitors_detailed()); print(overlay._resolve_monitor(None))"`
Expected: three `MonitorInfo` rows with `DP-4` flagged `primary=True`, and the resolved
rect `(2560, 0, 2560, 1440)`.

- [ ] **Step 14: Verify end to end**

```bash
systemctl --user restart blurt
```
Then dictate three times, with the mouse parked on a different monitor each time. The
overlay must appear on DP-4 all three times.

- [ ] **Step 15: Commit**

```bash
git add src/blurt/overlay.py src/blurt/config.py src/blurt/daemon.py \
        tests/test_overlay_monitor.py tests/test_config.py
git commit -m "overlay: pin to a configured monitor instead of a stale pointer query"
```

---

## Phase 2 — not planned in detail yet

Two items from the design doc are deliberately left unplanned. Each is worth its own pass
of the writing-plans skill once Phase 1 has landed, because both should be designed
against the *measured* model and *working* prompt plumbing rather than against today's
setup.

- **Profiles / pipelines** (OSW's best idea): a named bundle of model + `initial_prompt`
  + `hotwords` + cleanup instruction, selected per invocation by a modifier held while
  tapping the dictate key. `HotkeyListener` can read modifier state from evdev's
  `active_keys()`. Only worth building once there is something meaningful to vary.
- **Hold-to-record**: record while the dictate key is held, finalize on release.
  `HotkeyListener.events()` currently drops every event where
  `keystate != key_down` (`src/blurt/hotkey.py:96`), so this needs key_up plumbing plus a
  hold-vs-tap threshold. Fully independent of Phase 1.

- **Laptop support (last in the queue).** Today blurt only runs on jv-desktop, so dictation
  is unavailable offsite and the workflow changes. The goal is the same tap-to-dictate flow
  on the laptop, reaching `llmbox` over Tailscale. This is a portability *and* a latency
  problem, and needs its own brainstorming pass before planning, because several current
  assumptions are desktop-specific:

  - **Hotkey.** `KEY_CALC` almost certainly does not exist on the laptop keyboard, and
    `_find_keyboard_with()` raises outright when no device exposes the keycode
    (`src/blurt/hotkey.py:28`). Needs a laptop-appropriate keycode and a friendlier failure.
  - **Offsite latency.** WhisperLive streams audio continuously and re-transcribes a
    growing buffer; over hotel wifi or a cell hotspot the round trip may make partials
    arrive too late for the overlay to feel live. Measure first with `bench-stt`
    (Task 4) run from the laptop over Tailscale before designing anything.
  - **Offline fallback.** When `llmbox` is unreachable there is currently no degraded mode
    — the session errors and cancels (`Daemon._auto_finalize_on_error`). Options worth
    weighing: a small local faster-whisper/whisper.cpp model on the laptop, batch-on-stop
    instead of streaming when RTT is high, or an explicit "no STT available" notification.
    A local model is where the OSW clones' on-device design becomes genuinely relevant.
  - **Config divergence.** Model choice, `[overlay] monitor`, and hotkey all need to
    differ per machine while sharing one repo. Decide between per-host config files, a
    hostname-suffixed override, or simply not syncing `~/.config/blurt/`.
  - **Session and permissions.** Re-verify Wayland-vs-X11 detection, `/dev/uinput` access,
    the `input` group, and `pw-cat` availability on the laptop — none of it is guaranteed
    to match the desktop.
  - **Monitor preference.** `"primary"` is the right default for a single-display laptop
    and needs no special casing, but confirm the overlay lands correctly on a laptop panel
    plus an occasionally-attached external display.

---

## Progress Log

Append one row per session, before clearing context.

| Date | Task | Commit | Notes |
|---|---|---|---|
| 2026-07-25 | Plan authored | — | Baseline: `017c34e`, 62 tests green, working tree clean. Environment facts verified and recorded in the design doc. Discarded leftover debug logging in `overlay.py` from `017c34e`. |
| 2026-07-25 | 3 — initial_prompt + hotwords | (this commit) | Code + config + daemon wiring done; 72 tests green, ruff clean. Live `~/.config/blurt/config.toml` gained an `[stt]` block and the daemon was restarted. **Step 11 (dictate-and-check, incl. the silence hallucination check) is still OUTSTANDING — needs the user at the keyboard.** Task 4 step 6 measures the same thing properly. **Next: Task 4 (bench-stt), which needs fixture recordings from the user first.** |
| 2026-07-25 | 2 — WER helper | (this commit) | Done, no surprises. 68 tests green (62 -> 68), ruff clean. **Next: Task 3 (initial_prompt + hotwords).** |
| 2026-07-25 | 1 — Documentation truth-up | (this commit) | Done. Two things not in the plan: (a) the tree was not ruff-clean at baseline — 4 pre-existing F401/F841 in `whisper_bench.py`, `whisper_client.py`, `test_config.py`, `test_whisper_client.py` — fixed here so later tasks inherit a passing gate; (b) added `docs/corrections.example.yaml`, since the README told you to create `~/.config/blurt/corrections.yaml` with no example to copy. 62 tests green, ruff clean. **Next: Task 2 (WER helper).** |
