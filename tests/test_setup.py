"""Unit tests for template/scripts/setup.py.

These live at the repo root (maintainer-only) and are never delivered to a
developer's machine. They exercise the pure logic of the setup script; the
subprocess steps (uv sync, rasa ...) are verified by an end-to-end run.
"""

import pathlib
import sys

import pytest
from ruamel.yaml import YAML

SETUP_DIR = pathlib.Path(__file__).resolve().parents[1] / "template" / "scripts"
sys.path.insert(0, str(SETUP_DIR))

import setup  # noqa: E402

_yaml = YAML()


def _load(text):
    from io import StringIO

    return _yaml.load(StringIO(text))


# --- integrations.yml fixture mirroring the 3.20 Mantle scaffold -----------

INTEGRATIONS_YML = """\
# External integrations for your Mantle agent.

llm:
  model_group: orchestrator

model_groups:
  - id: orchestrator
    models:
      - provider: openai
        model: gpt-5.2
        api_key_env: OPENAI_API_KEY

channels:
  rest:
    enabled: true
  inspector:
    enabled: true
"""

TEMPLATE_DIR = pathlib.Path(__file__).resolve().parents[1] / "template"


# --- parse_args --------------------------------------------------------------

def test_parse_args_defaults():
    args = setup.parse_args([])
    assert args.provider == "openai"
    assert args.ides is None
    assert args.yes is False
    assert args.project_path == "."


def test_parse_args_values():
    args = setup.parse_args(
        ["--ides", "claude,cursor", "--provider", "anthropic", "--yes"]
    )
    assert args.ides == "claude,cursor"
    assert args.provider == "anthropic"
    assert args.yes is True


def test_parse_args_rejects_unknown_provider():
    with pytest.raises(SystemExit):
        setup.parse_args(["--provider", "gemini"])


def test_setup_source_is_ascii():
    # Windows consoles default to cp1252; non-ASCII in printed output crashes
    # there with UnicodeEncodeError. Keep the script ASCII-only.
    src = pathlib.Path(setup.__file__).read_text(encoding="utf-8")
    src.encode("ascii")


def test_parse_args_skip_train_default_false():
    assert setup.parse_args([]).skip_train is False


def test_parse_args_skip_train_flag():
    assert setup.parse_args(["--skip-train"]).skip_train is True


def test_parse_args_skills_only_flag():
    assert setup.parse_args([]).skills_only is False
    assert setup.parse_args(["--skills-only"]).skills_only is True


# --- parse_ides / validate_ides ---------------------------------------------

def test_parse_ides_normalizes():
    assert setup.parse_ides("claude, Cursor ,,") == ["claude", "cursor"]


def test_parse_ides_empty():
    assert setup.parse_ides("") == []


def test_validate_ides_ok():
    setup.validate_ides(["claude", "vscode"])  # no raise


def test_validate_ides_rejects_unknown():
    with pytest.raises(ValueError) as exc:
        setup.validate_ides(["emacs"])
    assert "emacs" in str(exc.value)


# --- detect_ides -------------------------------------------------------------

def test_detect_ides_by_command():
    which = lambda c: "/usr/bin/cursor" if c == "cursor" else None
    exists = lambda p: False
    assert setup.detect_ides(which=which, exists=exists) == ["cursor"]


def test_detect_ides_by_path():
    which = lambda c: None
    exists = lambda p: str(p).endswith(".claude")
    assert setup.detect_ides(which=which, exists=exists) == ["claude"]


def test_detect_ides_none():
    assert setup.detect_ides(which=lambda c: None, exists=lambda p: False) == []


# --- resolve_ides ------------------------------------------------------------

def _no_prompt(default):
    raise AssertionError("prompt should not be called")


def test_resolve_ides_flag_wins_without_prompt():
    assert setup.resolve_ides("vscode", ["claude"], False, _no_prompt) == ["vscode"]


def test_resolve_ides_flag_invalid_raises():
    with pytest.raises(ValueError):
        setup.resolve_ides("emacs", [], True, _no_prompt)


def test_resolve_ides_yes_uses_detected():
    assert setup.resolve_ides(None, ["cursor"], True, _no_prompt) == ["cursor"]


def test_resolve_ides_yes_falls_back_to_default():
    assert setup.resolve_ides(None, [], True, _no_prompt) == setup.DEFAULT_IDES


def test_resolve_ides_prompt_empty_uses_default():
    assert setup.resolve_ides(None, ["cursor"], False, lambda d: "") == ["cursor"]


def test_resolve_ides_prompt_parses_response():
    got = setup.resolve_ides(None, [], False, lambda d: "vscode, claude")
    assert got == ["vscode", "claude"]


def _eof_prompt(default):
    # Simulates `curl | bash`: no readable terminal, input() raises EOFError.
    raise EOFError


def test_resolve_ides_prompt_eof_falls_back_to_detected():
    assert setup.resolve_ides(None, ["cursor"], False, _eof_prompt) == ["cursor"]


def test_resolve_ides_prompt_eof_no_detected_uses_default():
    assert setup.resolve_ides(None, [], False, _eof_prompt) == setup.DEFAULT_IDES


# --- ensure_env --------------------------------------------------------------

def test_ensure_env_creates_from_example(tmp_path):
    (tmp_path / ".env.example").write_text("RASA_LICENSE=\nOPENAI_API_KEY=\n")
    created, missing = setup.ensure_env(
        str(tmp_path), ["RASA_LICENSE", "OPENAI_API_KEY"], environ={}
    )
    assert created is True
    assert (tmp_path / ".env").exists()
    assert missing == ["RASA_LICENSE", "OPENAI_API_KEY"]


def test_ensure_env_existing_is_untouched(tmp_path):
    (tmp_path / ".env.example").write_text("RASA_LICENSE=\n")
    (tmp_path / ".env").write_text("RASA_LICENSE=abc\nOPENAI_API_KEY=xyz\n")
    created, missing = setup.ensure_env(
        str(tmp_path), ["RASA_LICENSE", "OPENAI_API_KEY"], environ={}
    )
    assert created is False
    assert missing == []
    assert (tmp_path / ".env").read_text() == "RASA_LICENSE=abc\nOPENAI_API_KEY=xyz\n"


def test_ensure_env_reports_absent_and_empty_keys(tmp_path):
    (tmp_path / ".env.example").write_text("RASA_LICENSE=\n")
    (tmp_path / ".env").write_text("RASA_LICENSE=abc\nOPENAI_API_KEY=\n")
    _, missing = setup.ensure_env(
        str(tmp_path), ["RASA_LICENSE", "OPENAI_API_KEY", "OTHER"], environ={}
    )
    assert missing == ["OPENAI_API_KEY", "OTHER"]


def test_ensure_env_environment_variable_counts_as_set(tmp_path):
    # CI passes RASA_LICENSE as an env var instead of writing it to .env.
    (tmp_path / ".env.example").write_text("RASA_LICENSE=\n")
    _, missing = setup.ensure_env(
        str(tmp_path), ["RASA_LICENSE"], environ={"RASA_LICENSE": "abc"}
    )
    assert missing == []


def test_license_banner_is_actionable():
    assert setup.LICENSE_URL in setup.LICENSE_BANNER
    assert "RASA_LICENSE" in setup.LICENSE_BANNER
    assert "make setup" in setup.LICENSE_BANNER


def test_ensure_env_without_example_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        setup.ensure_env(str(tmp_path), ["RASA_LICENSE"], environ={})


# --- provider helpers --------------------------------------------------------

def test_provider_env_key():
    assert setup.provider_env_key("openai") == "OPENAI_API_KEY"
    assert setup.provider_env_key("anthropic") == "ANTHROPIC_API_KEY"


# --- command builders --------------------------------------------------------

def test_child_env_forces_utf8():
    # Rasa prints Unicode via rich; Windows' default cp1252 console crashes.
    env = setup.child_env()
    assert env["PYTHONUTF8"] == "1"
    assert env["PYTHONIOENCODING"] == "utf-8"


def test_uv_sync_command():
    assert setup.uv_sync_command() == ["uv", "sync"]


def test_mcp_command_joins_ides():
    assert setup.mcp_command(["claude", "cursor"]) == [
        "uv", "run", "rasa", "tools", "init", "--yes",
        "--ides", "claude,cursor",
    ]


def test_skills_command_installs_mantle_skills():
    assert setup.skills_command(["claude", "cursor"]) == [
        "uv", "run", "rasa", "skills", "install", "mantle", "--yes",
        "--ides", "claude,cursor",
    ]


def test_docs_command_fetches_mantle_docs():
    assert setup.docs_command() == [
        "uv", "run", "rasa", "tools", "init", "docs", "mantle", "--yes",
    ]


def test_coding_agent_commands_order():
    # MCP first: `rasa tools init` (re)writes .rasa/, docs land beneath it.
    cmds = setup.coding_agent_commands(["claude"])
    assert cmds == [
        setup.mcp_command(["claude"]),
        setup.skills_command(["claude"]),
        setup.docs_command(),
    ]


def test_train_command():
    assert setup.train_command() == ["uv", "run", "rasa", "train"]


# --- provider config rewrite -------------------------------------------------

def test_openai_preset_matches_template():
    # apply_provider() skips the rewrite for openai, so the shipped scaffold
    # must already be what the openai preset describes.
    data = _load((TEMPLATE_DIR / "integrations.yml").read_text())
    group_id = data["llm"]["model_group"]
    group = next(g for g in data["model_groups"] if g["id"] == group_id)
    assert [dict(m) for m in group["models"]] == (
        setup.PROVIDER_PRESETS["openai"]["models"]
    )


def test_set_orchestrator_models_anthropic():
    out = setup.set_orchestrator_models(INTEGRATIONS_YML, "anthropic")
    data = _load(out)
    assert data["llm"]["model_group"] == "orchestrator"
    group = data["model_groups"][0]
    assert group["id"] == "orchestrator"
    assert group["models"][0]["provider"] == "anthropic"
    assert group["models"][0]["api_key_env"] == "ANTHROPIC_API_KEY"


def test_set_orchestrator_models_follows_llm_reference():
    text = INTEGRATIONS_YML.replace(
        "model_group: orchestrator", "model_group: main"
    ).replace("- id: orchestrator", "- id: main")
    text += "\nextra_group_marker: true\n"
    data = _load(setup.set_orchestrator_models(text, "anthropic"))
    assert [g["id"] for g in data["model_groups"]] == ["main"]
    assert data["model_groups"][0]["models"][0]["provider"] == "anthropic"


def test_set_orchestrator_models_leaves_other_groups():
    text = INTEGRATIONS_YML.replace(
        "channels:",
        "  - id: embeddings\n    models:\n      - provider: openai\n"
        "        model: text-embedding-3-small\n\nchannels:",
    )
    data = _load(setup.set_orchestrator_models(text, "anthropic"))
    groups = {g["id"]: g for g in data["model_groups"]}
    assert groups["embeddings"]["models"][0]["provider"] == "openai"
    assert groups["orchestrator"]["models"][0]["provider"] == "anthropic"


def test_set_orchestrator_models_adds_missing_group():
    text = "llm:\n  model_group: orchestrator\nchannels:\n  rest:\n    enabled: true\n"
    data = _load(setup.set_orchestrator_models(text, "anthropic"))
    assert data["model_groups"][0]["id"] == "orchestrator"


def test_set_orchestrator_models_preserves_channels():
    data = _load(setup.set_orchestrator_models(INTEGRATIONS_YML, "anthropic"))
    assert data["channels"]["rest"]["enabled"] is True
    assert data["channels"]["inspector"]["enabled"] is True


def test_apply_provider_openai_is_noop(tmp_path):
    (tmp_path / "integrations.yml").write_text(INTEGRATIONS_YML)
    assert setup.apply_provider(str(tmp_path), "openai") is False
    assert (tmp_path / "integrations.yml").read_text() == INTEGRATIONS_YML


def test_apply_provider_anthropic_rewrites_integrations(tmp_path):
    (tmp_path / "integrations.yml").write_text(INTEGRATIONS_YML)
    assert setup.apply_provider(str(tmp_path), "anthropic") is True
    data = _load((tmp_path / "integrations.yml").read_text())
    assert data["model_groups"][0]["models"][0]["provider"] == "anthropic"


# --- delivered scaffold ------------------------------------------------------

def test_template_is_a_mantle_project():
    # Rasa picks Mantle when integrations.yml and skills/*/skill.md exist.
    assert (TEMPLATE_DIR / "agent.yml").is_file()
    assert (TEMPLATE_DIR / "integrations.yml").is_file()
    assert list((TEMPLATE_DIR / "skills").glob("*/skill.md"))


def test_template_has_no_calm_files():
    # endpoints.yml at a Mantle project root fails startup; the rest are dead
    # weight that would mislead coding agents (see AGENTS.md).
    for name in ["endpoints.yml", "config.yml", "domain.yml", "credentials.yml",
                 "domain", "data", "actions", "e2e_tests"]:
        assert not (TEMPLATE_DIR / name).exists(), name
