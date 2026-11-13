"""Tests for the signing helper and the signing library.

Covers: a signed report round-trips through verify_signature; tampering with the
report, the manifest, or a model name is detected; and sign_results.py writes a
valid signature file.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from evals.lib.paths import repo_root
from evals.lib.signing import compute_signature, verify_signature


def _write(tmp_path: Path, report: dict, manifest: dict):
    rp = tmp_path / "report.json"
    mp = tmp_path / "manifest.json"
    rp.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    mp.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return rp, mp


_REPORT = {"schema": "frontend-skills/report@2", "cases": [{"name": "x", "passed": True}]}
_MANIFEST = {"version": 2, "algorithm": "sha256", "entries": [{"concern": "content"}]}


def test_signature_round_trips(tmp_path):
    rp, mp = _write(tmp_path, _REPORT, _MANIFEST)
    sig = compute_signature(
        report_path=rp, manifest_path=mp,
        generation_model="qwen2.5:7b", judge_model="qwen2.5:14b",
    )
    assert verify_signature(sig, report_path=rp, manifest_path=mp) == []


def test_tampered_report_detected(tmp_path):
    rp, mp = _write(tmp_path, _REPORT, _MANIFEST)
    sig = compute_signature(
        report_path=rp, manifest_path=mp,
        generation_model="qwen2.5:7b", judge_model="qwen2.5:14b",
    )
    # Flip a pass to a fail after signing.
    tampered = dict(_REPORT)
    tampered["cases"] = [{"name": "x", "passed": False}]
    rp.write_text(json.dumps(tampered, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    problems = verify_signature(sig, report_path=rp, manifest_path=mp)
    assert problems and any("report.json has changed" in p for p in problems)


def test_tampered_manifest_detected(tmp_path):
    rp, mp = _write(tmp_path, _REPORT, _MANIFEST)
    sig = compute_signature(
        report_path=rp, manifest_path=mp,
        generation_model="qwen2.5:7b", judge_model="qwen2.5:14b",
    )
    mp.write_text(json.dumps({"version": 2, "entries": []}) + "\n", encoding="utf-8")
    problems = verify_signature(sig, report_path=rp, manifest_path=mp)
    assert problems and any("manifest.json has changed" in p for p in problems)


def test_forged_model_name_detected(tmp_path):
    rp, mp = _write(tmp_path, _REPORT, _MANIFEST)
    sig = compute_signature(
        report_path=rp, manifest_path=mp,
        generation_model="qwen2.5:7b", judge_model="qwen2.5:14b",
    )
    # Edit the signed model name without recomputing the HMAC.
    sig["signed"]["judge_model"] = "gpt-4o"
    problems = verify_signature(sig, report_path=rp, manifest_path=mp)
    assert problems and any("signature mismatch" in p for p in problems)


def _load_sign_module():
    path = repo_root() / "scripts" / "sign_results.py"
    spec = importlib.util.spec_from_file_location("_sign_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_sign_results_script_writes_valid_signature(tmp_path):
    mod = _load_sign_module()
    rp, mp = _write(tmp_path, _REPORT, _MANIFEST)
    sp = tmp_path / "signature.json"
    mod.report_path = lambda: rp
    mod.manifest_path = lambda: mp
    mod.signature_path = lambda: sp
    # No application entries with generation_model -> falls back to pinned default.
    mod.read_manifest = lambda: _MANIFEST

    assert mod.main([]) == 0
    assert sp.is_file()
    sig = json.loads(sp.read_text(encoding="utf-8"))
    assert verify_signature(sig, report_path=rp, manifest_path=mp) == []
    assert sig["signed"]["judge_model"] == "qwen2.5:14b"
