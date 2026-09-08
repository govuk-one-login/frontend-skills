#!/usr/bin/env python3
"""Record a locally-generated agent output as a committed fixture + manifest entry.

This helper does **not** call an LLM. The developer generates output for a task
case with their own agent/LLM, then runs this script to:

1. Copy the output into ``evals/fixtures/<skill>/<case-id>/output.<ext>``.
2. Record content hashes of the skill, the task case, and the fixture into
   ``evals/results/manifest.json`` under the ``application`` concern, so CI can
   later verify freshness.

Usage:

    python scripts/generate.py \
        --case evals/cases/govuk-accessible-component/text-input-basic.yaml \
        --output path/to/generated_output.md

    # or read the generated output from stdin (default filename output.md):
    my-agent ... | python scripts/generate.py --case <case.yaml> --stdin
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

# Ensure repo root import path when run as a script.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from evals.lib import (  # noqa: E402
    load_case,
    load_skill,
    hash_skill,
    hash_case,
    hash_fixture,
    read_manifest,
    write_manifest,
    upsert_entry,
    build_manifest_entry,
)
from evals.lib.paths import fixtures_dir, skills_dir  # noqa: E402


def _record_manifest(skill_name: str, case_id: str, skill_dir: Path,
                     case_path: Path, fixture_out_dir: Path) -> None:
    manifest = read_manifest()
    entry = build_manifest_entry(
        concern="application",
        skill=skill_name,
        case_id=case_id,
        skill_hash=hash_skill(skill_dir),
        case_hash=hash_case(case_path),
        fixture_hash=hash_fixture(fixture_out_dir),
    )
    upsert_entry(manifest, entry)

    # Also record a content-concern entry binding the skill hash, so the content
    # eval's freshness can be verified independently of any application case.
    content_entry = build_manifest_entry(
        concern="content",
        skill=skill_name,
        skill_hash=hash_skill(skill_dir),
    )
    upsert_entry(manifest, content_entry)

    write_manifest(manifest)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True, help="path to the task-case YAML")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--output", help="path to the locally-generated output file")
    src.add_argument("--stdin", action="store_true", help="read output from stdin")
    parser.add_argument(
        "--filename",
        default=None,
        help="fixture filename (default: keep --output's name, or output.md for stdin)",
    )
    args = parser.parse_args(argv)

    case_path = Path(args.case).resolve()
    case = load_case(case_path)

    skill_dir = (skills_dir() / case.skill).resolve()
    if not skill_dir.is_dir():
        parser.error(f"case references unknown skill '{case.skill}' ({skill_dir})")
    skill = load_skill(skill_dir)  # validates it parses

    fixture_out_dir = fixtures_dir() / case.skill / case.id
    fixture_out_dir.mkdir(parents=True, exist_ok=True)

    if args.stdin:
        data = sys.stdin.buffer.read()
        filename = args.filename or "output.md"
        (fixture_out_dir / filename).write_bytes(data)
    else:
        out_src = Path(args.output)
        if not out_src.is_file():
            parser.error(f"--output file not found: {out_src}")
        filename = args.filename or out_src.name
        shutil.copyfile(out_src, fixture_out_dir / filename)

    _record_manifest(skill.name, case.id, skill_dir, case_path, fixture_out_dir)

    print(f"Recorded fixture: {fixture_out_dir / filename}")
    print("Updated manifest: evals/results/manifest.json")
    print("Next: run the eval suites locally, then commit skills/, fixtures/, results/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
