"""Report capture: bind eval outcomes to concern labels and DeepEval's run data.

DeepEval's native ``TestRun`` records per-test-case pass/fail for graded
(LLM-judge) cases but does not know about our two concerns (content vs
application), and it does not see the deterministic gate tests at all. We
therefore keep our own authoritative outcome registry, populated from pytest
itself, and additionally embed DeepEval's native run under ``deepeval``.

Flow:

1. Suites *register* the identity of each graded test case (concern, skill,
   case id) keyed by the DeepEval ``LLMTestCase.name``.
2. The conftest also *seeds* the registry from discovery so every skill
   (content) and case (application) appears even on model-less runs.
3. A pytest hook *records outcomes* (pass/fail/skip) per concern+skill+case as
   tests complete.
4. On session finish we write ``evals/results/report.json`` combining the
   outcomes, the concern separation, and the native DeepEval run (kept as-is).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from evals.lib.paths import report_path
from evals.lib.models import GENERATION_MODEL, JUDGE_MODEL

# name -> label metadata, populated by tests / discovery seeding.
_REGISTRY: dict[str, dict[str, Any]] = {}

# (concern, skill, case_id) -> {"passed": bool, "skipped": bool}
_OUTCOMES: dict[tuple[str, str, str | None], dict[str, bool]] = {}

# (concern, skill, case_id) -> {"score": float|None, "threshold": float|None,
#                               "metric_success": bool|None}
# Populated directly by the suites from the metric object after grading, so it
# does not depend on DeepEval persisting a native run (which only happens under
# `deepeval test run`, not plain pytest).
_SCORES: dict[tuple[str, str, str | None], dict[str, Any]] = {}


@dataclass
class CaseLabel:
    concern: str  # "content" | "application"
    skill: str
    case_id: str | None = None


def register_case(name: str, label: CaseLabel) -> str:
    """Register a DeepEval test-case name with its concern label."""
    _REGISTRY[name] = asdict(label)
    return name


def reset() -> None:
    _REGISTRY.clear()
    _OUTCOMES.clear()
    _SCORES.clear()


def record_score(
    concern: str,
    skill: str,
    case_id: str | None,
    *,
    score: float | None,
    threshold: float | None,
    success: bool | None,
) -> None:
    """Record a graded metric's score/threshold for a concern+skill+case.

    Called by the suites straight from the metric object after grading, so the
    report captures scores even under plain pytest. When multiple metrics map
    to one case we keep the most conservative view (lowest score, highest
    threshold, success only if all succeeded)."""
    key = (concern, skill, case_id)
    prev = _SCORES.get(key)
    if prev is None:
        _SCORES[key] = {
            "score": score,
            "threshold": threshold,
            "metric_success": success,
        }
        return
    if score is not None and (prev["score"] is None or score < prev["score"]):
        prev["score"] = score
    if threshold is not None and (
        prev["threshold"] is None or threshold > prev["threshold"]
    ):
        prev["threshold"] = threshold
    if success is not None:
        prev["metric_success"] = bool(prev.get("metric_success", True)) and bool(success)
    _SCORES[key] = prev


def record_outcome(concern: str, skill: str, case_id: str | None, *, passed: bool,
                   skipped: bool = False) -> None:
    """Record (or downgrade) an outcome for a concern+skill+case key.

    A failure always wins over a prior pass; a real pass/fail wins over skip.
    """
    key = (concern, skill, case_id)
    prev = _OUTCOMES.get(key)
    if prev is None:
        _OUTCOMES[key] = {"passed": passed, "skipped": skipped}
        return
    # Failure is sticky.
    if not passed:
        prev["passed"] = False
        prev["skipped"] = False
    elif not skipped:
        # A concrete pass upgrades a previous skip-only record.
        prev["skipped"] = prev["skipped"] and skipped
    _OUTCOMES[key] = prev


def _native_run_dict() -> dict[str, Any] | None:
    try:
        from deepeval.test_run import global_test_run_manager

        data = global_test_run_manager.get_latest_test_run_data()
    except Exception:
        return None
    if data is None:
        return None
    if hasattr(data, "model_dump"):
        try:
            return data.model_dump(mode="json")
        except Exception:
            return None
    if isinstance(data, dict):
        return data
    return None


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _metrics_by_case_name(native: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Map a DeepEval test-case name -> best metric {score, threshold, success}.

    DeepEval's native run embeds per-test-case metric results. Field names have
    varied across versions, so we read defensively: a test case may expose its
    metrics under ``metrics_data`` / ``metricsData`` / ``metrics_metadata``, and
    each metric carries ``score``, ``threshold`` and ``success`` (the latter has
    also appeared as ``metric_success`` / ``passed``). When a case has several
    metrics we keep the most conservative view: the lowest score, and overall
    success only if every metric succeeded.
    """
    if not isinstance(native, dict):
        return {}
    test_cases = native.get("test_cases") or native.get("testCases") or []
    if not isinstance(test_cases, list):
        return {}

    out: dict[str, dict[str, Any]] = {}
    for tc in test_cases:
        if not isinstance(tc, dict):
            continue
        name = tc.get("name")
        if not name:
            continue
        metrics = (
            tc.get("metrics_data")
            or tc.get("metricsData")
            or tc.get("metrics_metadata")
            or []
        )
        if not isinstance(metrics, list) or not metrics:
            continue

        score: float | None = None
        threshold: float | None = None
        success = True
        saw_metric = False
        for m in metrics:
            if not isinstance(m, dict):
                continue
            saw_metric = True
            m_score = _coerce_float(m.get("score"))
            m_threshold = _coerce_float(m.get("threshold"))
            m_success = m.get("success")
            if m_success is None:
                m_success = m.get("metric_success")
            if m_success is None:
                m_success = m.get("passed")

            if m_score is not None and (score is None or m_score < score):
                score = m_score
            if m_threshold is not None and (threshold is None or m_threshold > threshold):
                threshold = m_threshold
            if m_success is not None:
                success = success and bool(m_success)

        if saw_metric:
            out[str(name)] = {
                "score": score,
                "threshold": threshold,
                "metric_success": success,
            }
    return out


def write_report(path: Path | None = None) -> Path:
    """Write ``report.json`` combining outcomes, concern labels, and native run."""
    out_path = Path(path) if path is not None else report_path()
    native = _native_run_dict()
    metrics = _metrics_by_case_name(native)

    cases: list[dict[str, Any]] = []
    for name, label in sorted(_REGISTRY.items()):
        entry = dict(label)
        entry["name"] = name
        key = (label["concern"], label["skill"], label.get("case_id"))
        outcome = _OUTCOMES.get(key)
        if outcome is None:
            # No recorded outcome (e.g. the graded test was skipped and no
            # deterministic test mapped here) -> treat as passed=True, skipped.
            entry["passed"] = True
            entry["skipped"] = True
        else:
            entry["passed"] = bool(outcome["passed"])
            entry["skipped"] = bool(outcome.get("skipped", False))

        # Attach the graded-metric score/threshold when this case was graded.
        # Prefer the score recorded directly by the suite (works under plain
        # pytest); fall back to DeepEval's native run when present. Absent on
        # model-less (skipped) runs; CI only enforces score >= threshold for
        # cases that actually carry a score.
        key_sc = (label["concern"], label["skill"], label.get("case_id"))
        m = _SCORES.get(key_sc) or metrics.get(name)
        if m is not None:
            entry["score"] = m.get("score")
            entry["threshold"] = m.get("threshold")
            entry["metric_success"] = m.get("metric_success")

        cases.append(entry)

    content_cases = [c for c in cases if c["concern"] == "content"]
    application_cases = [c for c in cases if c["concern"] == "application"]

    def _summ(items: list[dict[str, Any]]) -> dict[str, int]:
        return {
            "total": len(items),
            "passed": sum(1 for c in items if c["passed"]),
            "failed": sum(1 for c in items if not c["passed"]),
        }

    report = {
        "schema": "frontend-skills/report@2",
        "models": {
            "generation": GENERATION_MODEL,
            "judge": JUDGE_MODEL,
        },
        "summary": _summ(cases),
        "concerns": {
            "content": _summ(content_cases),
            "application": _summ(application_cases),
        },
        "cases": cases,
        "deepeval": native,  # native report kept as-is (may be null)
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return out_path
