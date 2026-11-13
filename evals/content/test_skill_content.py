"""Concern A — skill-content evaluations.

Two layers:

1. **Deterministic spec-conformance** (hard ``assert``) — required frontmatter,
   name/description constraints, name-matches-directory, size limits. These run
   with no LLM and always gate the suite.
2. **LLM-judge clarity/completeness** (DeepEval G-Eval) — runs locally using the
   developer's own model. Skipped automatically when no model/API key is
   configured so the deterministic gate still runs in constrained environments.

Content-concern outcomes are registered so the shared reporter can label them
and write ``evals/results/report.json`` with concerns kept separate.
"""

from __future__ import annotations

import os

import pytest

from evals.lib import discover_skills
from evals.lib.models import JUDGE_MODEL, build_judge_model, ollama_base_url
from evals.lib.reporting import CaseLabel, register_case

SKILLS = discover_skills()

# Any of these signals that a local judge model is available.
_MODEL_ENV_VARS = (
    "OPENAI_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "DEEPEVAL_MODEL",
    "GEMINI_API_KEY",
    "OLLAMA_MODEL",
    "LOCAL_MODEL_API_KEY",
)


def _ollama_reachable() -> bool:
    """True if a local Ollama server answers at the configured base URL."""
    import urllib.request

    try:
        with urllib.request.urlopen(f"{ollama_base_url()}/api/tags", timeout=1.0):
            return True
    except Exception:
        return False


def _has_local_model() -> bool:
    return any(os.getenv(v) for v in _MODEL_ENV_VARS) or _ollama_reachable()


def _skill_ids():
    return [s.name for s in SKILLS]


def test_at_least_one_skill_exists():
    assert SKILLS, "no skills discovered under skills/"


@pytest.mark.parametrize("skill", SKILLS, ids=_skill_ids())
def test_skill_is_spec_conformant(skill):
    """Deterministic, hard-assertion spec conformance for every skill."""
    errors = skill.validate()
    assert not errors, (
        f"skill '{skill.name}' violates the Agent Skills spec:\n  - "
        + "\n  - ".join(errors)
    )


@pytest.mark.parametrize("skill", SKILLS, ids=_skill_ids())
def test_skill_clarity_completeness(skill):
    """LLM-judge clarity/completeness (G-Eval), run locally with the dev's model."""
    if not _has_local_model():
        pytest.skip(
            "no local judge model configured (start Ollama and "
            f"`ollama pull {JUDGE_MODEL}`, or set e.g. OPENAI_API_KEY); "
            "deterministic content checks still enforced"
        )

    from deepeval.metrics import GEval
    from deepeval.test_case import LLMTestCase, LLMTestCaseParams

    from evals.lib.reporting import record_score

    name = register_case(
        f"content::{skill.name}",
        CaseLabel(concern="content", skill=skill.name),
    )

    clarity = GEval(
        name="Clarity and completeness",
        model=build_judge_model(),
        criteria=(
            "Evaluate whether the skill document (the actual output) is clear, "
            "internally consistent (no contradictions), and complete: it should "
            "state when to use the skill, give unambiguous step-by-step "
            "instructions, and include concrete examples. Penalise vagueness, "
            "contradictions, and missing steps."
        ),
        evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
        threshold=0.7,
    )

    test_case = LLMTestCase(
        name=name,
        input=f"Assess the clarity and completeness of the skill '{skill.name}'.",
        actual_output=skill.raw_text,
    )

    # Grade with measure() (not assert_test) so we can read the numeric score
    # off the metric object; assert_test deep-copies metrics and leaves the
    # passed-in object's score unset. The recorded score is what CI re-checks.
    clarity.measure(test_case)
    record_score(
        "content",
        skill.name,
        None,
        score=clarity.score,
        threshold=clarity.threshold,
        success=clarity.is_successful(),
    )
    assert clarity.is_successful(), (
        f"content clarity/completeness for '{skill.name}' scored "
        f"{clarity.score} below threshold {clarity.threshold}: {clarity.reason}"
    )
