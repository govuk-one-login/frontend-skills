"""Pinned Ollama model configuration for local evaluation.

Local evaluation is driven by two pinned Ollama models so results are
comparable across developers:

- ``GENERATION_MODEL`` (``qwen2.5:7b``) produces fixture output for an
  application task case (see ``scripts/generate.py --generate``).
- ``JUDGE_MODEL`` (``qwen2.5:14b``) is the DeepEval G-Eval judge used by both
  eval suites.

CI never runs a model, but it *does* assert that the committed, signed results
were produced with these exact pinned models. To keep the key-free CI verifier
free of DeepEval, this module exposes the pinned model *names* and the Ollama
base-URL resolution using only the standard library. The DeepEval-specific
``build_judge_model`` imports DeepEval lazily, so importing this module never
pulls in DeepEval.
"""

from __future__ import annotations

import os

# Pinned Ollama models. Change here (and regenerate + re-sign results) to roll
# the canonical judge/generation models for the whole repository.
GENERATION_MODEL = "qwen2.5:7b"
JUDGE_MODEL = "qwen2.5:14b"

# Recorded in generate.py when the developer supplies their own output instead
# of generating with the pinned model.
MANUAL_GENERATION_MODEL = "manual"

_DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"


def ollama_base_url() -> str:
    """Return the Ollama server base URL, honouring ``LOCAL_MODEL_BASE_URL``."""
    return os.getenv("LOCAL_MODEL_BASE_URL") or _DEFAULT_OLLAMA_BASE_URL


def build_judge_model():
    """Construct the pinned DeepEval Ollama judge model.

    DeepEval is imported lazily so this module stays importable (and
    CI-safe) without DeepEval installed. ``temperature=0`` keeps judging as
    deterministic as the model allows.
    """
    from deepeval.models import OllamaModel

    return OllamaModel(
        model=JUDGE_MODEL,
        base_url=ollama_base_url(),
        temperature=0,
    )
