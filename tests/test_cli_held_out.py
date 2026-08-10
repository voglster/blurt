"""Held-out test — no-subcommand still errors on missing cmd.

This ensures that adding --version did not change the existing behaviour where
running `blurt` with zero positional arguments produces an error about a
required subcommand."""

import subprocess
import sys as _sys


def test_no_subcommand_errors():
    """Running blurt without any argument must still error about missing cmd."""
    r = subprocess.run(
        [_sys.executable, "-m", "blurt"],
        capture_output=True,
        text=True,
    )
    # argparse with required=True on subparsers exits 2 for missing cmd
    assert r.returncode == 2, (
        f"expected exit 2, got {r.returncode}.\nstdout: {r.stdout}\nstderr: {r.stderr}"
    )


def test_no_subcommand_mentions_cmd():
    """The error message must reference the required 'cmd' subparser."""
    r = subprocess.run(
        [_sys.executable, "-m", "blurt"],
        capture_output=True,
        text=True,
    )
    assert "required" in r.stderr.lower(), (
        f"expected 'required' in error, got: {r.stderr}"
    )
