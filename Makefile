# This is the Rasa Quickstart *source* repo, not a Rasa project itself.
# The delivered project lives in template/. This Makefile only points the way
# for anyone who cloned the repo and ran `make` at the root.

.DEFAULT_GOAL := help

define HINT

This is the Rasa Quickstart source repo, not a Rasa project.

Create a new project with the one-liner in README.md, or set up in place:
    cd template && make setup

endef
export HINT

.PHONY: help
help:
	@echo "$$HINT"

# Any other target (setup, inspect, run, ...) gets the same signpost.
%:
	@echo "$$HINT"
