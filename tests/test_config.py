import textwrap
from pathlib import Path


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


def test_overlay_monitor_defaults_to_primary(tmp_path):
    cfg = load(tmp_path / "missing.toml")
    assert cfg.overlay.monitor == "primary"


def test_overlay_monitor_override(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text('[overlay]\nmonitor = "DP-4"\n')
    assert load(p).overlay.monitor == "DP-4"
