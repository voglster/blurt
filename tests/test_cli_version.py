"""Acceptance test for the --version feature flag on blurt CLI."""

import subprocess
import sys as _sys


def test_blurt_version_exits_zero():
    """blurt --version must exit 0, not error about a missing subcommand."""
    r = subprocess.run(
        [_sys.executable, "-m", "blurt", "--version"],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, (
        f"expected exit 0, got {r.returncode}.\n"
        f"stderr: {r.stderr}"
    )


def test_blurt_version_prints_package_version():
    """blurt --version must print the version string from blurt.__version__."""
    r = subprocess.run(
        [_sys.executable, "-m", "blurt", "--version"],
        capture_output=True,
        text=True,
    )
    assert r.stdout.strip() != "", "expected non-empty stdout"
    assert r.stdout.strip().startswith("blurt "), (
        f"output should start with 'blurt ', got: {r.stdout.strip()!r}"
    )
