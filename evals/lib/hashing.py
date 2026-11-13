"""Deterministic content hashing for skills, cases, and fixtures.

Hashes bind committed evaluation results to the exact content they were
produced from. The algorithm is intentionally simple and stdlib-only (sha256)
so the CI verifier can recompute hashes without DeepEval or any third-party
dependency beyond what is already required.

Directory hashing is order-independent and path-relative: we hash a sorted list
of ``(relative_posix_path, sha256_of_bytes)`` pairs so the result is stable
across machines and OSes.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

ALGORITHM = "sha256"


def hash_bytes(data: bytes) -> str:
    """Return the hex sha256 of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def hash_file(path: Path) -> str:
    """Return the hex sha256 of a single file's bytes."""
    return hash_bytes(Path(path).read_bytes())


def _hash_tree(root: Path) -> str:
    """Hash every regular file under ``root`` in a stable, path-relative way."""
    root = Path(root)
    entries: list[str] = []
    for p in sorted(root.rglob("*")):
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            entries.append(f"{rel}\0{hash_file(p)}")
    joined = "\n".join(entries).encode("utf-8")
    return hash_bytes(joined)


def hash_skill(skill_path: Path) -> str:
    """Content hash of an entire skill directory (SKILL.md + all resources)."""
    return _hash_tree(Path(skill_path))


def hash_case(case_path: Path) -> str:
    """Content hash of a single task-case YAML file."""
    return hash_file(Path(case_path))


def hash_fixture(fixture_dir: Path) -> str:
    """Content hash of a fixture output directory (all files within)."""
    return _hash_tree(Path(fixture_dir))


def hash_golden(golden_dir: Path) -> str:
    """Content hash of a case's golden example directory (all files within)."""
    return _hash_tree(Path(golden_dir))
