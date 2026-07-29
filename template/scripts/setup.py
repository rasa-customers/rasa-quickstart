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
import os
import pathlib
import random
import re
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
        "models": [
            {
                "provider": "anthropic",
                "model": "claude-opus-5",
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
        try:
            answer = prompt(default)
        except (EOFError, OSError):
            # No usable terminal (e.g. `curl | bash`): take the default.
            answer = ""
        ides = parse_ides(answer) or list(default)
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


def ensure_env(project_path, required_keys, environ=None):
    # A key counts as set if it has a value in .env OR in the process
    # environment (rasa reads both; CI passes RASA_LICENSE as an env var).
    environ = os.environ if environ is None else environ
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
    missing = [
        key for key in required_keys
        if not values.get(key) and not environ.get(key)
    ]
    return created, missing


def provider_env_key(provider):
    return PROVIDER_PRESETS[provider]["env_key"]


LICENSE_URL = "https://rasa.com/docs/rasa-pro/developer-edition/"

# ASCII only: Windows consoles default to cp1252 and crash on fancier art.
LICENSE_BANNER = r"""
  +-------------------------------------------------------------------+
  |                                                                   |
  |      .------.                                                     |
  |     /  .--.  \                                                    |
  |     |  |  |  |==[]==[]==]=>    Your agent is scaffolded --        |
  |     \  `--'  /                 it just needs its license key.     |
  |      `------'                                                     |
  |                                                                   |
  |    Get a FREE Rasa Pro Developer Edition license:                 |
  |                                                                   |
  |      >>   https://rasa.com/docs/rasa-pro/developer-edition/       |
  |                                                                   |
  |    Paste it into .env as RASA_LICENSE (plus your LLM key),        |
  |    then finish with:                                              |
  |                                                                   |
  |      $ make setup                                                 |
  |                                                                   |
  +-------------------------------------------------------------------+
"""


# --- assistant id ------------------------------------------------------------

# Must match the assistant_id shipped in template/config.yml (a test enforces
# this). Every bootstrap replaces it with a random one so deployments are
# distinguishable in telemetry/tracing; ids a user chose are never touched.
DEFAULT_ASSISTANT_ID = "piercing-heap"

_ASSISTANT_ID_LINE_RE = re.compile(r"(?m)^assistant_id:\s*(\S+)\s*$")

_ID_ADJECTIVES = [
    "amber", "bold", "brisk", "calm", "clever", "cosmic", "deft", "eager",
    "fabled", "gentle", "keen", "lively", "lunar", "mellow", "nimble",
    "polar", "quiet", "rapid", "solar", "sturdy", "swift", "tidal",
    "vivid", "witty",
]

_ID_NOUNS = [
    "anchor", "beacon", "canyon", "comet", "condor", "dolphin", "ember",
    "falcon", "garden", "glacier", "harbor", "heron", "lantern", "meadow",
    "nebula", "orchard", "osprey", "pines", "quartz", "river", "sparrow",
    "summit", "tundra", "willow",
]


def random_assistant_id(rng=random):
    return "%s-%s-%04x" % (
        rng.choice(_ID_ADJECTIVES),
        rng.choice(_ID_NOUNS),
        rng.randrange(16 ** 4),
    )


def ensure_assistant_id(project_path, rng=random):
    """Replace the template's default assistant_id with a random one.

    Returns the new id, or None if the id was already customized (idempotent:
    re-running `make setup` never overwrites an assigned or user-chosen id).
    """
    config_file = pathlib.Path(project_path) / "config.yml"
    text = config_file.read_text()
    match = _ASSISTANT_ID_LINE_RE.search(text)
    if not match or match.group(1) != DEFAULT_ASSISTANT_ID:
        return None
    new_id = random_assistant_id(rng)
    config_file.write_text(
        text[: match.start()] + "assistant_id: " + new_id + text[match.end():]
    )
    return new_id


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


def child_env():
    # Rasa prints Unicode (rich banners, telemetry notice); on Windows the
    # console defaults to cp1252 and crashes with UnicodeEncodeError. Force
    # Python UTF-8 mode for child processes (harmless on macOS/Linux).
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _run(cmd, cwd):
    print("+ %s" % " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True, env=child_env())


def _prompt_ides(default):
    message = (
        "Install Rasa skills + MCP for which coding agents?\n"
        "  options: %s\n"
        "  [%s]: " % (", ".join(ALLOWED_IDES), ", ".join(default))
    )
    # Read from the controlling terminal so the prompt works even when stdin
    # is the script itself (e.g. `curl ... | bash`). Fall back to stdin; if
    # neither is usable, raise so resolve_ides() takes the default.
    try:
        with open("/dev/tty", "r+") as tty:
            tty.write(message)
            tty.flush()
            return tty.readline()
    except OSError:
        return input(message)


# --- orchestration -----------------------------------------------------------

def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    proj = args.project_path

    llm_key = provider_env_key(args.provider)
    created, missing = ensure_env(proj, ["RASA_LICENSE", llm_key])
    if created:
        print("Created .env from .env.example.")

    new_id = ensure_assistant_id(proj)
    if new_id:
        print("Assigned assistant_id: %s" % new_id)

    _run(uv_sync_command(), proj)

    if apply_provider(proj, args.provider):
        print("Configured LLM provider: %s" % args.provider)

    # Every `rasa` command is license-gated, so without RASA_LICENSE the
    # skills/train steps below would just crash. Stop here with directions
    # instead; `make setup` re-runs this script and picks up where we left off.
    if "RASA_LICENSE" in missing:
        print(LICENSE_BANNER)
        return

    ides = resolve_ides(args.ides, detect_ides(), args.yes, _prompt_ides)
    _run(skills_command(ides), proj)

    if args.skip_train:
        print("Skipping `rasa train` (--skip-train).")
        next_step = "make inspect"
    elif llm_key in missing:
        print("! %s is not set -- skipping the initial model training." % llm_key)
        next_step = "add %s to .env, then: make train && make inspect" % llm_key
    else:
        _run(train_command(), proj)
        next_step = "make inspect"
    print("\nSetup complete. Next: %s" % next_step)


if __name__ == "__main__":
    main()
