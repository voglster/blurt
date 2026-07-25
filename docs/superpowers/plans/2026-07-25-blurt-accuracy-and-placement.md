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

- [x] **Step 11: Verify end to end by hand**

```bash
systemctl --user restart blurt
journalctl --user -u blurt -f    # in another terminal
```
Dictate: "open github and run kubectl apply then check the json output". Expect `GitHub`,
`kubectl`, and `JSON` to appear correctly in the overlay *before* any corrections pass
runs. Then dictate into silence for ~3 seconds and confirm nothing spurious appears — if
prompt-adjacent words leak in, the prompt is too list-like; shorten it to one natural
sentence. Task 4 measures this properly; this step is the smoke test.

- [x] **Step 12: Commit**

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

- [x] **Step 1: Record the fixtures** — DONE 2026-07-25 via `scripts/record-fixtures.sh`

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

- [x] **Step 2: Write the bench**

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

- [x] **Step 3: Register the subcommand**

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

- [x] **Step 4: Verify the CLI wiring without touching the network**

Run: `.venv/bin/python -m blurt bench-stt --help`
Expected: usage text listing `--host`, `--port`, `--models`, `--fixtures`,
`--initial-prompt`, `--hotwords`.

- [x] **Step 5: Verify fixture discovery fails loudly**

Run: `.venv/bin/python -m blurt bench-stt --fixtures /tmp/nope`
Expected: exits with `no <name>.wav + <name>.txt pairs in /tmp/nope`.

- [x] **Step 6: Measure whether prompting actually helps** — MEASURED 2026-07-25: YES, 0.054 -> 0.000

| fixture | unprompted WER | prompted WER |
|---|---|---|
| mixed | 0.056 | **0.000** |
| prose | 0.031 | **0.000** |
| tech | 0.074 | **0.000** |
| silence | `''` | `''` |
| **mean** | **0.054** | **0.000** |

**These are the corrected numbers.** The first run of this bench scored `tech` against a
reference containing "for **a** YAML parse error". The recorded take omits the "a" — the user
confirmed by listening, and all five benchmarked models transcribed it without the article.
`tech.txt` and `script_for tech` in the recorder were corrected to match the audio, which
moved prompted `tech` from 0.036 to 0.000.

Same model (`base.en`), same fixtures. Unprompted failures were exactly the ones
`corrections.yaml` exists to patch: `kubectl` -> "cube control", `GitHub` -> "github",
`in CI` -> "NCI". Prompted, **all three scored fixtures are word-perfect**.

**The hallucination risk did not materialize**: `silence.wav` returns `''` with the prompt
active, so the design doc's main concern about `initial_prompt` is retired.

Consequence for Task 5: at 0.000 there is **no** headroom for a bigger model to win on these
fixtures, and a bigger model costs partial cadence. Do not assume the largest model wins.

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

- [x] **Step 7: Run the full suite and linter** — 81 passed, ruff clean

Run: `.venv/bin/python -m pytest -q && .venv/bin/python -m ruff check src tests`
Expected: green and clean. The bench itself has no unit tests — it is an I/O-bound
measurement tool whose only logic, WER, is tested in Task 2.

- [x] **Step 8: Commit**

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

- [x] **Step 1: Confirm the model cache is a persistent volume** — DONE 2026-07-25

Verified: named volume `whisperlive_whisperlive-cache` is mounted at `/root/.cache`, so
the HuggingFace cache (605 MB today) survives `docker rm`. Compose file lives on llmbox at
`/home/jvogel/compose/whisperlive/docker-compose.yml` and passes no server flags, so
WhisperLive's own defaults apply. **No WhisperLive or faster-whisper upgrade is needed** —
0.8.0 / 1.2.0 already support `initial_prompt`, `hotwords`, and large-v3-turbo. The only
llmbox-side change required is pulling model files (Step 2).

- [x] **Step 2: Pre-pull the candidate models** — DONE 2026-07-25

Both pulled successfully into the persistent volume; the HF cache went 605 MB -> 3.6 GB and
now holds `base.en`, `small.en`, `distil-large-v3.5-ct2`, and
`faster-whisper-large-v3-turbo-ct2`. Command used, for reference:

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

- [x] **Step 3: Verify VRAM headroom** — DONE 2026-07-25, WITH A CAVEAT

Measured 5381 / 10240 MiB used, so **only ~4.8 GB free**. The consumer is not whisperlive
(224 MiB) — it is `mimic-server` in the `mimic-tts` container, holding **4320 MiB**. Others:
`wyoming-faster-whisper` 440 MiB, coqui `tts` 372 MiB. Ollama is running but has no model
resident (`/api/ps` -> empty).

**Therefore: do NOT run Step 4 with the default four-model list in one go.** WhisperLive
instantiates a model per client connection unless started with `--single_model`, and the
compose file passes no flags, so a 4-model x 4-fixture sweep can stack model instances and
OOM the card. Run one model at a time and check VRAM between runs:

```bash
for m in base.en small.en distil-whisper/distil-large-v3.5-ct2 \
         deepdml/faster-whisper-large-v3-turbo-ct2; do
  .venv/bin/python -m blurt bench-stt --models "$m" 2>&1 | tee -a /tmp/bench-stt.txt
  ssh llmbox 'docker exec whisperlive nvidia-smi --query-gpu=memory.used --format=csv,noheader'
done
```

If a run OOMs, `docker restart whisperlive` to reclaim, and consider stopping `mimic-tts`
for the duration of the bench to free its 4.3 GB.

- [x] **Step 4: Run the bench across all four candidates** — DONE 2026-07-25, one model at a time. VRAM held flat throughout, so models did not accumulate and the OOM concern was unfounded.

Run: `.venv/bin/python -m blurt bench-stt 2>&1 | tee /tmp/bench-stt.txt`
Expected: a `mean WER` and `median final` line per model. The first connection to each
newly pulled model includes a one-time model load; if a model's first fixture looks
anomalous, re-run that model alone.

- [x] **Step 5: Pick the winner and record the evidence** — WINNER: `base.en`, unchanged

Scored on tail latency (`final_ms - audio_duration`), not raw `final_ms`, which includes the
fixture's real-time playback. All rows prompted except the first. WER uses the corrected
`tech` reference.

| run | mean WER | tail p50 | partials/s | on disk | silence |
|---|---|---|---|---|---|
| base.en unprompted | 0.054 | 1531 ms | 4.2 | 141 MB | clean |
| **base.en prompted** | **0.000** | **1483 ms** | **3.7** | **141 MB** | clean |
| small.en | 0.000 | 1766 ms | 3.7 | 464 MB | clean |
| distil-large-v3.5-ct2 | 0.025 | 2698 ms | 3.7 | 1.5 GB | clean |
| large-v3-turbo-ct2 | 0.000 | 2186 ms | 2.9 | 1.6 GB | clean |

Three models tie at word-perfect, so **accuracy cannot pick a winner here**. `base.en` wins on
the axes that still discriminate: the best tail latency, the most partials per second, and a
model 11x smaller than turbo. **The model does not change.** The accuracy win came entirely
from Task 3's prompting, not from model size.

**This overturns the original ranking**, which put the model upgrade at #2 and prompting at #3.
Recorded so nobody re-litigates it: bigger was not better here.

**Read this bench honestly — it is saturated.** Three-way perfection means zero resolving
power. The conditions were quiet room (room tone peak 180), close-miked Fifine, native accent,
*read* speech, and technical vocabulary pre-declared in the prompt. That is exactly the regime
where base.en's weaknesses do not surface. Published WER on LibriSpeech shows what is being
given up as conditions get harder:

| model | params | test-clean | test-other (hard) |
|---|---|---|---|
| base.en | 74M | 4.2% | **10.2%** |
| small.en | 244M | 3.1% | 7.4% |
| large-v3 (turbo shares the encoder) | 809M | 2.7% | **5.2%** |

Roughly a 2x gap on hard audio, a modest one on clean. Where the bigger models win, per the
literature: noisy environments (small models degrade faster; large-v3 was trained on noisier
samples), accented speech, rare proper nouns, and long or disfluent speech. Note that the
documented mitigation for the proper-noun case is precisely `initial_prompt` + `hotwords`,
which is already deployed — so much of that particular gap is already bought.

Counterpoint against reaching for turbo by default: it is reported to hallucinate *more* than
full large-v3 on very short clips and noisy recordings, and dictation is short clips.

`distil-large-v3.5` losing at 0.025 is documented behavior, not a fluke: distil-whisper states
`initial_prompt` has little effect on it, because distil-large-v3 was trained with prompt
conditioning on only 50% of samples. Its `tech` WER of 0.074 exactly equals base.en
**unprompted**. Do not use a distil model while prompting is load-bearing.

Sources: Whisper paper (arxiv 2212.04356), huggingface/distil-whisper issue #20.

**Implication for the laptop (Phase 2):** offsite means cafes, hotel wifi and ambient noise —
the exact conditions where base.en gives up the most. The laptop may want a different model
than the desktop, which strengthens the per-host config-divergence question.

**Prompt-sensitivity matrix (added 2026-07-25, after the first sweep proved confounded).**
The original sweep gave every model the same 14-term prompt, so it measured models *given one
prompt* rather than model robustness. Re-run as 3 models x 3 prompt variants x 2 fixtures
(WER / partial count; TRUNC = silently stopped transcribing mid-utterance):

| model | LONG prompt (14 terms) | SHORT prompt (5 terms) | no prompt |
|---|---|---|---|
| **base.en** | 0.000 / 43p, 45p | 0.000 / 40p, 39p | 0.056, 0.074 / 51p, 52p |
| small.en | 0.000 / 41p, 39p | **0.694 TRUNC**, 0.000 | 0.028, 0.000 / 43p, 50p |
| large-v3-turbo | 0.000 / 31p, 35p | 0.000 / 32p, 38p | **0.000 / 28p, 34p** |

**`small.en` is disqualified.** With the 5-term prompt it truncates `mixed.wav` to just its
first sentence — 20 partials instead of 43, two-thirds of the words gone, no error raised.
Reproduced 5/5, fully deterministic. `mixed.wav`'s first sentence ends in a question mark and
small.en treats that as end-of-utterance; the longer prompt happens to suppress it. Note this
is **non-monotonic** — it fails with the short prompt but is fine with the long prompt *and*
with no prompt at all, so there is no "shorter is safer" rule to reason with.

Ruled out as the cause: blurt's own finalization. Raising `QUIET_GAP_SECONDS` from 0.5 to 1.5
to 3.0 changed nothing (still ~20 partials), so this is server/model-side, not the client
declaring final too early.

**`large-v3-turbo` is the accuracy/robustness winner** — 0.000 on every variant including no
prompt, the only model that does not need prompting at all. It still loses for the desktop:
zero measured accuracy gain over base.en *in the configuration actually deployed*, against
~25% fewer partials (2.8/s vs 3.9/s), 1.6 GB vs 141 MB, and roughly double the VRAM. It is
also reported to hallucinate more on very short clips, which is untested here — the fixtures
are 10-12 s while real dictation is often 2-5 s.

**Decision: stay on `base.en` + the long prompt.** It is 0.000 in the deployed config, has the
best partial cadence (which is what makes the overlay feel live), and degrades *gracefully*
(0.056) rather than truncating when prompting weakens.

**Switch to turbo when either becomes true:**
1. **Laptop / offsite use** — ambient noise is where base.en's hard-audio gap (10.2% vs 5.2%)
   bites, and turbo needs no per-environment prompt tuning.
2. **Correction-capture ships** — once something auto-edits `hotwords`/`initial_prompt`,
   base.en's accuracy is coupled to an input this matrix proves can fail catastrophically.
   Turbo's prompt-independence stops being a luxury at that point.

**Measured VRAM footprint** (peak while decoding minus an idle server at 827 MiB):
`base.en` 527 MiB, `small.en` 975 MiB. On disk: base.en 141 MB, small.en 464 MB,
distil-large-v3.5 1.5 GB, large-v3-turbo 1.6 GB.

**DECISION REVERSED 2026-07-25, same day: switched to `large-v3-turbo`.**

The "stay on base.en" conclusion above rested on an untested assumption — that base.en
"degrades gracefully" — when every measurement had been taken in a silent room with a
close-miked Fifine. Challenged on that, the missing experiments were run: the real
recordings noise-augmented at 20/10/5 dB SNR, and cut to 2.6-3.0 s clips (the length real
dictation actually is, versus the 10-12 s fixtures).

| SNR | base.en | large-v3-turbo |
|---|---|---|
| tech @ 20 dB | 0.000 | 0.000 |
| tech @ 10 dB | 0.037 | **0.000** |
| tech @ 5 dB | 0.111 | **0.000** |
| mixed @ 20 dB | 0.000 | 0.000 |
| mixed @ 10 dB | 0.000 | 0.000 |
| mixed @ 5 dB | 0.167 | **0.083** |

base.en degrades monotonically with noise; turbo holds at 0.000 until 5 dB and is still half
the error rate there. **The graceful-degradation advantage belongs to turbo, the opposite of
what was claimed.** The published LibriSpeech gap (10.2% vs 5.2% on test-other) reproduces on
this user's own voice — it simply cannot surface in a quiet room.

Short clips (2.6-3.0 s, clean and at 10 dB): **turbo produced no hallucination**, transcribing
all three identically to base.en. That was the single documented argument against turbo and it
did not reproduce.

Measured costs of turbo: **~800 ms slower to first partial** (≈2.2 s vs ≈1.3 s, the only cost
that is felt), **~2543 MiB VRAM while a session is active** vs base.en's 463 MiB — released
when the session ends, so it contends with mimic-tts's 4.3 GB only during actual dictation —
and 1.6 GB on disk vs 141 MB.

Applied to `~/.config/blurt/config.toml` and verified: 0.000 on all clean fixtures, silence
still clean. Reverting is one config line; the user explicitly framed this as a two-way door.

**Process lesson, the important one:** the clean-room bench was not merely saturated, it was
*misleading*. Three models tied at 0.000 and the tie was broken on latency — a conclusion that
inverted as soon as the audio got hard. When a bench saturates, that is a signal the test
conditions are wrong, not a signal to break the tie on a secondary axis.

**If this bench is ever to rank models again it needs harder fixtures**: background noise,
faster speech, longer utterances, disfluencies, and vocabulary deliberately left out of the
prompt.

Selection rule: the lowest mean WER whose **median final** stays under 1500 ms and which
still produces multiple partials per fixture — sparse partials mean the live overlay
stops feeling live, which is blurt's main advantage over the OSW clones.

Paste the bench table into the Progress Log along with the chosen model and the reasoning.

- [x] **Step 6: Apply the winner** — set to `deepdml/faster-whisper-large-v3-turbo-ct2` after the decision reversal below (was briefly a no-op on `base.en`). `~/.config/blurt/config.toml` already had `model = "base.en"`, which is the measured winner. Confirmed live end-to-end after the fixture correction: mean WER 0.000 with `silence` still clean. Daemon left running.

Set `[whisper] model` in `~/.config/blurt/config.toml` to the winner, then:

```bash
systemctl --user restart blurt
```
Dictate three real sentences containing technical terms and confirm the overlay still
fills in while you speak. If partials feel noticeably sparser than before, revert the one
config line and pick the runner-up.

- [x] **Step 7: Update docs with the measured result** — README gained a "Model selection" section with the measured table, the `small.en` truncation warning, and the turbo-for-noisy-conditions note.

Update `docs/config.example.toml`'s `model` line to the winner, and add a short "Model
selection" section to the README naming the winner, its mean WER, its median final
latency, and the date measured — so the next reader does not re-litigate it.

- [x] **Step 8: Commit**

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

- [x] **Step 1: Write the failing tests for detailed monitor parsing**

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

- [x] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_overlay_monitor.py -q`
Expected: FAIL — `AttributeError: module 'blurt.overlay' has no attribute '_parse_listmonitors'`

- [x] **Step 3: Implement parsing**

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

- [x] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_overlay_monitor.py -q`
Expected: PASS, including the six pre-existing tests in that file.

- [x] **Step 5: Write the failing tests for preference-based resolution**

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

- [x] **Step 6: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_overlay_monitor.py -q`
Expected: FAIL — `_resolve_monitor() got an unexpected keyword argument 'preference'`

- [x] **Step 7: Implement preference-based resolution**

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

- [x] **Step 8: Run the full overlay monitor suite**

Run: `.venv/bin/python -m pytest tests/test_overlay_monitor.py -q`
Expected: PASS, including the updated pre-existing five.

- [x] **Step 9: Write the failing config test**

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

- [x] **Step 10: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_config.py -q`
Expected: FAIL — `AttributeError: 'OverlayConfig' object has no attribute 'monitor'`

- [x] **Step 11: Add the config key and wire it through**

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

- [x] **Step 12: Run the full suite and linter**

Run: `.venv/bin/python -m pytest -q && .venv/bin/python -m ruff check src tests`
Expected: all tests pass, ruff clean.

- [x] **Step 13: Verify against the real display**

Run: `.venv/bin/python -c "from blurt import overlay; print(overlay._list_monitors_detailed()); print(overlay._resolve_monitor(None))"`
Expected: three `MonitorInfo` rows with `DP-4` flagged `primary=True`, and the resolved
rect `(2560, 0, 2560, 1440)`.

- [x] **Step 14: Verify end to end** — CONFIRMED by user 2026-07-25

```bash
systemctl --user restart blurt
```
Then dictate three times, with the mouse parked on a different monitor each time. The
overlay must appear on DP-4 all three times.

- [x] **Step 15: Commit**

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

- **Fix `aclose(): asynchronous generator is already running` on session teardown
  (found 2026-07-25 during the bench).** Every WhisperLive session ends with this
  RuntimeError on stderr:

  ```
  an error occurred during closing of asynchronous generator
    <async_generator object Connection.send_context ...>
  RuntimeError: aclose(): asynchronous generator is already running
  ```

  Cause: `WhisperLiveServer.stream()`'s `finally` block cancels `send_task` while that task
  is suspended inside `ws.send(...)`, i.e. inside websockets' `send_context` async generator.
  Cancelling mid-yield leaves the generator un-closeable, and the event loop complains when it
  is finalized. It fires on every production dictate-and-commit too, not just in the bench —
  results are unaffected, which is exactly why it went unnoticed.

  Likely fix: signal the sender to stop cooperatively (an `asyncio.Event` the `async for`
  checks) and `await` it with a timeout, instead of `send_task.cancel()`. Verify by running
  `blurt bench-stt --models base.en` and confirming clean stderr.

- **Rework the bench's latency metric (found 2026-07-25).** `Result.final_ms` times from
  stream start, so it includes the fixture's full real-time playback — a 10.88 s clip reporting
  `final=12420ms` actually means a 1.54 s tail. Report `final_ms - audio_duration_ms` instead,
  and add the age of the last partial at commit time, which is what blurt's UX actually depends
  on: `Daemon._finalize` snapshots the overlay text and never waits for the official final.
  Task 5's "median final under 1500 ms" selection rule is meaningless until this is fixed.

- **Time-to-first-partial has an architectural floor of ~1s, and blurt is already on it
  (established 2026-07-25).** After pinning the model server-side, first partial dropped to a
  flat ~1.1s — and the user reported **no perceptible difference** in live dictation. That is
  the correct outcome to expect, for a measurable reason: base.en (74M params) and
  large-v3-turbo (809M) both reach first partial at ~1.1s once resident. An 11x parameter gap
  producing identical latency proves inference is not the limiter. WhisperLive's STT loop does
  not process audio until >=1s is buffered (noted in `WhisperLiveServer`'s docstring), so ~1s
  is a floor no model choice can beat.

  **Do not attempt to improve perceived dictation latency by changing models.** If it is ever
  worth attacking, the remaining costs are, in rough order:
  1. The server-side >=1s buffer. Not client-configurable; needs a change inside the
     WhisperLive container.
  2. Session startup on the critical path — `AudioCapture.start()` spawns a `pw-cat`
     subprocess and `_resolve_monitor` shells out to `xrandr` on every dictate. A persistent
     WebSocket and/or a long-lived capture process would move the handshake off the hot path.
  3. Human timing, which dominates all of the above and cannot be optimised.

  Measure before touching any of it: instrument from keypress to first overlay text, which is
  the number the user actually experiences. `bench-stt` measures from stream start and so
  misses items 2 and 3 entirely.

- **Hotword bleed is real, and the guard caught it (2026-07-25).** Live tuning of the user's
  vocabulary produced a concrete instance of the over-biasing risk. Growing `hotwords` from 12
  to 29 terms — adding `Claude`, `Claude Code`, `Sherpa`, `FleetView`, `PyPI` and others —
  regressed the bench from 0.000 to 0.009, because with both `TypeScript` and `JavaScript`
  boosted the model **inserted a word that was never spoken**:

  ```
  REF: ... The TypeScript types were wrong ...
  HYP: ... The TypeScript. JavaScript types were wrong ...
  ```

  Trimming to 18 terms — only those actually observed to mis-transcribe — restored 0.000.

  **The rule this establishes:** `initial_prompt` is soft context and can be generous;
  `hotwords` are hard token boosts and must be restricted to terms that demonstrably fail.
  Terms that already transcribe correctly cost accuracy when boosted, for no benefit. This is
  exactly the failure mode the correction-capture feature would cause if it appended terms
  without measuring, and it validates making a `bench-stt` re-run mandatory before persisting
  any prompt or hotword change.

  Also note `Claude` and `cloud` are near-homophones and both are in this user's vocabulary, so
  the prompt names both in natural context rather than boosting only one.

- ~~**Pin the model server-side to recover first-partial latency (2026-07-25).**~~ **DONE 2026-07-25.** Added `command: python run_server.py -fw deepdml/faster-whisper-large-v3-turbo-ct2` to llmbox's compose (original backed up as `docker-compose.yml.bak-2026-07-25`). Server logs `Custom model option was provided. Switching to single model mode.` and `Loading model:` now appears **once ever** instead of once per dictation. First partial went from 1642/1799/2138 ms to a flat **1087/1102/1106 ms** — the variance *was* the model load. This is faster than base.en ever managed (1189-1434 ms), so turbo's only real drawback is gone. Caveat: `-fw` overrides the client's requested model, so blurt's `[whisper] model` is now advisory and model changes happen in the compose file. Original note follows for context: The whisperlive
  logs show `INFO:root:Loading model:` once **per connection** — a fresh model instance for
  every dictation session, because `single_model` mode only applies to a server-side custom
  model path and blurt passes the repo id per-client. With a 1.6 GB model that load is part of
  the ~800 ms first-partial cost. Launching the container with
  `-fw <path-to-turbo> --single_model` should pin one instance and reuse it. This is an llmbox
  compose change (`/home/jvogel/compose/whisperlive/docker-compose.yml`), not a blurt change,
  and it would make turbo's main drawback largely disappear. Measure first-partial before and
  after with `bench-stt`.

- **Correction capture / hotword feedback loop (user request, 2026-07-25).** When blurt
  mis-transcribes a term there is currently no way to tell it so — you have to remember the
  term, open `~/.config/blurt/config.toml`, edit `[stt] hotwords` by hand, and restart the
  daemon. Nothing captures the failure at the moment you notice it, which is the only moment
  you actually have the wrong-vs-right pair in front of you.

  Worth designing properly rather than guessing, but the shape of the problem:
  - **Capture.** The overlay already holds the raw transcript, and `_last_text` survives the
    session. An overlay-time key (alongside the existing Enter / Esc / C) could mark "this was
    wrong" and stash the raw text for later correction. Alternatively a `blurt fix` CLI that
    operates on the last transcript, or a tray menu entry.
  - **Diff.** Given the wrong text and the intended text, the terms that changed can be derived
    rather than typed — `wer.py`'s word-level edit distance (Task 2) already computes exactly
    the substitution pairs needed, so the alignment work is largely done.
  - **Apply.** Decide where a learned term lands: `[stt] hotwords` (decode-time, needs a daemon
    restart to take effect), `initial_prompt` (same), or `corrections.yaml` (post-hoc, but
    reloadable without a restart and deterministic). Probably hotwords for real words and
    corrections.yaml for homophone-style mangles like "cube cuttle".
  - **Reload.** Any of these is useless if it needs a manual `systemctl --user restart blurt`.
    Watching the config/corrections files and reloading in place is likely a prerequisite.
  - **Guard.** An unbounded auto-grown hotword list will eventually hurt accuracy — faster-whisper
    biases toward every term given. Needs a cap, or a usage count, or a review step.
  - **Guard, the serious one.** The 2026-07-25 prompt-sensitivity matrix showed that changing
    the prompt can make a model **silently truncate** an utterance (`small.en` dropped two
    thirds of a sentence with a shorter prompt, deterministically, and non-monotonically — long
    and empty prompts were both fine). So mutating `initial_prompt`/`hotwords` automatically is
    not a safe operation. Any auto-tuning MUST re-run `bench-stt` against the fixtures after a
    change and refuse to persist a prompt that regresses WER or partial count. A truncation
    guard in `WhisperLiveServer` — flag a final that arrives with suspiciously few partials for
    the audio duration — would also catch this class of failure in production.

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
| 2026-07-25 | Live tuning on turbo | (this commit) | Confirmed from whisperlive logs that turbo is genuinely loaded (`models--deepdml--...`), not silently falling back. User reported the trailing-artifact annoyances are gone. Live dictation exposed missing vocabulary (`Claude Code` came out as "CloudCode"); expanded hotwords 12 -> 29, which **regressed the bench 0.000 -> 0.009 via hotword bleed** (boosting both TypeScript and JavaScript made the model insert an unspoken "JavaScript"). Trimmed to 18 demonstrated-failure terms, back to 0.000, applied and restarted. Rule: generous prompt, lean hotwords. Also found whisperlive reloads the model per connection — pinning it server-side should recover much of turbo's first-partial cost. |
| 2026-07-25 | 5 — model choice REVISED | (this commit) | **Switched to `large-v3-turbo`.** The earlier "keep base.en" call rested on an untested claim that base.en degrades gracefully; all measurements had been in a silent room. Noise-augmenting the real recordings (20/10/5 dB SNR) showed base.en degrading monotonically while turbo held at 0.000 until 5 dB — the graceful-degradation advantage is turbo's, the opposite of what I wrote. Short clips (2.6-3.0 s) showed no turbo hallucination, killing the one argument against it. Costs measured: ~800 ms slower first partial, 2543 MiB VRAM while active (released after, so it only contends with mimic-tts during dictation). Verified 0.000 on clean fixtures after switching. **Lesson: a saturated bench means the test conditions are wrong, not that the tie should be broken on a secondary axis.** |
| 2026-07-25 | 5 — model choice COMPLETE | (this commit) | **Winner: `base.en`, unchanged.** Prompting was the whole win (0.054 -> 0.000); no larger model beat it. `small.en` disqualified for deterministic silent truncation under a shorter prompt. `large-v3-turbo` is the robustness winner (0.000 even unprompted) but costs ~25% partial cadence for zero measured gain in the deployed config — flagged as the right choice for the laptop and for after correction-capture ships. Measured VRAM: base.en 527 MiB, small.en 975 MiB (idle server 827 MiB). **Two process lessons: (1) my first sweep was confounded — one shared prompt across all models measured 'models given this prompt', not the models; (2) I over-ticked checkboxes with a positional script and had to un-tick Task 5 steps 5-8. Tick deliberately, not positionally.** |
| 2026-07-25 | 4 — fixtures recorded | (this commit) | User recorded all four takes; all validate at 16 kHz/mono/s16. Durations 10.0-12.2 s, `silence.wav` peak 180 (genuinely quiet, so it is a real hallucination check). **Levels are lowish** — peak 4274-6062, RMS 336-599; `prose.wav` only just cleared the recorder's 4000 floor. If WER is poor across *every* model, suspect mic gain before the models. 1.3 MB committed. |
| 2026-07-25 | Recorder + user verification | (this commit) | Added `scripts/record-fixtures.sh`: Enter/speak/Enter with re-record, targets the FIFINE by node name, and validates format + level + duration per take (room tone measured at peak ~950, so the speech floor is 4000). Gotcha found: `pw-cat --record` ignores SIGINT *and* SIGTERM, so stopping escalates to SIGKILL — safe because the WAV frame count stays patched as it writes. Launched in tmux session `blurt-fixtures`. User confirmed overlay-on-primary works (Task 6 Step 14) and that GitHub/JSON/kubectl now transcribe correctly (Task 3 Step 11) — both ticked. New Phase 2 item recorded: correction-capture / hotword feedback loop. |
| 2026-07-25 | 5 — model choice (steps 1-3) | (this commit) | llmbox prep done, no reboot needed for it. **No WhisperLive/faster-whisper upgrade required** — 0.8.0 / 1.2.0 already support everything. Both candidate models pulled (cache 605 MB -> 3.6 GB, persistent volume). **Caveat found: only ~4.8 GB VRAM free** — `mimic-server` in `mimic-tts` holds 4320 MiB of the 10240 MiB card, whisperlive only 224 MiB. Step 4 must run one model at a time; details in the step. Separately, llmbox's host `nvidia-smi` is broken (loaded module 580.159.03 vs built/userspace 580.173.02 — driver upgraded without a module reload); containers unaffected, fix is a reboot, walked the user through it. **Steps 4-8 OUTSTANDING — need fixtures from Task 4 Step 1 first.** |
| 2026-07-25 | 6 — overlay monitor pinning | (this commit) | Done. 81 tests green, ruff clean. On the real display `preference="primary"` resolves DP-4 (x=2560) while `preference="pointer"` resolves DP-9 (x=5120) — a live demonstration of the stale-pointer bug and the fix. Rewrote `test_overlay_monitor.py` around `MonitorInfo`; note one pre-existing test (`falls_back_to_first_when_no_signal`) had been passing by accident because `MONS[0]` happened to equal DP-4's rect. Live config gained an explicit `[overlay] monitor = "primary"`. **Step 14 (dictate from 3 monitors) OUTSTANDING — needs the user.** |
| 2026-07-25 | 4 — bench-stt (code only) | (this commit) | Bench + CLI written. Found and fixed a latent CLI bug: bench subcommands were registered with no flags, so `blurt bench-cleanup --models x` (and `bench-whisper --wav`) died at the outer parser — every bench main now takes `argv` and the outer parser forwards unrecognized args, with `add_help=False` so `--help` reaches the real parser. **Steps 1 and 6 OUTSTANDING — need the user to record `tests/fixtures/*.wav`.** Also confirmed llmbox's HF cache is the persistent named volume `whisperlive_whisperlive-cache` (Task 5 Step 1 done early). **Next: Task 6 (overlay pinning), which needs nobody.** |
| 2026-07-25 | 3 — initial_prompt + hotwords | (this commit) | Code + config + daemon wiring done; 72 tests green, ruff clean. Live `~/.config/blurt/config.toml` gained an `[stt]` block and the daemon was restarted. **Step 11 (dictate-and-check, incl. the silence hallucination check) is still OUTSTANDING — needs the user at the keyboard.** Task 4 step 6 measures the same thing properly. **Next: Task 4 (bench-stt), which needs fixture recordings from the user first.** |
| 2026-07-25 | 2 — WER helper | (this commit) | Done, no surprises. 68 tests green (62 -> 68), ruff clean. **Next: Task 3 (initial_prompt + hotwords).** |
| 2026-07-25 | 1 — Documentation truth-up | (this commit) | Done. Two things not in the plan: (a) the tree was not ruff-clean at baseline — 4 pre-existing F401/F841 in `whisper_bench.py`, `whisper_client.py`, `test_config.py`, `test_whisper_client.py` — fixed here so later tasks inherit a passing gate; (b) added `docs/corrections.example.yaml`, since the README told you to create `~/.config/blurt/corrections.yaml` with no example to copy. 62 tests green, ruff clean. **Next: Task 2 (WER helper).** |
