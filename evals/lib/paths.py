"""Canonical repository paths used across the eval tooling."""

from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    """Return the repository root (the parent of the ``evals`` package)."""
    return Path(__file__).resolve().parents[2]


def skills_dir() -> Path:
    return repo_root() / "skills"


def cases_dir() -> Path:
    return repo_root() / "evals" / "cases"


def fixtures_dir() -> Path:
    return repo_root() / "evals" / "fixtures"


def golden_dir() -> Path:
    return repo_root() / "evals" / "golden"


def results_dir() -> Path:
    return repo_root() / "evals" / "results"


def report_path() -> Path:
    return results_dir() / "report.json"


def manifest_path() -> Path:
    return results_dir() / "manifest.json"


def signature_path() -> Path:
    return results_dir() / "signature.json"
