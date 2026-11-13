"""Tests for the CI verifier: pass, stale hash, missing report, recorded failure,
signature tampering, pinned-model policy, and score thresholds.

Each test isolates the verifier against a temporary results/manifest/signature by
monkeypatching the path helpers the verifier imports, so the real committed
artifacts are never mutated.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from evals.lib.hashing import hash_skill, hash_case, hash_fixture, hash_golden
from evals.lib.models import GENERATION_MODEL, JUDGE_MODEL
from evals.lib.paths import repo_root, skills_dir, cases_dir, fixtures_dir, golden_dir
from evals.lib.signing import compute_signature


def _load_verifier():
    path = repo_root() / "scripts" / "verify_results.py"
    spec = importlib.util.spec_from_file_location("_verify_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _good_manifest_and_report(skill, case_id):
    sdir = skills_dir() / skill
    cpath = cases_dir() / skill / f"{case_id}.yaml"
    fdir = fixtures_dir() / skill / case_id
    gdir = golden_dir() / skill / case_id
    manifest = {
        "version": 2,
        "algorithm": "sha256",
        "entries": [
            {
                "concern": "content",
                "skill": skill,
                "case_id": None,
                "skill_hash": hash_skill(sdir),
            },
            {
                "concern": "application",
                "skill": skill,
                "case_id": case_id,
                "skill_hash": hash_skill(sdir),
                "case_hash": hash_case(cpath),
                "fixture_hash": hash_fixture(fdir),
                "golden_hash": hash_golden(gdir),
                "generation_model": GENERATION_MODEL,
            },
        ],
    }
    report = {
        "schema": "frontend-skills/report@2",
        "models": {"generation": GENERATION_MODEL, "judge": JUDGE_MODEL},
        "summary": {"total": 2, "passed": 2, "failed": 0},
        "concerns": {
            "content": {"total": 1, "passed": 1, "failed": 0},
            "application": {"total": 1, "passed": 1, "failed": 0},
        },
        "cases": [
            {"concern": "content", "skill": skill, "case_id": None,
             "name": f"content::{skill}", "passed": True, "skipped": False,
             "score": 0.9, "threshold": 0.7, "metric_success": True},
            {"concern": "application", "skill": skill, "case_id": case_id,
             "name": f"application::{skill}::{case_id}", "passed": True,
             "skipped": False, "score": 0.8, "threshold": 0.7,
             "metric_success": True},
        ],
        "deepeval": None,
    }
    return manifest, report


def _point_verifier_at(mod, tmp_path, manifest, report, *, sign=True):
    rp = tmp_path / "report.json"
    mp = tmp_path / "manifest.json"
    sp = tmp_path / "signature.json"
    rp.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    mp.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    mod.report_path = lambda: rp
    mod.manifest_path = lambda: mp
    mod.signature_path = lambda: sp
    if sign:
        sig = compute_signature(
            report_path=rp, manifest_path=mp,
            generation_model=GENERATION_MODEL, judge_model=JUDGE_MODEL,
        )
        sp.write_text(json.dumps(sig, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return rp, mp, sp


SKILL = "govuk-accessible-component"
CASE = "text-input-basic"


def test_pass(tmp_path):
    mod = _load_verifier()
    manifest, report = _good_manifest_and_report(SKILL, CASE)
    _point_verifier_at(mod, tmp_path, manifest, report)
    assert mod.verify() == []
    assert mod.main([]) == 0


def test_stale_hash_mismatch(tmp_path):
    mod = _load_verifier()
    manifest, report = _good_manifest_and_report(SKILL, CASE)
    for e in manifest["entries"]:
        if "skill_hash" in e:
            e["skill_hash"] = "deadbeef"
    _point_verifier_at(mod, tmp_path, manifest, report)
    problems = mod.verify()
    assert problems and any("stale" in p for p in problems)
    assert mod.main([]) == 1


def test_missing_report(tmp_path):
    mod = _load_verifier()
    manifest, report = _good_manifest_and_report(SKILL, CASE)
    mp = tmp_path / "manifest.json"
    mp.write_text(json.dumps(manifest), encoding="utf-8")
    mod.manifest_path = lambda: mp
    mod.report_path = lambda: tmp_path / "does_not_exist.json"
    mod.signature_path = lambda: tmp_path / "signature.json"
    assert mod.main([]) == 1


def test_recorded_failure(tmp_path):
    mod = _load_verifier()
    manifest, report = _good_manifest_and_report(SKILL, CASE)
    report["cases"][1]["passed"] = False
    # Re-sign so the signature matches the (legitimately recorded) failure; the
    # verifier must still fail on the recorded failure itself.
    _point_verifier_at(mod, tmp_path, manifest, report)
    problems = mod.verify()
    assert problems and any("failed" in p for p in problems)
    assert mod.main([]) == 1


def test_missing_signature(tmp_path):
    mod = _load_verifier()
    manifest, report = _good_manifest_and_report(SKILL, CASE)
    _point_verifier_at(mod, tmp_path, manifest, report, sign=False)
    # A missing signature is a fatal VerificationError surfaced via main() -> 1.
    with_err = mod.VerificationError
    try:
        mod.verify()
        raised = False
    except with_err as exc:
        raised = True
        assert "signature missing" in str(exc)
    assert raised
    assert mod.main([]) == 1


def test_tampered_report_after_signing(tmp_path):
    mod = _load_verifier()
    manifest, report = _good_manifest_and_report(SKILL, CASE)
    rp, mp, sp = _point_verifier_at(mod, tmp_path, manifest, report)
    # Hand-edit the report after signing: flip a failure to a pass.
    report["cases"][1]["passed"] = False  # the "truth"
    # Attacker instead writes passed: True without re-signing.
    report["cases"][1]["passed"] = True
    rp.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # Change a byte so the content hash differs from the signed one.
    report["summary"]["passed"] = 999
    rp.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    problems = mod.verify()
    assert problems and any("has changed since it was signed" in p for p in problems)
    assert mod.main([]) == 1


def test_wrong_pinned_model(tmp_path):
    mod = _load_verifier()
    manifest, report = _good_manifest_and_report(SKILL, CASE)
    rp = tmp_path / "report.json"
    mp = tmp_path / "manifest.json"
    sp = tmp_path / "signature.json"
    rp.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    mp.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # Sign with a non-pinned judge model so the HMAC is valid but policy fails.
    sig = compute_signature(
        report_path=rp, manifest_path=mp,
        generation_model=GENERATION_MODEL, judge_model="gpt-4o",
    )
    sp.write_text(json.dumps(sig, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    mod.report_path = lambda: rp
    mod.manifest_path = lambda: mp
    mod.signature_path = lambda: sp
    problems = mod.verify()
    assert problems and any("pinned judge" in p for p in problems)
    assert mod.main([]) == 1


def test_score_below_threshold(tmp_path):
    mod = _load_verifier()
    manifest, report = _good_manifest_and_report(SKILL, CASE)
    report["cases"][1]["score"] = 0.5
    report["cases"][1]["threshold"] = 0.7
    _point_verifier_at(mod, tmp_path, manifest, report)
    problems = mod.verify()
    assert problems and any("below its threshold" in p for p in problems)
    assert mod.main([]) == 1
