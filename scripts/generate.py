#!/usr/bin/env python3
"""Record (or locally generate) an agent output as a committed fixture + manifest entry.

Three ways to provide the output for a task case:

1. ``--generate`` — generate the fixture locally with the pinned Ollama
   generation model (``qwen2.5:7b``), prompted with the skill document and the
   case task. Requires a running Ollama with that model pulled.
2. ``--output <file>`` — record an output you produced with your own agent/LLM.
3. ``--stdin`` — read the output from stdin (default filename ``output.md``).

In every mode this script:

1. Copies/writes the output into
   ``evals/fixtures/<skill>/<case-id>/output.<ext>``.
2. Records content hashes of the skill, the task case, and the fixture into
   ``evals/results/manifest.json`` under the ``application`` concern (plus a
   ``content`` entry binding the skill hash), along with the generation model
   used, so CI can later verify freshness and the pinned-model policy.

This script never calls an LLM judge; judging happens in the eval suites.

Usage:

    # Generate locally with the pinned Ollama model:
    python scripts/generate.py \
        --case evals/cases/govuk-accessible-component/text-input-basic.yaml \
        --generate

    # Record output produced by your own agent:
    python scripts/generate.py --case <case.yaml> --output path/to/output.md

    # Or pipe it in:
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
    hash_golden,
    read_manifest,
    write_manifest,
    upsert_entry,
    build_manifest_entry,
    GENERATION_MODEL,
    MANUAL_GENERATION_MODEL,
    ollama_base_url,
)
from evals.lib.paths import fixtures_dir, skills_dir  # noqa: E402


def _generate_with_ollama(skill, case) -> str:
    """Generate fixture output for a case with the pinned Ollama model.

    Uses the Ollama HTTP API directly (stdlib only) so this script does not
    depend on DeepEval. Raises a clear error if the server is unreachable.
    """
    import json
    import urllib.error
    import urllib.request

    prompt = (
        "You are applying the following agent skill to a task. Follow the "
        "skill's guidance precisely and return only the requested artefact "
        "(no commentary).\n\n"
        "=== SKILL ===\n"
        f"{skill.raw_text}\n\n"
        "=== TASK ===\n"
        f"{case.prompt}\n"
    )
    payload = json.dumps(
        {
            "model": GENERATION_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0},
        }
    ).encode("utf-8")
    url = f"{ollama_base_url()}/api/generate"
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise SystemExit(
            f"could not reach Ollama at {url}: {exc}. Start Ollama and run "
            f"`ollama pull {GENERATION_MODEL}`."
        ) from exc
    text = (data or {}).get("response", "")
    if not text.strip():
        raise SystemExit(
            f"Ollama ({GENERATION_MODEL}) returned empty output for "
            f"{case.skill}/{case.id}."
        )
    return text


def _record_manifest(skill_name: str, case_id: str, skill_dir: Path,
                     case_path: Path, fixture_out_dir: Path, golden_dir_path: Path,
                     generation_model: str) -> None:
    manifest = read_manifest()
    entry = build_manifest_entry(
        concern="application",
        skill=skill_name,
        case_id=case_id,
        skill_hash=hash_skill(skill_dir),
        case_hash=hash_case(case_path),
        fixture_hash=hash_fixture(fixture_out_dir),
        golden_hash=hash_golden(golden_dir_path),
        generation_model=generation_model,
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
    src.add_argument("--generate", action="store_true",
                     help=f"generate the fixture locally with Ollama ({GENERATION_MODEL})")
    src.add_argument("--output", help="path to the locally-generated output file")
    src.add_argument("--stdin", action="store_true", help="read output from stdin")
    parser.add_argument(
        "--filename",
        default=None,
        help="fixture filename (default: keep --output's name, or output.md otherwise)",
    )
    args = parser.parse_args(argv)

    case_path = Path(args.case).resolve()
    case = load_case(case_path)

    skill_dir = (skills_dir() / case.skill).resolve()
    if not skill_dir.is_dir():
        parser.error(f"case references unknown skill '{case.skill}' ({skill_dir})")
    skill = load_skill(skill_dir)  # validates it parses

    golden_dir_path = case.golden_path
    if not case.golden_text().strip():
        parser.error(
            f"case '{case.skill}/{case.id}' has no golden example at "
            f"{golden_dir_path} — add the expected output there first."
        )

    fixture_out_dir = fixtures_dir() / case.skill / case.id
    fixture_out_dir.mkdir(parents=True, exist_ok=True)

    if args.generate:
        text = _generate_with_ollama(skill, case)
        filename = args.filename or "output.md"
        (fixture_out_dir / filename).write_text(text, encoding="utf-8")
        generation_model = GENERATION_MODEL
    elif args.stdin:
        data = sys.stdin.buffer.read()
        filename = args.filename or "output.md"
        (fixture_out_dir / filename).write_bytes(data)
        generation_model = MANUAL_GENERATION_MODEL
    else:
        out_src = Path(args.output)
        if not out_src.is_file():
            parser.error(f"--output file not found: {out_src}")
        filename = args.filename or out_src.name
        shutil.copyfile(out_src, fixture_out_dir / filename)
        generation_model = MANUAL_GENERATION_MODEL

    _record_manifest(
        skill.name, case.id, skill_dir, case_path, fixture_out_dir,
        golden_dir_path, generation_model,
    )

    print(f"Recorded fixture: {fixture_out_dir / filename}")
    print(f"Generation model: {generation_model}")
    print("Updated manifest: evals/results/manifest.json")
    print("Next: run the eval suites locally (make eval), sign (make sign), then commit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
