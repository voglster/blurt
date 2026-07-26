from blurt.cleanup_client import FALLBACK_VOCABULARY, build_system_prompt


def test_blank_vocabulary_falls_back_to_the_builtin_term_list():
    assert FALLBACK_VOCABULARY in build_system_prompt("")


def test_configured_hotwords_replace_the_builtin_term_list():
    prompt = build_system_prompt("gcloud,kubectl,Claude Code")

    assert "gcloud, kubectl, Claude Code" in prompt
    assert FALLBACK_VOCABULARY not in prompt


def test_hotword_spacing_is_normalised():
    assert "gcloud, kubectl" in build_system_prompt(" gcloud ,  kubectl ")


def test_empty_hotword_entries_are_dropped():
    assert "gcloud, kubectl" in build_system_prompt("gcloud,,kubectl,")


def test_whitespace_only_vocabulary_is_treated_as_blank():
    assert FALLBACK_VOCABULARY in build_system_prompt("  ,  ")


def test_prompt_keeps_the_do_not_paraphrase_constraint():
    assert "Do NOT paraphrase" in build_system_prompt("gcloud")
