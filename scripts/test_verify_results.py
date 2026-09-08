"""Tests for the CI verifier: pass, stale hash, missing report, recorded failure.

Each test isolates the verifier against a temporary results/manifest by
monkeypatching the path helpers the verifier imports, so the real committed
artifacts are never mutated.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from evals.lib.hashing import hash_skill, hash_case, hash_fixture
from evals.lib.paths import repo_root, skills_dir, cases_dir, fixtures_dir


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
    manifest = {
        "version": 1,
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
            },
        ],
    }
    report = {
        "schema": "frontend-skills/report@1",
        "summary": {"total": 2, "passed": 2, "failed": 0},
        "concerns": {
            "content": {"total": 1, "passed": 1, "failed": 0},
            "application": {"total": 1, "passed": 1, "failed": 0},
        },
        "cases": [
            {"concern": "content", "skill": skill, "case_id": None,
             "name": f"content::{skill}", "passed": True, "skipped": False},
            {"concern": "application", "skill": skill, "case_id": case_id,
             "name": f"application::{skill}::{case_id}", "passed": True,
             "skipped": False},
        ],
        "deepeval": None,
    }
    return manifest, report


def _point_verifier_at(mod, tmp_path, manifest, report):
    rp = tmp_path / "report.json"
    mp = tmp_path / "manifest.json"
    rp.write_text(json.dumps(report), encoding="utf-8")
    mp.write_text(json.dumps(manifest), encoding="utf-8")
    mod.report_path = lambda: rp
    mod.manifest_path = lambda: mp


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
    # Corrupt the recorded skill hash to simulate a changed skill.
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
    assert mod.main([]) == 1


def test_recorded_failure(tmp_path):
    mod = _load_verifier()
    manifest, report = _good_manifest_and_report(SKILL, CASE)
    report["cases"][1]["passed"] = False
    _point_verifier_at(mod, tmp_path, manifest, report)
    problems = mod.verify()
    assert problems and any("failed" in p for p in problems)
    assert mod.main([]) == 1
