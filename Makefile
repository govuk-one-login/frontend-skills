# frontend-skills — developer entrypoints
#
# Local workflow uses the full eval stack (DeepEval + pytest). CI uses only the
# key-free verifier. Everything below is documented in the README.

PYTHON ?= python3
VENV   ?= .venv
BIN     = $(VENV)/bin

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

$(BIN)/python:
	$(PYTHON) -m venv $(VENV)

.PHONY: install
install: $(BIN)/python ## Install the full local eval stack (DeepEval + pytest)
	$(BIN)/python -m pip install --upgrade pip
	$(BIN)/python -m pip install -r evals/requirements.txt

.PHONY: install-ci
install-ci: $(BIN)/python ## Install only the key-free CI verifier deps (no DeepEval)
	$(BIN)/python -m pip install --upgrade pip
	$(BIN)/python -m pip install -r requirements-ci.txt

.PHONY: generate
generate: ## Record a locally-generated output into fixtures + manifest. Args: CASE=... OUTPUT=...
	@test -n "$(CASE)"   || (echo "set CASE=evals/cases/<skill>/<case>.yaml"; exit 2)
	@test -n "$(OUTPUT)" || (echo "set OUTPUT=path/to/generated_output"; exit 2)
	$(BIN)/python scripts/generate.py --case "$(CASE)" --output "$(OUTPUT)"

.PHONY: eval
eval: ## Run both eval suites locally and (re)write evals/results/report.json
	$(BIN)/python -m pytest evals

.PHONY: test
test: ## Run the tooling unit tests (lib + generate + verifier)
	$(BIN)/python -m pytest evals/lib/test_lib.py scripts/test_generate.py scripts/test_verify_results.py

.PHONY: verify
verify: ## Adjudicate committed results the same way CI does (key-free)
	$(BIN)/python scripts/verify_results.py

.PHONY: all
all: eval verify ## Run the eval suites then adjudicate the results locally
