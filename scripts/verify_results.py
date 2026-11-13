#!/usr/bin/env python3
"""CI-side adjudicator for committed evaluation results.

This script runs in CI with **no agent, no LLM, and no API keys**. It only reads
the committed artifacts and performs a fast, deterministic check:

1. ``evals/results/report.json`` exists and is valid (our schema).
2. ``evals/results/manifest.json`` exists and is valid.
3. ``evals/results/signature.json`` exists and its HMAC matches a fresh
   recomputation over the committed report + manifest + pinned model names
   (tamper-evidence: a hand-edited report is rejected).
4. The signed generation/judge model names are the repo's pinned models.
5. Every manifest entry's recorded hashes match freshly recomputed hashes of the
   current committed skills, task cases, and fixtures (freshness / integrity).
6. Every graded case that carries a score satisfies ``score >= threshold``.
7. No recorded case in the report is a failure.

Exit code is 0 on success and non-zero on any problem, with a clear, actionable
message. When run under GitHub Actions, a summary is also written to
``$GITHUB_STEP_SUMMARY``.

It deliberately imports only stdlib + the stdlib/PyYAML-only ``evals.lib``
helpers (hashing/manifest/signing/models/paths); it never imports DeepEval.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from evals.lib.hashing import hash_skill, hash_case, hash_fixture, hash_golden  # noqa: E402
from evals.lib.manifest import read_manifest  # noqa: E402
from evals.lib.signing import verify_signature  # noqa: E402
from evals.lib.models import (  # noqa: E402
    GENERATION_MODEL,
    JUDGE_MODEL,
    MANUAL_GENERATION_MODEL,
)
from evals.lib.paths import (  # noqa: E402
    report_path,
    manifest_path,
    signature_path,
    skills_dir,
    cases_dir,
    fixtures_dir,
    golden_dir,
)

REPORT_SCHEMA = "frontend-skills/report@2"
# Tolerate the pre-signing schema so an older committed report produces a clear,
# actionable "regenerate + re-sign" message rather than an opaque failure.
LEGACY_REPORT_SCHEMA = "frontend-skills/report@1"


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
    if not isinstance(report, dict) or report.get("schema") not in (
        REPORT_SCHEMA,
        LEGACY_REPORT_SCHEMA,
    ):
        raise VerificationError(
            f"report.json has an unexpected schema (want {REPORT_SCHEMA!r})."
        )
    if report.get("schema") == LEGACY_REPORT_SCHEMA:
        raise VerificationError(
            "report.json uses the pre-signing schema "
            f"({LEGACY_REPORT_SCHEMA!r}); regenerate and re-sign results locally "
            "(make eval && make sign)."
        )
    for field in ("summary", "concerns", "cases"):
        if field not in report:
            raise VerificationError(f"report.json is missing '{field}'.")
    return report


def _load_signature() -> dict:
    p = signature_path()
    if not p.is_file():
        raise VerificationError(
            f"signature missing: {_rel(p)} not found — sign results locally "
            f"(make sign) and commit signature.json."
        )
    try:
        signature = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise VerificationError(f"signature.json is not valid JSON: {exc}") from exc
    if not isinstance(signature, dict):
        raise VerificationError("signature.json is not a JSON object.")
    return signature


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

        if "golden_hash" in entry:
            gdir = golden_dir() / skill / case_id
            if not gdir.is_dir():
                problems.append(f"golden for '{skill}/{case_id}' is missing")
            elif hash_golden(gdir) != entry["golden_hash"]:
                problems.append(f"golden for '{skill}/{case_id}' changed")

    return problems


def _check_signature_and_models(report: dict) -> list[str]:
    """Verify the HMAC signature and the pinned-model policy."""
    problems: list[str] = []
    signature = _load_signature()

    sig_problems = verify_signature(
        signature, report_path=report_path(), manifest_path=manifest_path()
    )
    problems.extend(sig_problems)
    if sig_problems:
        # If the signature itself is broken/tampered, the model-policy check
        # below would be meaningless, so stop here.
        return problems

    signed = signature.get("signed", {})
    gen = signed.get("generation_model")
    judge = signed.get("judge_model")

    if gen not in (GENERATION_MODEL, MANUAL_GENERATION_MODEL):
        problems.append(
            f"signed generation_model {gen!r} is not the pinned model "
            f"{GENERATION_MODEL!r} (or {MANUAL_GENERATION_MODEL!r})"
        )
    if judge != JUDGE_MODEL:
        problems.append(
            f"signed judge_model {judge!r} is not the pinned judge {JUDGE_MODEL!r}"
        )

    # Cross-check the report's own models block when present.
    report_models = report.get("models") or {}
    if report_models:
        if report_models.get("judge") not in (None, JUDGE_MODEL):
            problems.append(
                f"report.json records judge model {report_models.get('judge')!r}, "
                f"expected {JUDGE_MODEL!r}"
            )

    return problems


def _check_scores(report: dict) -> list[str]:
    """Re-assert score >= threshold for every graded case that carries a score."""
    problems: list[str] = []
    for c in report.get("cases", []):
        score = c.get("score")
        threshold = c.get("threshold")
        if score is None or threshold is None:
            # Not graded (e.g. model-less skipped run) — nothing to re-check.
            continue
        try:
            if float(score) < float(threshold):
                problems.append(
                    f"case {c.get('name')!r} scored {score} below its "
                    f"threshold {threshold}"
                )
        except (TypeError, ValueError):
            problems.append(
                f"case {c.get('name')!r} has a non-numeric score/threshold "
                f"({score!r}/{threshold!r})"
            )
    return problems


def verify() -> list[str]:
    """Run all checks; return a list of human-readable problems (empty == pass)."""
    problems: list[str] = []

    report = _load_report()
    manifest = _load_manifest()

    # 1. Signature (tamper-evidence) + pinned-model policy.
    problems.extend(_check_signature_and_models(report))

    # 2. Freshness / integrity.
    stale: list[str] = []
    for entry in manifest["entries"]:
        stale.extend(_recompute(entry))
    if stale:
        problems.append(
            "results are stale or tampered — regenerate and re-run evals locally:\n    - "
            + "\n    - ".join(stale)
        )

    # 3. Score thresholds for graded cases.
    problems.extend(_check_scores(report))

    # 4. Recorded failures.
    failed_cases = [c for c in report.get("cases", []) if not c.get("passed", False)]
    if failed_cases:
        names = ", ".join(
            c.get("name", f"{c.get('concern')}::{c.get('skill')}") for c in failed_cases
        )
        problems.append(f"one or more recorded eval cases failed: {names}")

    # 5. Sanity: report must reference at least one case.
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
            "manifest.json + signature.json, recompute content hashes and the "
            "HMAC signature to prove freshness/integrity, enforce the pinned "
            "models and per-case score thresholds, and fail on "
            "missing/stale/tampered/failing results. Never calls an LLM."
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
