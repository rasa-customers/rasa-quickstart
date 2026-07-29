# Your Rasa Agent

A [Rasa Pro](https://rasa.com/docs/rasa-pro) CALM assistant, scaffolded and ready to build on. This is the default `rasa init` project — a small contact-manager agent — with coding-agent skills wired in.

## Prerequisites

- A Rasa Pro license → put it in `.env` as `RASA_LICENSE`
- An LLM key (OpenAI by default) → `OPENAI_API_KEY` in `.env`
- [`uv`](https://docs.astral.sh/uv/) (the setup handles the Python version for you)

## First run

```bash
cp .env.example .env      # then fill in RASA_LICENSE and OPENAI_API_KEY
make setup                # venv + deps, coding-agent skills, trains a model
make inspect              # open the browser inspector and talk to your agent
```

## Commands

| Command | What it does |
|---|---|
| `make setup` | Provision venv + deps, install coding-agent skills, train a model |
| `make inspect` | Open the CALM inspector (browser debugger) |
| `make run` | Run the Rasa API server |
| `make actions` | Run a standalone action server (actions run in-process by default) |
| `make train` | Train a model |
| `make validate` | Validate flows / domain / config |
| `make shell` | Chat with the agent in the terminal |
| `make skills` | (Re)install coding-agent skills for another editor |
| `make clean` | Remove venv, models, and cache |

Run `make help` any time for this list.

## Project layout

```
config.yml          # CALM pipeline (references the LLM model group by id)
domain/             # responses, slots, actions the agent knows about
data/flows/         # the conversation flows (business logic)
actions/            # custom Python actions
endpoints.yml       # model groups (LLM provider/model) + optional services
credentials.yml     # chat / voice channel credentials
e2e_tests/          # end-to-end conversation tests
.env                # your secrets (git-ignored)
```

## Building on it

- **Add a flow:** create a YAML file under `data/flows/`, then `make validate` and `make train`.
- **Add a custom action:** add it under `actions/` and register it in `domain/`.
- **Switch LLM provider:** edit the `model_groups` block in `endpoints.yml` (and the `model_group` reference in `config.yml`), then set the matching key in `.env`.
- **Coding-agent help:** the `make setup`/`make skills` step installs Rasa skills into your editor (e.g. `.claude/skills/`) so your AI assistant knows how to write flows, actions, and tests for this project.

Full docs: https://rasa.com/docs/rasa-pro
