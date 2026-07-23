# Rasa Quickstart

Go from nothing to a running [Rasa Pro](https://rasa.com/docs/rasa-pro) (CALM) agent — with coding-agent skills and MCP wired into your editor — in one command.

## Get started

**macOS / Linux**

```bash
curl -fsSL https://raw.githubusercontent.com/rasa-customers/rasa-quickstart/main/install.sh | bash
```

**Windows (PowerShell)**

```powershell
irm https://raw.githubusercontent.com/rasa-customers/rasa-quickstart/main/install.ps1 | iex
```

That's it. The bootstrap installs [`uv`](https://docs.astral.sh/uv/), downloads the project, starts a fresh git repo, sets up a virtual environment, installs Rasa skills for your coding agent, and trains an initial model.

When it finishes:

```bash
cd rasa-quickstart
# add RASA_LICENSE and your LLM key to .env, then:
make inspect
```

> You need a **Rasa Pro license** (`RASA_LICENSE`) and an **LLM key** (`OPENAI_API_KEY` by default). Get a license at [rasa.com](https://rasa.com/).

## Options

Pass a target directory and/or flags. On macOS/Linux, append them after `-s --`:

```bash
curl -fsSL https://raw.githubusercontent.com/rasa-customers/rasa-quickstart/main/install.sh \
  | bash -s -- --ides claude,cursor --provider openai my-agent
```

On Windows, run the script with arguments:

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/rasa-customers/rasa-quickstart/main/install.ps1))) `
  -Ides claude,cursor -Provider openai my-agent
```

| Flag | Values | Default |
|---|---|---|
| `--ides` | `claude`, `cursor`, `vscode`, `jetbrains` (comma-separated) | auto-detected, then prompted |
| `--provider` | `openai`, `anthropic` | `openai` |
| `--yes` | accept detected defaults, no prompts | off |
| *(positional)* | target directory to create | `rasa-quickstart` |

## What you'll get

The bootstrap delivers the project in [`template/`](template/):

```
config.yml          CALM pipeline + LLM model group
domain/             responses, slots, actions
data/flows/         conversation flows (business logic)
actions/            custom Python actions
endpoints.yml       action server, tracker store, model groups
credentials.yml     chat / voice channels
e2e_tests/          end-to-end conversation tests
Makefile            setup / run / inspect / train / ...
scripts/setup.py    one-shot provisioning
.env.example        secrets template (copy to .env)
```

See [`template/README.md`](template/README.md) for the day-to-day building guide.

## Already have the repo?

If you cloned this repo instead of using the bootstrap, the project lives in `template/`:

```bash
cd template
cp .env.example .env    # fill in RASA_LICENSE + your LLM key
make setup
make inspect
```

## Repository layout

This repo is a source/template — most of it never lands on your machine:

- **`template/`** — the delivered project. The bootstrap copies *only* this directory, then starts a fresh git history.
- **`install.sh` / `install.ps1`** — the bootstrap, served over HTTPS and run directly (never copied).
- **`tests/`, `.github/`, `scripts/maintenance/`** — CI and maintenance tooling for this repo, not part of your project.

## Contributing

- Bootstrap logic: `install.sh`, `install.ps1`
- Delivered project: `template/`
- Tests: `uv run --with pytest --with ruamel.yaml python -m pytest tests/`

The pinned Rasa version tracks the latest release over time; the committed scaffold in `template/` is kept in sync by automation.
