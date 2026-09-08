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

# name -> label metadata, populated by tests / discovery seeding.
_REGISTRY: dict[str, dict[str, Any]] = {}

# (concern, skill, case_id) -> {"passed": bool, "skipped": bool}
_OUTCOMES: dict[tuple[str, str, str | None], dict[str, bool]] = {}


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


def write_report(path: Path | None = None) -> Path:
    """Write ``report.json`` combining outcomes, concern labels, and native run."""
    out_path = Path(path) if path is not None else report_path()
    native = _native_run_dict()

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
        "schema": "frontend-skills/report@1",
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
