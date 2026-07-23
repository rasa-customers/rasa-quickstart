# Rasa Quickstart — common commands. Run `make help` for the list.
# Every target runs through `uv run`, which provisions the venv from
# pyproject.toml + .python-version on first use. Rasa auto-loads .env.
SHELL := /bin/bash

.PHONY: help setup train validate run actions inspect shell skills clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-9s\033[0m %s\n", $$1, $$2}'

setup: ## Provision venv + deps, wire up coding-agent skills, train a model
	uv run python scripts/setup.py

train: ## Train a model
	uv run rasa train

validate: ## Validate flows / domain / config
	uv run rasa data validate

run: ## Run the Rasa API server
	uv run rasa run --enable-api --cors "*"

actions: ## Run the custom action server
	uv run rasa run actions

inspect: ## Open the CALM inspector (browser debugger)
	uv run rasa inspect --nextgen --cors "*"

shell: ## Chat with the assistant in the terminal
	uv run rasa shell

skills: ## (Re)install coding-agent skills + MCP (rasa tools init skills)
	uv run rasa tools init skills

clean: ## Remove venv, trained models, and Rasa cache
	rm -rf .venv models .rasa
