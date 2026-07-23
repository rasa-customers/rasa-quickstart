"""Tests for install.ps1 — the Windows (PowerShell) bootstrap.

Uses -DryRun so the script prints its plan instead of acting. Skipped if
pwsh is not available. The plan format mirrors install.sh so the bootstrap
behaves identically across platforms.
"""

import os
import pathlib
import shutil
import subprocess

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
INSTALL_PS1 = REPO / "install.ps1"

pytestmark = pytest.mark.skipif(
    shutil.which("pwsh") is None, reason="pwsh not installed"
)


def run(args, env=None):
    base = dict(os.environ)
    if env:
        base.update(env)
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(INSTALL_PS1), "-DryRun", *args],
        capture_output=True, text=True, env=base,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_default_target_is_rasa_quickstart():
    assert "git init in rasa-quickstart" in run([])


def test_custom_target_dir():
    out = run(["myagent"])
    assert "git init in myagent" in out
    assert "extract template/ into myagent" in out


def test_forwards_ides_provider_yes():
    out = run(["-Ides", "claude,cursor", "-Provider", "anthropic", "-Yes",
               "-Target", "myagent"])
    assert "scripts/setup.py --ides claude,cursor --provider anthropic --yes" in out


def test_no_flags_forwards_bare_setup():
    setup_line = [line for line in run(["myagent"]).splitlines() if "scripts/setup.py" in line][0]
    assert "--ides" not in setup_line
    assert "--provider" not in setup_line
    assert "--yes" not in setup_line


def test_default_tarball_url():
    assert (
        "fetch https://github.com/rasa-customers/rasa-quickstart/archive/refs/heads/main.tar.gz"
        in run([])
    )


def test_repo_and_ref_overridable():
    out = run([], env={"RASA_QUICKSTART_REPO": "me/fork", "RASA_QUICKSTART_REF": "dev"})
    assert "fetch https://github.com/me/fork/archive/refs/heads/dev.tar.gz" in out


def test_plan_mentions_uv_and_extract():
    out = run(["myagent"])
    assert "ensure uv is installed" in out
    assert "extract template/ into myagent" in out
