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
