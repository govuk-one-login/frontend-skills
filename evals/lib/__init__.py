"""Shared helpers for the eval suites and tooling.

This package deliberately depends only on the Python standard library plus
PyYAML so that the CI-side verifier can import the hashing/manifest helpers
without pulling in DeepEval or any LLM client.
"""

from evals.lib.skills import Skill, discover_skills, load_skill, parse_frontmatter
from evals.lib.cases import Case, discover_cases, load_case
from evals.lib.hashing import (
    hash_bytes,
    hash_file,
    hash_skill,
    hash_case,
    hash_fixture,
)
from evals.lib.manifest import (
    MANIFEST_VERSION,
    build_manifest_entry,
    read_manifest,
    write_manifest,
    upsert_entry,
)
from evals.lib.paths import (
    repo_root,
    skills_dir,
    cases_dir,
    fixtures_dir,
    results_dir,
    report_path,
    manifest_path,
)

__all__ = [
    "Skill",
    "discover_skills",
    "load_skill",
    "parse_frontmatter",
    "Case",
    "discover_cases",
    "load_case",
    "hash_bytes",
    "hash_file",
    "hash_skill",
    "hash_case",
    "hash_fixture",
    "MANIFEST_VERSION",
    "build_manifest_entry",
    "read_manifest",
    "write_manifest",
    "upsert_entry",
    "repo_root",
    "skills_dir",
    "cases_dir",
    "fixtures_dir",
    "results_dir",
    "report_path",
    "manifest_path",
]
