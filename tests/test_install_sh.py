"""Tests for install.sh — the macOS/Linux bootstrap.

Run in DRY_RUN mode so the script prints its plan instead of touching the
network or filesystem. We assert on the plan: uv check, tarball URL, extract
target, git init, and the setup.py command it forwards flags to.
"""

import pathlib
import subprocess

REPO = pathlib.Path(__file__).resolve().parents[1]
INSTALL_SH = REPO / "install.sh"


def run(args, env=None):
    base = {"DRY_RUN": "1", "PATH": "/usr/bin:/bin:/usr/local/bin"}
    if env:
        base.update(env)
    result = subprocess.run(
        ["bash", str(INSTALL_SH), *args],
        capture_output=True, text=True, env=base,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_default_target_is_rasa_quickstart():
    out = run([])
    assert "git init in rasa-quickstart" in out


def test_custom_target_dir():
    out = run(["myagent"])
    assert "git init in myagent" in out
    assert "extract template/ into myagent" in out


def test_forwards_ides_provider_yes():
    out = run(["--ides", "claude,cursor", "--provider", "anthropic", "--yes", "myagent"])
    assert "scripts/setup.py --ides claude,cursor --provider anthropic --yes" in out


def test_no_flags_forwards_bare_setup():
    out = run(["myagent"])
    setup_line = [l for l in out.splitlines() if "scripts/setup.py" in l][0]
    assert "--ides" not in setup_line
    assert "--provider" not in setup_line
    assert "--yes" not in setup_line


def test_default_tarball_url():
    out = run([])
    assert (
        "fetch https://github.com/rasa/rasa-quickstart/archive/refs/heads/main.tar.gz"
        in out
    )


def test_repo_and_ref_overridable():
    out = run([], env={"RASA_QUICKSTART_REPO": "me/fork", "RASA_QUICKSTART_REF": "dev"})
    assert "fetch https://github.com/me/fork/archive/refs/heads/dev.tar.gz" in out


def test_plan_mentions_uv_and_extract():
    out = run(["myagent"])
    assert "ensure uv is installed" in out
    assert "extract template/ into myagent" in out


def test_equals_style_flags():
    out = run(["--ides=vscode", "--provider=openai", "myagent"])
    assert "scripts/setup.py --ides vscode --provider openai" in out
