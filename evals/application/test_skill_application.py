"""Concern B — grade locally-generated agent output against task cases.

For each task case under ``evals/cases/<skill>/<case-id>.yaml`` this suite loads
the committed fixture output from ``evals/fixtures/<skill>/<case-id>/`` and grades
it with a DeepEval G-Eval metric against the case's ``expected_criteria``.

Two layers, mirroring the content suite:

1. **Deterministic presence check** (hard ``assert``) — every case must have a
   non-empty committed fixture. This always runs and gates the suite even with
   no model configured, so a missing/blank fixture fails fast.
2. **LLM-judge grading** (G-Eval) — runs locally with the developer's own model,
   skipped automatically when no model/API key is configured.

Application-concern outcomes are registered so the shared reporter labels them
and writes ``evals/results/report.json`` with concerns kept separate.
"""

from __future__ import annotations

import os

import pytest

from evals.lib import discover_cases
from evals.lib.paths import fixtures_dir
from evals.lib.reporting import CaseLabel, register_case

CASES = discover_cases()

_MODEL_ENV_VARS = (
    "OPENAI_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "DEEPEVAL_MODEL",
    "GEMINI_API_KEY",
    "OLLAMA_MODEL",
)


def _has_local_model() -> bool:
    return any(os.getenv(v) for v in _MODEL_ENV_VARS)


def _case_ids():
    return [f"{c.skill}/{c.id}" for c in CASES]


def _fixture_output(case) -> str:
    """Read and concatenate all committed fixture files for a case."""
    fdir = fixtures_dir() / case.skill / case.id
    if not fdir.is_dir():
        return ""
    parts = []
    for f in sorted(fdir.rglob("*")):
        if f.is_file():
            parts.append(f.read_text(encoding="utf-8"))
    return "\n\n".join(parts)


def test_at_least_one_case_exists():
    assert CASES, "no task cases discovered under evals/cases/"


@pytest.mark.parametrize("case", CASES, ids=_case_ids())
def test_fixture_output_present(case):
    """Deterministic gate: each case must have a non-empty committed fixture."""
    output = _fixture_output(case)
    assert output.strip(), (
        f"no committed fixture output for {case.skill}/{case.id}; "
        f"generate one locally and record it with scripts/generate.py"
    )


@pytest.mark.parametrize("case", CASES, ids=_case_ids())
def test_fixture_meets_expected_criteria(case):
    """LLM-judge grading of the committed fixture vs the case criteria."""
    output = _fixture_output(case)
    assert output.strip(), f"missing fixture for {case.skill}/{case.id}"

    if not _has_local_model():
        pytest.skip(
            "no local judge model configured (set e.g. OPENAI_API_KEY); "
            "fixture-presence check still enforced"
        )

    from deepeval import assert_test
    from deepeval.metrics import GEval
    from deepeval.test_case import LLMTestCase, LLMTestCaseParams

    name = register_case(
        f"application::{case.skill}::{case.id}",
        CaseLabel(concern="application", skill=case.skill, case_id=case.id),
    )

    correctness = GEval(
        name="Meets expected criteria",
        criteria=(
            "Given the task and the expected criteria, judge whether the actual "
            "output satisfies every expected criterion. The output fully passes "
            "only if all criteria are met. Penalise missing or contradicted "
            "criteria."
        ),
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
            LLMTestCaseParams.EXPECTED_OUTPUT,
        ],
        threshold=0.7,
    )

    test_case = LLMTestCase(
        name=name,
        input=case.task,
        actual_output=output,
        expected_output=(
            "The output should satisfy all of these criteria:\n"
            + case.expected_criteria_text
        ),
    )
    assert_test(test_case, [correctness])
