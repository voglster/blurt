import textwrap
from pathlib import Path

import pytest

from blurt.config import Config, load


def test_load_minimal_config(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(
        textwrap.dedent("""
            [whisper]
            host = "llmbox"
            port = 10300

            [cleanup]
            enabled = true
            host = "llmbox"
            port = 11434
            model = "qwen2.5:1.5b"
            timeout_ms = 500

            [hotkey]
            keycode = "KEY_CALC"
            device = "auto"

            [corrections]
            file = "~/.config/blurt/corrections.yaml"

            [tray]
            enabled = true
        """)
    )

    cfg = load(cfg_file)

    assert isinstance(cfg, Config)
    assert cfg.whisper.host == "llmbox"
    assert cfg.whisper.port == 10300
    assert cfg.cleanup.enabled is True
    assert cfg.cleanup.model == "qwen2.5:1.5b"
    assert cfg.cleanup.timeout_ms == 500
    assert cfg.hotkey.keycode == "KEY_CALC"
    assert cfg.tray.enabled is True


def test_load_uses_defaults_when_file_missing(tmp_path: Path) -> None:
    missing = tmp_path / "nope.toml"
    cfg = load(missing)
    assert cfg.whisper.host == "llmbox"
    assert cfg.cleanup.timeout_ms == 500
    assert cfg.hotkey.keycode == "KEY_CALC"
