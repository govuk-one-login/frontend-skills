"""The integrity/freshness manifest sidecar.

``manifest.json`` records, for the run that produced ``report.json``, a content
hash of each skill, task case, and generated fixture output, plus enough
identity metadata (skill name, case id, concern) to map entries back to report
entries. CI recomputes each hash from the current committed tree and fails on
any mismatch.

Manifest shape:

```json
{
  "version": 1,
  "algorithm": "sha256",
  "entries": [
    {
      "concern": "application",
      "skill": "govuk-accessible-component",
      "case_id": "text-input-basic",
      "skill_hash": "…",
      "case_hash": "…",
      "fixture_hash": "…",
      "golden_hash": "…",
      "generation_model": "qwen2.5:7b"
    },
    {
      "concern": "content",
      "skill": "govuk-accessible-component",
      "case_id": null,
      "skill_hash": "…"
    }
  ]
}
```
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evals.lib.hashing import ALGORITHM
from evals.lib.paths import manifest_path

MANIFEST_VERSION = 2


def _entry_key(concern: str, skill: str, case_id: str | None) -> tuple[str, str, str | None]:
    return (concern, skill, case_id)


def build_manifest_entry(
    *,
    concern: str,
    skill: str,
    case_id: str | None = None,
    skill_hash: str | None = None,
    case_hash: str | None = None,
    fixture_hash: str | None = None,
    golden_hash: str | None = None,
    generation_model: str | None = None,
) -> dict[str, Any]:
    """Construct a single manifest entry, omitting values that don't apply."""
    if concern not in ("content", "application"):
        raise ValueError(f"unknown concern: {concern!r}")
    entry: dict[str, Any] = {
        "concern": concern,
        "skill": skill,
        "case_id": case_id,
    }
    if skill_hash is not None:
        entry["skill_hash"] = skill_hash
    if case_hash is not None:
        entry["case_hash"] = case_hash
    if fixture_hash is not None:
        entry["fixture_hash"] = fixture_hash
    if golden_hash is not None:
        entry["golden_hash"] = golden_hash
    if generation_model is not None:
        entry["generation_model"] = generation_model
    return entry


def empty_manifest() -> dict[str, Any]:
    return {"version": MANIFEST_VERSION, "algorithm": ALGORITHM, "entries": []}


def read_manifest(path: Path | None = None) -> dict[str, Any]:
    """Read a manifest file, returning an empty manifest if it does not exist."""
    p = Path(path) if path is not None else manifest_path()
    if not p.is_file():
        return empty_manifest()
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "entries" not in data:
        raise ValueError(f"malformed manifest at {p}")
    return data


def write_manifest(manifest: dict[str, Any], path: Path | None = None) -> Path:
    """Write a manifest to disk with stable formatting."""
    p = Path(path) if path is not None else manifest_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    # Sort entries for deterministic diffs.
    entries = sorted(
        manifest.get("entries", []),
        key=lambda e: (e.get("concern", ""), e.get("skill", ""), e.get("case_id") or ""),
    )
    out = {
        "version": manifest.get("version", MANIFEST_VERSION),
        "algorithm": manifest.get("algorithm", ALGORITHM),
        "entries": entries,
    }
    p.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return p


def upsert_entry(manifest: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    """Insert or replace an entry keyed by (concern, skill, case_id)."""
    key = _entry_key(entry["concern"], entry["skill"], entry.get("case_id"))
    entries = [
        e
        for e in manifest.get("entries", [])
        if _entry_key(e["concern"], e["skill"], e.get("case_id")) != key
    ]
    entries.append(entry)
    manifest["entries"] = entries
    return manifest
