# Your Rasa Agent

A [Rasa Mantle](https://mantle.rasa.com) agent, scaffolded and ready to build on. Mantle is Rasa's LLM-native engine: you describe behaviour in plain language (`agent.yml` and skills) and add framework-enforced guarantees only where you need them. This is the default `rasa init --engine mantle` project — a small banking agent that shows recent transactions — with coding-agent skills, the Rasa MCP server, and the Mantle docs wired in.

## Prerequisites

- A Rasa Pro license → put it in `.env` as `RASA_LICENSE`
- An LLM key (OpenAI by default) → `OPENAI_API_KEY` in `.env`
- [`uv`](https://docs.astral.sh/uv/) (the setup handles the Python version for you)

## First run

```bash
cp .env.example .env      # then fill in RASA_LICENSE and OPENAI_API_KEY
make setup                # venv + deps, coding-agent skills + docs, trains a model
make inspect              # open the Inspector and talk to your agent
```

Try: *"Show me my recent transactions."*

## Commands

| Command | What it does |
|---|---|
| `make setup` | Provision venv + deps, wire up coding agents, train a model |
| `make inspect` | Open the Inspector (chat with the agent, watch its reasoning) |
| `make run` | Run the Rasa API server |
| `make train` | Validate and package the agent into `models/` |
| `make validate` | Validate `agent.yml`, `integrations.yml`, and skills |
| `make shell` | Chat with the agent in the terminal |
| `make skills` | (Re)install Mantle skills, MCP + docs (e.g. `make skills IDES=cursor`) |
| `make clean` | Remove venv, models, and cache |

Run `make help` any time for this list.

## Project layout

```
agent.yml           # identity, persona, global rules
integrations.yml    # LLM model groups, channels, optional MCP servers / tracing
skills/             # one folder per skill (the folder name is the skill id)
  view_transactions/
    skill.md        # frontmatter + plain-language instructions
    memory.yml      # what this skill remembers
    tools.py        # Python tools the skill can call (@tool)
AGENTS.md           # context for your coding agent
.env                # your secrets (git-ignored)
```

A skill can grow `responses.yml` (verbatim wording) and `references/` (knowledge); the project root can hold shared `tools/`, `memory.yml`, `responses.yml`, `references/`, and hooks.

## Building on it

- **Add a skill:** create `skills/<name>/skill.md`, then `make validate` and `make train`. Keep each skill to one job.
- **Add a tool:** write an `async` function decorated with `@tool` in the skill's `tools.py` (see `skills/view_transactions/tools.py`). Tools are auto-discovered.
- **Switch LLM provider:** edit the `orchestrator` group under `model_groups` in `integrations.yml`, then set the matching key in `.env`. (The bootstrap's `--provider anthropic` does this for you.)
- **Test with simulated users:** ask your coding agent to *"simulate a happy path for the view_transactions skill"* while `make inspect` is running — it writes scenarios under `eval/` and runs them through the Rasa MCP server.
- **Coding-agent help:** `make setup` / `make skills` installs the Mantle skills into your editor (e.g. `.claude/skills/`), registers the `rasa-tools` MCP server, and downloads the Mantle docs to `.rasa/docs/mantle/`. `AGENTS.md` tells your coding agent how to use them.

> Mantle is new. What you (or your coding agent) remember about Rasa is probably **CALM** — flows, slots, `domain.yml`, custom actions. None of those exist here; check `.rasa/docs/mantle/` instead.

Full docs: https://mantle.rasa.com
