#!/usr/bin/env python3
"""CI-side adjudicator for committed evaluation results.

This script runs in CI with **no agent, no LLM, and no API keys**. It only reads
the committed artifacts and performs a fast, deterministic check:

1. ``evals/results/report.json`` exists and is valid (our schema).
2. ``evals/results/manifest.json`` exists and is valid.
3. Every manifest entry's recorded hashes match freshly recomputed hashes of the
   current committed skills, task cases, and fixtures (freshness / integrity).
4. No recorded case in the report is a failure.

Exit code is 0 on success and non-zero on any problem, with a clear, actionable
message. When run under GitHub Actions, a summary is also written to
``$GITHUB_STEP_SUMMARY``.

It deliberately imports only stdlib + the stdlib/PyYAML-only ``evals.lib``
helpers (hashing/manifest/paths); it never imports DeepEval.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from evals.lib.hashing import hash_skill, hash_case, hash_fixture  # noqa: E402
from evals.lib.manifest import read_manifest  # noqa: E402
from evals.lib.paths import (  # noqa: E402
    report_path,
    manifest_path,
    skills_dir,
    cases_dir,
    fixtures_dir,
)

REPORT_SCHEMA = "frontend-skills/report@1"


class VerificationError(Exception):
    """A fatal verification problem; message is safe to show to users."""


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(_REPO_ROOT))
    except ValueError:
        return str(p)


def _load_report() -> dict:
    p = report_path()
    if not p.is_file():
        raise VerificationError(
            f"results missing: {_rel(p)} not found — run the "
            f"eval suites locally and commit the results."
        )
    try:
        report = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise VerificationError(f"report.json is not valid JSON: {exc}") from exc
    if not isinstance(report, dict) or report.get("schema") != REPORT_SCHEMA:
        raise VerificationError(
            f"report.json has an unexpected schema (want {REPORT_SCHEMA!r})."
        )
    for field in ("summary", "concerns", "cases"):
        if field not in report:
            raise VerificationError(f"report.json is missing '{field}'.")
    return report


def _load_manifest() -> dict:
    p = manifest_path()
    if not p.is_file():
        raise VerificationError(
            f"integrity manifest missing: {_rel(p)} not found — "
            f"regenerate results locally (scripts/generate.py + eval run)."
        )
    try:
        manifest = read_manifest(p)
    except Exception as exc:
        raise VerificationError(f"manifest.json is invalid: {exc}") from exc
    if not manifest.get("entries"):
        raise VerificationError("manifest.json has no entries.")
    return manifest


def _recompute(entry: dict) -> list[str]:
    """Return a list of freshness problems for one manifest entry (empty == ok)."""
    problems: list[str] = []
    concern = entry.get("concern")
    skill = entry.get("skill")
    case_id = entry.get("case_id")

    # Skill hash (present on both concerns).
    if "skill_hash" in entry:
        sdir = skills_dir() / skill
        if not sdir.is_dir():
            problems.append(f"skill '{skill}' directory is missing")
        else:
            actual = hash_skill(sdir)
            if actual != entry["skill_hash"]:
                problems.append(
                    f"skill '{skill}' changed since results were generated"
                )

    # Application entries also bind the case + fixture.
    if concern == "application":
        cpath = cases_dir() / skill / f"{case_id}.yaml"
        if "case_hash" in entry:
            if not cpath.is_file():
                # Allow .yml as an alternative extension.
                alt = cases_dir() / skill / f"{case_id}.yml"
                cpath = alt if alt.is_file() else cpath
            if not cpath.is_file():
                problems.append(f"case '{skill}/{case_id}' is missing")
            elif hash_case(cpath) != entry["case_hash"]:
                problems.append(f"case '{skill}/{case_id}' changed")

        if "fixture_hash" in entry:
            fdir = fixtures_dir() / skill / case_id
            if not fdir.is_dir():
                problems.append(f"fixture for '{skill}/{case_id}' is missing")
            elif hash_fixture(fdir) != entry["fixture_hash"]:
                problems.append(f"fixture for '{skill}/{case_id}' changed")

    return problems


def verify() -> list[str]:
    """Run all checks; return a list of human-readable problems (empty == pass)."""
    problems: list[str] = []

    report = _load_report()
    manifest = _load_manifest()

    # 1. Freshness / integrity.
    stale: list[str] = []
    for entry in manifest["entries"]:
        stale.extend(_recompute(entry))
    if stale:
        problems.append(
            "results are stale or tampered — regenerate and re-run evals locally:\n    - "
            + "\n    - ".join(stale)
        )

    # 2. Recorded failures.
    failed_cases = [c for c in report.get("cases", []) if not c.get("passed", False)]
    if failed_cases:
        names = ", ".join(
            c.get("name", f"{c.get('concern')}::{c.get('skill')}") for c in failed_cases
        )
        problems.append(f"one or more recorded eval cases failed: {names}")

    # 3. Sanity: report must reference at least one case.
    if not report.get("cases"):
        problems.append("report.json records no cases.")

    return problems


def _write_summary(text: str) -> None:
    summary_file = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_file:
        try:
            with open(summary_file, "a", encoding="utf-8") as fh:
                fh.write(text + "\n")
        except OSError:
            pass


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Key-free CI adjudicator: validate committed report.json + "
            "manifest.json, recompute content hashes to prove freshness, and "
            "fail on missing/stale/tampered/failing results. Never calls an LLM."
        )
    )
    parser.parse_args(argv)

    try:
        problems = verify()
    except VerificationError as exc:
        msg = f"❌ eval gate FAILED: {exc}"
        print(msg, file=sys.stderr)
        _write_summary(f"## Eval gate\n\n**FAILED**\n\n{exc}")
        return 1

    if problems:
        body = "\n".join(f"- {p}" for p in problems)
        print("❌ eval gate FAILED:\n" + body, file=sys.stderr)
        _write_summary(f"## Eval gate\n\n**FAILED**\n\n{body}")
        return 1

    print("✅ eval gate passed: committed results are fresh and all cases passed.")
    _write_summary(
        "## Eval gate\n\n**PASSED** — committed results are fresh and all "
        "recorded cases passed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
