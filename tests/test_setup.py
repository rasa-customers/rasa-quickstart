"""Unit tests for template/scripts/setup.py.

These live at the repo root (maintainer-only) and are never delivered to a
developer's machine. They exercise the pure logic of the setup script; the
subprocess steps (uv sync, rasa ...) are verified by an end-to-end run.
"""

import sys
import pathlib

import pytest
from ruamel.yaml import YAML

SETUP_DIR = pathlib.Path(__file__).resolve().parents[1] / "template" / "scripts"
sys.path.insert(0, str(SETUP_DIR))

import setup  # noqa: E402

_yaml = YAML()


def _load(text):
    from io import StringIO

    return _yaml.load(StringIO(text))


# --- config.yml / endpoints.yml fixtures mirroring the 3.17 scaffold ---------

CONFIG_YML = """\
recipe: default.v1
assistant_id: piercing-heap
language: en
pipeline:
- name: CompactLLMCommandGenerator
  llm:
    model_group: openai-gpt-5-1
policies:
- name: FlowPolicy
"""

ENDPOINTS_YML = """\
# endpoints
action_endpoint:
  actions_module: "actions"

model_groups:
  - id: openai-gpt-5-1
    models:
      - provider: openai
        model: gpt-5.1-2025-11-13
        reasoning_effort: "none"
        timeout: 15
"""


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


# --- ensure_env --------------------------------------------------------------

def test_ensure_env_creates_from_example(tmp_path):
    (tmp_path / ".env.example").write_text("RASA_LICENSE=\nOPENAI_API_KEY=\n")
    created, missing = setup.ensure_env(
        str(tmp_path), ["RASA_LICENSE", "OPENAI_API_KEY"]
    )
    assert created is True
    assert (tmp_path / ".env").exists()
    assert missing == ["RASA_LICENSE", "OPENAI_API_KEY"]


def test_ensure_env_existing_is_untouched(tmp_path):
    (tmp_path / ".env.example").write_text("RASA_LICENSE=\n")
    (tmp_path / ".env").write_text("RASA_LICENSE=abc\nOPENAI_API_KEY=xyz\n")
    created, missing = setup.ensure_env(
        str(tmp_path), ["RASA_LICENSE", "OPENAI_API_KEY"]
    )
    assert created is False
    assert missing == []
    assert (tmp_path / ".env").read_text() == "RASA_LICENSE=abc\nOPENAI_API_KEY=xyz\n"


def test_ensure_env_reports_absent_and_empty_keys(tmp_path):
    (tmp_path / ".env.example").write_text("RASA_LICENSE=\n")
    (tmp_path / ".env").write_text("RASA_LICENSE=abc\nOPENAI_API_KEY=\n")
    _, missing = setup.ensure_env(
        str(tmp_path), ["RASA_LICENSE", "OPENAI_API_KEY", "OTHER"]
    )
    assert missing == ["OPENAI_API_KEY", "OTHER"]


def test_ensure_env_without_example_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        setup.ensure_env(str(tmp_path), ["RASA_LICENSE"])


# --- provider helpers --------------------------------------------------------

def test_provider_env_key():
    assert setup.provider_env_key("openai") == "OPENAI_API_KEY"
    assert setup.provider_env_key("anthropic") == "ANTHROPIC_API_KEY"


# --- command builders --------------------------------------------------------

def test_uv_sync_command():
    assert setup.uv_sync_command() == ["uv", "sync"]


def test_skills_command_joins_ides():
    assert setup.skills_command(["claude", "cursor"]) == [
        "uv", "run", "rasa", "tools", "init", "skills", "--yes",
        "--ides", "claude,cursor",
    ]


def test_train_command():
    assert setup.train_command() == ["uv", "run", "rasa", "train"]


# --- provider config rewrite -------------------------------------------------

def test_set_pipeline_model_group():
    out = setup.set_pipeline_model_group(CONFIG_YML, "anthropic-claude")
    data = _load(out)
    assert data["pipeline"][0]["llm"]["model_group"] == "anthropic-claude"


def test_set_model_groups_openai_keeps_openai():
    out = setup.set_model_groups(ENDPOINTS_YML, "openai")
    data = _load(out)
    assert data["model_groups"][0]["id"] == "openai-gpt-5-1"
    assert data["model_groups"][0]["models"][0]["provider"] == "openai"


def test_set_model_groups_anthropic():
    out = setup.set_model_groups(ENDPOINTS_YML, "anthropic")
    data = _load(out)
    group = data["model_groups"][0]
    assert group["id"] == setup.PROVIDER_PRESETS["anthropic"]["group_id"]
    assert group["models"][0]["provider"] == "anthropic"
    assert group["models"][0]["model"] == (
        setup.PROVIDER_PRESETS["anthropic"]["models"][0]["model"]
    )


def test_set_model_groups_preserves_other_endpoints():
    out = setup.set_model_groups(ENDPOINTS_YML, "anthropic")
    data = _load(out)
    assert data["action_endpoint"]["actions_module"] == "actions"


def test_apply_provider_openai_is_noop(tmp_path):
    (tmp_path / "config.yml").write_text(CONFIG_YML)
    (tmp_path / "endpoints.yml").write_text(ENDPOINTS_YML)
    changed = setup.apply_provider(str(tmp_path), "openai")
    assert changed is False
    assert (tmp_path / "config.yml").read_text() == CONFIG_YML
    assert (tmp_path / "endpoints.yml").read_text() == ENDPOINTS_YML


def test_apply_provider_anthropic_rewrites_both_files(tmp_path):
    (tmp_path / "config.yml").write_text(CONFIG_YML)
    (tmp_path / "endpoints.yml").write_text(ENDPOINTS_YML)
    changed = setup.apply_provider(str(tmp_path), "anthropic")
    assert changed is True
    cfg = _load((tmp_path / "config.yml").read_text())
    eps = _load((tmp_path / "endpoints.yml").read_text())
    group_id = setup.PROVIDER_PRESETS["anthropic"]["group_id"]
    assert cfg["pipeline"][0]["llm"]["model_group"] == group_id
    assert eps["model_groups"][0]["id"] == group_id
    assert eps["model_groups"][0]["models"][0]["provider"] == "anthropic"
