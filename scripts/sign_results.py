#!/usr/bin/env python3
"""Sign the committed evaluation results so CI can detect tampering.

After running the eval suites locally (``make eval``), run this to write
``evals/results/signature.json``: a keyed hash (HMAC-SHA256) over the exact
committed bytes of ``report.json`` and ``manifest.json`` plus the pinned
generation/judge model names. CI recomputes the same HMAC and fails on any
mismatch, so a hand-edited report (e.g. flipping a failure to a pass or raising
a score) is rejected.

This is tamper-evidence, not anti-forgery: the key lives in the repo on purpose
to keep CI key-free and fork-friendly. See ``evals/lib/signing.py``.

Usage:

    python scripts/sign_results.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from evals.lib import (  # noqa: E402
    compute_signature,
    read_manifest,
    GENERATION_MODEL,
    JUDGE_MODEL,
)
from evals.lib.paths import (  # noqa: E402
    report_path,
    manifest_path,
    signature_path,
)


def _recorded_generation_model(default: str) -> str:
    """Return the generation model recorded in the manifest, if consistent.

    The pinned model is the norm, but a developer may have recorded a manual
    fixture. We sign whatever the manifest actually records so the signature
    reflects reality; if application entries disagree we fall back to the
    pinned default and let the CI policy check surface the discrepancy.
    """
    manifest = read_manifest()
    models = {
        e.get("generation_model")
        for e in manifest.get("entries", [])
        if e.get("concern") == "application" and e.get("generation_model")
    }
    if len(models) == 1:
        return next(iter(models))
    return default


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)

    rp = report_path()
    mp = manifest_path()
    if not rp.is_file():
        print(f"cannot sign: {rp} not found — run `make eval` first.", file=sys.stderr)
        return 1
    if not mp.is_file():
        print(f"cannot sign: {mp} not found — run `make generate` first.", file=sys.stderr)
        return 1

    signature = compute_signature(
        report_path=rp,
        manifest_path=mp,
        generation_model=_recorded_generation_model(GENERATION_MODEL),
        judge_model=JUDGE_MODEL,
    )

    out = signature_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(signature, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"Signed results: {out}")
    print(f"  generation_model = {signature['signed']['generation_model']}")
    print(f"  judge_model      = {signature['signed']['judge_model']}")
    print("Commit report.json, manifest.json, and signature.json together.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
