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
generate: ## Record/generate a fixture into fixtures + manifest. Args: CASE=... and one of OUTPUT=... or GENERATE=1
	@test -n "$(CASE)" || (echo "set CASE=evals/cases/<skill>/<case>.yaml"; exit 2)
	@if [ -n "$(GENERATE)" ]; then \
		$(BIN)/python scripts/generate.py --case "$(CASE)" --generate; \
	elif [ -n "$(OUTPUT)" ]; then \
		$(BIN)/python scripts/generate.py --case "$(CASE)" --output "$(OUTPUT)"; \
	else \
		echo "set OUTPUT=path/to/generated_output (manual) or GENERATE=1 (Ollama)"; exit 2; \
	fi

.PHONY: eval
eval: ## Run both eval suites locally and (re)write evals/results/report.json
	$(BIN)/python -m pytest evals

.PHONY: sign
sign: ## Sign the committed results (tamper-evident) into evals/results/signature.json
	$(BIN)/python scripts/sign_results.py

.PHONY: test
test: ## Run the tooling unit tests (lib + generate + verifier + signing)
	$(BIN)/python -m pytest evals/lib/test_lib.py scripts/test_generate.py scripts/test_verify_results.py scripts/test_sign_results.py

.PHONY: verify
verify: ## Adjudicate committed results the same way CI does (key-free)
	$(BIN)/python scripts/verify_results.py

.PHONY: all
all: eval sign verify ## Run the eval suites, sign the results, then adjudicate locally

.PHONY: check-ollama
check-ollama: $(BIN)/python ## Verify Ollama is running and the pinned models are pulled
	@$(BIN)/python scripts/check_ollama.py

.PHONY: ollama-up
ollama-up: $(BIN)/python ## Start the Ollama server (if needed) and pull the pinned models
	@$(BIN)/python scripts/check_ollama.py --ensure

.PHONY: regenerate
regenerate: check-ollama ## Regenerate fixtures for every committed case with the pinned Ollama model
	@for case in $$(find evals/cases -name '*.yaml' -o -name '*.yml'); do \
		echo ">> generating $$case"; \
		$(BIN)/python scripts/generate.py --case "$$case" --generate || exit $$?; \
	done

.PHONY: refresh
refresh: install ollama-up regenerate eval sign verify ## One command: set up, start Ollama, regenerate everything, eval, sign, verify
