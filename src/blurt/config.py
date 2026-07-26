from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class WhisperConfig:
    backend: str = "wyoming"   # "wyoming" or "whisperlive"
    host: str = "localhost"
    port: int = 10300
    model: str = "small.en"    # whisperlive only
    # No-op: WhisperLive takes VAD as a server launch flag and ignores this field.
    use_vad: bool = True


@dataclass(frozen=True)
class SttConfig:
    initial_prompt: str = ""
    hotwords: str = ""


@dataclass(frozen=True)
class CleanupConfig:
    enabled: bool = True
    host: str = "localhost"
    port: int = 11434
    model: str = "qwen2.5:1.5b"
    timeout_ms: int = 500


@dataclass(frozen=True)
class HotkeyConfig:
    keycode: str = "KEY_CALC"
    device: str = "auto"


@dataclass(frozen=True)
class CorrectionsConfig:
    file: str = "~/.config/blurt/corrections.yaml"


@dataclass(frozen=True)
class TrayConfig:
    enabled: bool = True


@dataclass(frozen=True)
class OverlayConfig:
    enabled: bool = True
    position: str = "center"
    width_fraction: float = 0.75
    min_height_px: int = 200
    max_height_fraction: float = 0.33
    opacity: float = 0.85
    font: str = "monospace 22"
    monitor: str = "primary"   # "primary", an output name (e.g. "DP-4"), or "pointer"
    corner_radius: int = 14    # 0 for square corners


@dataclass(frozen=True)
class ClipboardConfig:
    tool: str = "xclip"


@dataclass(frozen=True)
class Config:
    whisper: WhisperConfig = field(default_factory=WhisperConfig)
    stt: SttConfig = field(default_factory=SttConfig)
    cleanup: CleanupConfig = field(default_factory=CleanupConfig)
    hotkey: HotkeyConfig = field(default_factory=HotkeyConfig)
    corrections: CorrectionsConfig = field(default_factory=CorrectionsConfig)
    tray: TrayConfig = field(default_factory=TrayConfig)
    overlay: OverlayConfig = field(default_factory=OverlayConfig)
    clipboard: ClipboardConfig = field(default_factory=ClipboardConfig)


DEFAULT_PATH = Path.home() / ".config" / "blurt" / "config.toml"


def load(path: Path | None = None) -> Config:
    path = path or DEFAULT_PATH
    if not path.exists():
        return Config()
    with path.open("rb") as f:
        data = tomllib.load(f)
    return Config(
        whisper=WhisperConfig(**data.get("whisper", {})),
        stt=SttConfig(**data.get("stt", {})),
        cleanup=CleanupConfig(**data.get("cleanup", {})),
        hotkey=HotkeyConfig(**data.get("hotkey", {})),
        corrections=CorrectionsConfig(**data.get("corrections", {})),
        tray=TrayConfig(**data.get("tray", {})),
        overlay=OverlayConfig(**data.get("overlay", {})),
        clipboard=ClipboardConfig(**data.get("clipboard", {})),
    )
