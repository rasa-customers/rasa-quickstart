#!/usr/bin/env python3
"""Provision this Rasa Quickstart project.

Runs via `uv run python scripts/setup.py` (or `make setup`). Idempotent.

Steps: ensure `.env` exists -> `uv sync` -> apply the chosen LLM provider ->
install coding-agent skills -> train an initial model.

Flags let the bootstrap (or a future install-builder) drive it unattended;
omitted flags fall back to interactive prompts:

    --ides claude,cursor,vscode,jetbrains   which coding agents to wire up
    --provider openai|anthropic             LLM provider (default: openai)
    --yes                                   accept detected defaults, no prompts
    --project-path PATH                     project dir (default: current dir)
"""

import argparse
import io
import pathlib
import shutil
import subprocess
import sys

ALLOWED_IDES = ["claude", "cursor", "vscode", "jetbrains"]
DEFAULT_IDES = ["claude"]

IDE_SIGNATURES = {
    "claude": {"commands": ["claude"], "paths": ["~/.claude"]},
    "cursor": {
        "commands": ["cursor"],
        "paths": ["~/.cursor", "/Applications/Cursor.app"],
    },
    "vscode": {
        "commands": ["code"],
        "paths": ["~/.vscode", "/Applications/Visual Studio Code.app"],
    },
    "jetbrains": {
        "commands": [],
        "paths": [
            "~/.config/JetBrains",
            "~/Library/Application Support/JetBrains",
        ],
    },
}

PROVIDER_PRESETS = {
    "openai": {
        "group_id": "openai-gpt-5-1",
        "env_key": "OPENAI_API_KEY",
        "models": [
            {
                "provider": "openai",
                "model": "gpt-5.1-2025-11-13",
                "reasoning_effort": "none",
                "timeout": 15,
            }
        ],
    },
    "anthropic": {
        "group_id": "anthropic-claude",
        "env_key": "ANTHROPIC_API_KEY",
        # NOTE: model string not yet verified end-to-end against a live
        # Anthropic key; adjust to the current Claude model as needed.
        "models": [
            {
                "provider": "anthropic",
                "model": "claude-sonnet-4-5-20250929",
                "timeout": 15,
            }
        ],
    },
}

# --- argument parsing --------------------------------------------------------

def parse_args(argv):
    parser = argparse.ArgumentParser(description="Set up the Rasa Quickstart project.")
    parser.add_argument("--ides", default=None,
                        help="Comma-separated coding agents: %s" % ",".join(ALLOWED_IDES))
    parser.add_argument("--provider", default="openai", choices=list(PROVIDER_PRESETS),
                        help="LLM provider (default: openai)")
    parser.add_argument("--yes", action="store_true",
                        help="Accept detected defaults; no prompts")
    parser.add_argument("--skip-train", dest="skip_train", action="store_true",
                        help="Skip the final `rasa train` (e.g. for CI)")
    parser.add_argument("--project-path", dest="project_path", default=".",
                        help="Project directory (default: current dir)")
    return parser.parse_args(argv)


# --- IDE selection -----------------------------------------------------------

def parse_ides(value):
    return [part.strip().lower() for part in value.split(",") if part.strip()]


def validate_ides(ides):
    for ide in ides:
        if ide not in ALLOWED_IDES:
            raise ValueError(
                "Unknown IDE: %s. Choose from %s" % (ide, ", ".join(ALLOWED_IDES))
            )


def _default_exists(path):
    return pathlib.Path(path).expanduser().exists()


def detect_ides(which=shutil.which, exists=_default_exists):
    found = []
    for ide in ALLOWED_IDES:
        sig = IDE_SIGNATURES[ide]
        if any(which(c) for c in sig["commands"]) or any(exists(p) for p in sig["paths"]):
            found.append(ide)
    return found


def resolve_ides(flag, detected, assume_yes, prompt):
    if flag:
        ides = parse_ides(flag)
    elif assume_yes:
        ides = list(detected) or list(DEFAULT_IDES)
    else:
        default = list(detected) or list(DEFAULT_IDES)
        ides = parse_ides(prompt(default)) or list(default)
    validate_ides(ides)
    return ides


# --- environment file --------------------------------------------------------

def _parse_env(text):
    values = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def ensure_env(project_path, required_keys):
    proj = pathlib.Path(project_path)
    env_file = proj / ".env"
    example = proj / ".env.example"
    created = False
    if not env_file.exists():
        if not example.exists():
            raise FileNotFoundError("No .env.example found in %s" % project_path)
        shutil.copyfile(example, env_file)
        created = True
    values = _parse_env(env_file.read_text())
    missing = [key for key in required_keys if not values.get(key)]
    return created, missing


def provider_env_key(provider):
    return PROVIDER_PRESETS[provider]["env_key"]


# --- provider config rewrite -------------------------------------------------

_YAML = None


def _yaml_engine():
    # Imported lazily: ruamel.yaml ships with rasa-pro and is only needed for
    # the (non-default) provider rewrite, so bare `python setup.py` still runs.
    global _YAML
    if _YAML is None:
        from ruamel.yaml import YAML

        _YAML = YAML()
        _YAML.preserve_quotes = True
    return _YAML


def _load_yaml(text):
    return _yaml_engine().load(io.StringIO(text))


def _dump_yaml(data):
    buf = io.StringIO()
    _yaml_engine().dump(data, buf)
    return buf.getvalue()


def set_pipeline_model_group(config_text, group_id):
    data = _load_yaml(config_text)
    for step in data.get("pipeline", []):
        if isinstance(step, dict) and "llm" in step and "model_group" in step["llm"]:
            step["llm"]["model_group"] = group_id
    return _dump_yaml(data)


def set_model_groups(endpoints_text, provider):
    data = _load_yaml(endpoints_text)
    preset = PROVIDER_PRESETS[provider]
    data["model_groups"] = [
        {"id": preset["group_id"], "models": [dict(m) for m in preset["models"]]}
    ]
    return _dump_yaml(data)


def apply_provider(project_path, provider):
    # The scaffold already ships the OpenAI model group; nothing to rewrite.
    if provider == "openai":
        return False
    proj = pathlib.Path(project_path)
    config_file = proj / "config.yml"
    endpoints_file = proj / "endpoints.yml"
    group_id = PROVIDER_PRESETS[provider]["group_id"]
    config_file.write_text(set_pipeline_model_group(config_file.read_text(), group_id))
    endpoints_file.write_text(set_model_groups(endpoints_file.read_text(), provider))
    return True


# --- external commands -------------------------------------------------------

def uv_sync_command():
    return ["uv", "sync"]


def skills_command(ides):
    return ["uv", "run", "rasa", "tools", "init", "skills", "--yes",
            "--ides", ",".join(ides)]


def train_command():
    return ["uv", "run", "rasa", "train"]


def _run(cmd, cwd):
    print("+ %s" % " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def _prompt_ides(default):
    answer = input(
        "Install Rasa skills + MCP for which coding agents?\n"
        "  options: %s\n"
        "  [%s]: " % (", ".join(ALLOWED_IDES), ", ".join(default))
    )
    return answer


# --- orchestration -----------------------------------------------------------

def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    proj = args.project_path

    required = ["RASA_LICENSE", provider_env_key(args.provider)]
    created, missing = ensure_env(proj, required)
    if created:
        print("Created .env from .env.example.")
    if missing:
        print("⚠  Add these to .env before running the agent: %s" % ", ".join(missing))

    _run(uv_sync_command(), proj)

    if apply_provider(proj, args.provider):
        print("Configured LLM provider: %s" % args.provider)

    ides = resolve_ides(args.ides, detect_ides(), args.yes, _prompt_ides)
    _run(skills_command(ides), proj)

    if args.skip_train:
        print("Skipping `rasa train` (--skip-train).")
    else:
        _run(train_command(), proj)
    print("\n✔  Setup complete. Try: make inspect")


if __name__ == "__main__":
    main()
