from pathlib import Path

from blurt.corrections import Corrections, load


def test_apply_simple_substitution(tmp_path: Path) -> None:
    yaml_file = tmp_path / "corrections.yaml"
    yaml_file.write_text(
        "- pattern: '(?i)git\\s*hub'\n"
        "  replacement: 'GitHub'\n"
    )
    corr = load(yaml_file)
    assert corr.apply("check the git hub repo") == "check the GitHub repo"
    assert corr.apply("Check the GITHUB repo") == "Check the GitHub repo"


def test_apply_multiple_rules(tmp_path: Path) -> None:
    yaml_file = tmp_path / "corrections.yaml"
    yaml_file.write_text(
        "- pattern: '(?i)git\\s*hub'\n"
        "  replacement: 'GitHub'\n"
        "- pattern: '(?i)cube\\s*cuttle'\n"
        "  replacement: 'kubectl'\n"
    )
    corr = load(yaml_file)
    assert corr.apply("run cube cuttle on git hub") == "run kubectl on GitHub"


def test_apply_missing_file_returns_passthrough(tmp_path: Path) -> None:
    corr = load(tmp_path / "nope.yaml")
    assert corr.apply("anything goes") == "anything goes"


def test_empty_yaml(tmp_path: Path) -> None:
    yaml_file = tmp_path / "empty.yaml"
    yaml_file.write_text("")
    corr = load(yaml_file)
    assert corr.apply("hello") == "hello"


def test_corrections_instance_directly() -> None:
    corr = Corrections([(r"foo", "bar")])
    assert corr.apply("foo baz") == "bar baz"
