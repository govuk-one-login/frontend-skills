"""Pytest configuration for the eval suites.

Ensures the repository root is importable so tests can use
``from evals.lib import ...`` regardless of the working directory pytest is
invoked from, records per-test outcomes mapped to a concern, and writes the
combined ``evals/results/report.json`` at the end of a run.

The report always reflects the discovered content and application cases with
per-case pass/fail and a concern label, keeping the two concerns separate.
DeepEval's native run data is embedded under the ``deepeval`` key when available.
"""

import re
import sys
from pathlib import Path

# Repo root is the parent of the `evals/` directory that holds this file.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _seed_registry_from_discovery() -> None:
    """Ensure every discovered content/application case is represented."""
    from evals.lib import discover_skills, discover_cases
    from evals.lib.reporting import CaseLabel, register_case, _REGISTRY

    for skill in discover_skills():
        name = f"content::{skill.name}"
        if name not in _REGISTRY:
            register_case(name, CaseLabel(concern="content", skill=skill.name))

    for case in discover_cases():
        name = f"application::{case.skill}::{case.id}"
        if name not in _REGISTRY:
            register_case(
                name,
                CaseLabel(concern="application", skill=case.skill, case_id=case.id),
            )


_PARAM_RE = re.compile(r"\[(?P<param>.+)\]$")


def _classify(nodeid: str):
    """Map a pytest nodeid to (concern, skill, case_id) or None if unrelated."""
    if "evals/content/" in nodeid:
        concern = "content"
    elif "evals/application/" in nodeid:
        concern = "application"
    else:
        return None

    m = _PARAM_RE.search(nodeid)
    if not m:
        return None
    param = m.group("param")

    if concern == "content":
        # param id is the skill name.
        return ("content", param, None)
    # application param id is "<skill>/<case-id>".
    if "/" in param:
        skill, case_id = param.split("/", 1)
        return ("application", skill, case_id)
    return None


def pytest_runtest_logreport(report):
    """Record pass/fail/skip per concern+skill+case from the call phase."""
    # Only consider the actual test call (skips are reported in setup).
    if report.when not in ("call", "setup"):
        return
    classified = _classify(report.nodeid)
    if classified is None:
        return
    concern, skill, case_id = classified

    from evals.lib.reporting import record_outcome

    if report.skipped:
        record_outcome(concern, skill, case_id, passed=True, skipped=True)
    elif report.when == "call":
        record_outcome(concern, skill, case_id, passed=report.passed, skipped=False)
    elif report.failed:  # setup error
        record_outcome(concern, skill, case_id, passed=False, skipped=False)


def pytest_sessionfinish(session, exitstatus):
    """Write the combined report at the end of an eval run."""
    try:
        from evals.lib.reporting import write_report

        _seed_registry_from_discovery()
        write_report()
    except Exception as exc:  # pragma: no cover - never fail the run on reporting
        print(f"warning: failed to write report.json: {exc}", file=sys.stderr)
