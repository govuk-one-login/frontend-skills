"""Concern B — grade generated output against each case's golden example.

A **case** is one prompt paired with one golden example (the expected
high-quality output for that prompt). Coverage grows by adding more cases. The
committed fixture under ``evals/fixtures/<skill>/<case-id>/`` is the output the
current skill produced for the prompt (regenerated locally with the pinned
generation model via ``scripts/generate.py``); this suite grades that committed
output against the case's golden at ``evals/golden/<skill>/<case-id>/``.

Each case is graded two ways, and **both must pass**:

1. **Deterministic marker check** (hard ``assert``) — the output must contain
   every ``must_contain`` string and none of the ``must_not_contain`` strings.
   Always runs, with or without a model, so blatant regressions fail fast and
   deterministically (and CI can rely on the recorded pass/fail).
2. **LLM-judge vs golden** (DeepEval G-Eval) — judges whether the generated
   output matches the quality and covers the same substance as the golden
   example. Runs locally with the pinned judge model; skipped automatically when
   no model is available (the deterministic check still gates).

Application-concern outcomes and scores are recorded so the shared reporter
writes ``evals/results/report.json`` with concerns kept separate.
"""

from __future__ import annotations

import os

import pytest

from evals.lib import discover_cases
from evals.lib.paths import fixtures_dir
from evals.lib.models import JUDGE_MODEL, build_judge_model, ollama_base_url
from evals.lib.reporting import CaseLabel, record_score, register_case

CASES = discover_cases()

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
def test_case_has_golden(case):
    """Deterministic gate: every case must have a non-empty golden example."""
    assert case.golden_text().strip(), (
        f"case {case.skill}/{case.id} has no golden example at "
        f"{case.golden_path}; add the expected output there"
    )


@pytest.mark.parametrize("case", CASES, ids=_case_ids())
def test_output_present(case):
    """Deterministic gate: each case must have a non-empty committed fixture."""
    output = _fixture_output(case)
    assert output.strip(), (
        f"no committed fixture output for {case.skill}/{case.id}; "
        f"generate one locally with scripts/generate.py"
    )


@pytest.mark.parametrize("case", CASES, ids=_case_ids())
def test_output_markers(case):
    """Deterministic marker check: must_contain present, must_not_contain absent."""
    output = _fixture_output(case)
    assert output.strip(), f"missing fixture for {case.skill}/{case.id}"

    missing = [s for s in case.must_contain if s not in output]
    present_forbidden = [s for s in case.must_not_contain if s in output]

    problems = []
    if missing:
        problems.append("missing required markers: " + ", ".join(repr(s) for s in missing))
    if present_forbidden:
        problems.append(
            "contains forbidden markers: " + ", ".join(repr(s) for s in present_forbidden)
        )
    assert not problems, (
        f"output for {case.skill}/{case.id} failed deterministic marker check:\n  - "
        + "\n  - ".join(problems)
    )


@pytest.mark.parametrize("case", CASES, ids=_case_ids())
def test_output_matches_golden(case):
    """LLM-judge: generated output vs the golden example."""
    output = _fixture_output(case)
    assert output.strip(), f"missing fixture for {case.skill}/{case.id}"
    golden = case.golden_text()
    assert golden.strip(), f"missing golden for {case.skill}/{case.id}"

    if not _has_local_model():
        pytest.skip(
            "no local judge model configured (start Ollama and "
            f"`ollama pull {JUDGE_MODEL}`, or set e.g. OPENAI_API_KEY); "
            "deterministic marker check still enforced"
        )

    from deepeval.metrics import GEval
    from deepeval.test_case import LLMTestCase, LLMTestCaseParams

    name = register_case(
        f"application::{case.skill}::{case.id}",
        CaseLabel(concern="application", skill=case.skill, case_id=case.id),
    )

    match = GEval(
        name="Matches golden example",
        model=build_judge_model(),
        criteria=(
            "You are given a reference 'golden' output (the expected output) and "
            "an actual output produced by applying a skill to the same task. "
            "Judge whether the actual output is at least as good as the golden: "
            "it must cover the same substantive features and correct techniques "
            "the golden demonstrates, with comparable quality. Penalise the "
            "actual output for missing features the golden has, for incorrect or "
            "contradicted techniques, and for lower quality. Differences in "
            "wording, ordering, or formatting that do not change substance are "
            "acceptable."
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
        input=case.prompt,
        actual_output=output,
        expected_output=golden,
    )

    # Grade with measure() (not assert_test) so we can read the numeric score
    # off the metric object and record it for CI to re-check.
    match.measure(test_case)
    record_score(
        "application",
        case.skill,
        case.id,
        score=match.score,
        threshold=match.threshold,
        success=match.is_successful(),
    )
    assert match.is_successful(), (
        f"output for {case.skill}/{case.id} scored {match.score} below "
        f"threshold {match.threshold} vs golden: {match.reason}"
    )
