from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class WhisperConfig:
    backend: str = "wyoming"   # "wyoming" or "whisperlive"
    host: str = "llmbox"
    port: int = 10300
    model: str = "small.en"    # whisperlive only
    use_vad: bool = True       # whisperlive only


@dataclass(frozen=True)
class CleanupConfig:
    enabled: bool = True
    host: str = "llmbox"
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
    position: str = "bottom-center"
    width_fraction: float = 0.6
    min_height_px: int = 120
    max_height_fraction: float = 0.33
    opacity: float = 0.85
    font: str = "monospace 18"


@dataclass(frozen=True)
class ClipboardConfig:
    tool: str = "xclip"


@dataclass(frozen=True)
class Config:
    whisper: WhisperConfig = field(default_factory=WhisperConfig)
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
        cleanup=CleanupConfig(**data.get("cleanup", {})),
        hotkey=HotkeyConfig(**data.get("hotkey", {})),
        corrections=CorrectionsConfig(**data.get("corrections", {})),
        tray=TrayConfig(**data.get("tray", {})),
        overlay=OverlayConfig(**data.get("overlay", {})),
        clipboard=ClipboardConfig(**data.get("clipboard", {})),
    )
