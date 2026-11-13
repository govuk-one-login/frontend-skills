"""Test the local generation helper writes a fixture + stable manifest entry."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from evals.lib import read_manifest
from evals.lib.paths import repo_root, fixtures_dir, cases_dir


def _load_generate_module():
    path = repo_root() / "scripts" / "generate.py"
    spec = importlib.util.spec_from_file_location("_generate_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_generate_records_fixture_and_manifest(tmp_path):
    gen = _load_generate_module()
    case_path = cases_dir() / "govuk-accessible-component" / "text-input-basic.yaml"
    assert case_path.is_file(), "seed case must exist"

    fixture = fixtures_dir() / "govuk-accessible-component" / "text-input-basic" / "output.md"
    manifest_file = repo_root() / "evals" / "results" / "manifest.json"
    # Preserve the real committed artifacts so the test does not corrupt them.
    saved_fixture = fixture.read_bytes() if fixture.is_file() else None
    saved_manifest = manifest_file.read_bytes() if manifest_file.is_file() else None

    try:
        src = tmp_path / "gen.md"
        src.write_text("# generated output\nhello", encoding="utf-8")

        rc = gen.main(["--case", str(case_path), "--output", str(src), "--filename", "output.md"])
        assert rc == 0
        assert fixture.is_file()

        manifest = read_manifest()
        app_entries = [
            e for e in manifest["entries"]
            if e["concern"] == "application"
            and e["skill"] == "govuk-accessible-component"
            and e["case_id"] == "text-input-basic"
        ]
        assert len(app_entries) == 1
        entry = app_entries[0]
        assert entry["skill_hash"] and entry["case_hash"] and entry["fixture_hash"]
        # --output path records a manual generation model.
        assert entry["generation_model"] == "manual"

        # Re-running with identical content yields identical hashes (stable).
        rc2 = gen.main(["--case", str(case_path), "--output", str(src), "--filename", "output.md"])
        assert rc2 == 0
        entry2 = [
            e for e in read_manifest()["entries"]
            if e["concern"] == "application" and e["case_id"] == "text-input-basic"
        ][0]
        assert entry2["fixture_hash"] == entry["fixture_hash"]
    finally:
        if saved_fixture is not None:
            fixture.write_bytes(saved_fixture)
        if saved_manifest is not None:
            manifest_file.write_bytes(saved_manifest)
