"""Tamper-evident signing of committed evaluation results.

The committed ``report.json`` is the outcome CI trusts, but a plain JSON file
can be hand-edited (e.g. flipping ``passed: false`` to ``true`` or raising a
score). To make such edits *detectable*, a keyed hash (HMAC-SHA256) is computed
over the exact committed bytes of ``report.json`` and ``manifest.json`` plus the
pinned generation/judge model names, and written to
``evals/results/signature.json``. CI recomputes the same HMAC and fails on any
mismatch.

Threat model (deliberate): this is **tamper-evidence**, not anti-forgery. The
HMAC key is a constant committed in this repository, so the scheme keeps CI
key-free and fork-friendly (no secrets, fork PRs just work). It reliably catches
accidental hand-edits, stale commits, and casual gaming, and it binds the report
to the pinned models. It is **not** a defence against a motivated insider who
reads the key from the repo and recomputes a valid signature. Upgrading to
anti-forgery (asymmetric signing / an allow-list of public keys) would be a
localised change to this module and ``scripts/verify_results.py``.

This module imports only the standard library so the key-free CI verifier can
use it without DeepEval or any third-party dependency.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Any

SIGNATURE_SCHEMA = "frontend-skills/signature@1"
SIGNATURE_ALGORITHM = "hmac-sha256"

# Keyed-hash "key". Per the threat model above this lives in the repository on
# purpose: it makes the signature a deterministic, fork-friendly integrity seal,
# not a secret. Rotating it only forces results to be re-signed.
_SIGNING_KEY = b"frontend-skills/results-integrity/v1"


def _sha256_file(path: Path) -> str:
    """Hex sha256 of a file's exact committed bytes."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _canonical_payload(
    report_hash: str,
    manifest_hash: str,
    generation_model: str,
    judge_model: str,
) -> bytes:
    """Serialise the signed fields canonically (stable key order)."""
    return json.dumps(
        {
            "report_hash": report_hash,
            "manifest_hash": manifest_hash,
            "generation_model": generation_model,
            "judge_model": judge_model,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _hmac(payload: bytes) -> str:
    return hmac.new(_SIGNING_KEY, payload, hashlib.sha256).hexdigest()


def compute_signature(
    *,
    report_path: Path,
    manifest_path: Path,
    generation_model: str,
    judge_model: str,
) -> dict[str, Any]:
    """Compute a signature dict over the committed report + manifest + models."""
    report_hash = _sha256_file(report_path)
    manifest_hash = _sha256_file(manifest_path)
    signed = {
        "report_hash": report_hash,
        "manifest_hash": manifest_hash,
        "generation_model": generation_model,
        "judge_model": judge_model,
    }
    payload = _canonical_payload(
        report_hash, manifest_hash, generation_model, judge_model
    )
    return {
        "schema": SIGNATURE_SCHEMA,
        "algorithm": SIGNATURE_ALGORITHM,
        "signature": _hmac(payload),
        "signed": signed,
    }


def verify_signature(
    signature: dict[str, Any],
    *,
    report_path: Path,
    manifest_path: Path,
) -> list[str]:
    """Return a list of human-readable problems (empty == valid signature).

    Recomputes the content hashes of the *current* committed report and
    manifest and the HMAC over the signed fields, and compares both to the
    signature. The pinned-model *policy* check (are these the expected models?)
    is intentionally left to the caller so this module stays policy-free.
    """
    problems: list[str] = []

    if not isinstance(signature, dict):
        return ["signature.json is not a JSON object"]
    if signature.get("schema") != SIGNATURE_SCHEMA:
        problems.append(
            f"signature.json has an unexpected schema (want {SIGNATURE_SCHEMA!r})"
        )
    if signature.get("algorithm") != SIGNATURE_ALGORITHM:
        problems.append(
            f"signature.json uses an unexpected algorithm "
            f"(want {SIGNATURE_ALGORITHM!r})"
        )

    signed = signature.get("signed")
    if not isinstance(signed, dict):
        problems.append("signature.json is missing the 'signed' block")
        return problems
    for field in ("report_hash", "manifest_hash", "generation_model", "judge_model"):
        if field not in signed:
            problems.append(f"signature 'signed' block is missing '{field}'")
    if problems:
        return problems

    actual_report = _sha256_file(report_path)
    actual_manifest = _sha256_file(manifest_path)
    if actual_report != signed["report_hash"]:
        problems.append("report.json has changed since it was signed")
    if actual_manifest != signed["manifest_hash"]:
        problems.append("manifest.json has changed since it was signed")

    payload = _canonical_payload(
        signed["report_hash"],
        signed["manifest_hash"],
        signed["generation_model"],
        signed["judge_model"],
    )
    expected_sig = _hmac(payload)
    provided_sig = signature.get("signature", "")
    if not hmac.compare_digest(expected_sig, str(provided_sig)):
        problems.append(
            "signature mismatch: report/manifest/model names do not match the "
            "recorded signature"
        )

    return problems
