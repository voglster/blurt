from blurt.bench.stt_bench import resolve_prompting
from blurt.config import Config, SttConfig


def _config(initial_prompt: str = "", hotwords: str = "") -> Config:
    return Config(stt=SttConfig(initial_prompt=initial_prompt, hotwords=hotwords))


def test_defaults_to_the_users_configured_prompting():
    cfg = _config(initial_prompt="Technical dictation.", hotwords="gcloud,kubectl")

    assert resolve_prompting(None, None, False, cfg) == (
        "Technical dictation.", "gcloud,kubectl",
    )


def test_blank_config_values_become_none_rather_than_empty_strings():
    assert resolve_prompting(None, None, False, _config()) == (None, None)


def test_no_prompt_benchmarks_a_bare_baseline():
    cfg = _config(initial_prompt="Technical dictation.", hotwords="gcloud")

    assert resolve_prompting(None, None, True, cfg) == (None, None)


def test_no_prompt_overrides_explicit_flags():
    cfg = _config(hotwords="gcloud")

    assert resolve_prompting("explicit", "explicit", True, cfg) == (None, None)


def test_explicit_flags_win_over_config():
    cfg = _config(initial_prompt="from config", hotwords="from-config")

    assert resolve_prompting("from flag", "from-flag", False, cfg) == (
        "from flag", "from-flag",
    )


def test_one_explicit_flag_suppresses_config_for_both():
    """Mixing a flag with a config value would benchmark a combination the user
    never configured, which is worse than an obviously-bare run."""
    cfg = _config(initial_prompt="from config", hotwords="from-config")

    assert resolve_prompting(None, "from-flag", False, cfg) == (None, "from-flag")
