"""Discover and parse agent skills conforming to the Agent Skills spec."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from evals.lib.paths import skills_dir

# name: 1-64 chars, lowercase alphanumeric + hyphens, no leading/trailing
# hyphen, no consecutive hyphens.
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
NAME_MAX = 64
DESC_MAX = 1024
# Recommended SKILL.md size ceiling (soft-ish, enforced as a hard limit here).
MAX_LINES = 500

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.DOTALL)


class SkillFormatError(ValueError):
    """Raised when a SKILL.md cannot be parsed into frontmatter + body."""


@dataclass
class Skill:
    """A parsed skill directory."""

    name: str
    path: Path  # the skill directory
    frontmatter: dict[str, Any]
    body: str
    raw_text: str

    @property
    def skill_md(self) -> Path:
        return self.path / "SKILL.md"

    @property
    def description(self) -> str:
        return str(self.frontmatter.get("description", ""))

    @property
    def line_count(self) -> int:
        return self.raw_text.count("\n") + 1

    def validate(self) -> list[str]:
        """Return a list of spec-conformance error strings (empty == valid)."""
        errors: list[str] = []
        fm = self.frontmatter

        name = fm.get("name")
        if not name:
            errors.append("frontmatter is missing required field 'name'")
        else:
            if not isinstance(name, str):
                errors.append("'name' must be a string")
            else:
                if not (1 <= len(name) <= NAME_MAX):
                    errors.append(f"'name' must be 1-{NAME_MAX} chars (got {len(name)})")
                if not NAME_RE.match(name):
                    errors.append(
                        "'name' must be lowercase alphanumeric and hyphens, with no "
                        f"leading/trailing or consecutive hyphens (got {name!r})"
                    )
                if name != self.path.name:
                    errors.append(
                        f"'name' ({name!r}) must match the directory name "
                        f"({self.path.name!r})"
                    )

        desc = fm.get("description")
        if not desc:
            errors.append("frontmatter is missing required field 'description'")
        elif not isinstance(desc, str):
            errors.append("'description' must be a string")
        else:
            stripped = desc.strip()
            if not (1 <= len(stripped) <= DESC_MAX):
                errors.append(
                    f"'description' must be 1-{DESC_MAX} non-empty chars "
                    f"(got {len(stripped)})"
                )

        if self.line_count > MAX_LINES:
            errors.append(
                f"SKILL.md should be <= {MAX_LINES} lines (got {self.line_count})"
            )

        return errors


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split SKILL.md text into (frontmatter dict, body string)."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise SkillFormatError(
            "SKILL.md must start with a YAML frontmatter block delimited by '---'"
        )
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as exc:  # pragma: no cover - defensive
        raise SkillFormatError(f"invalid YAML frontmatter: {exc}") from exc
    if not isinstance(fm, dict):
        raise SkillFormatError("YAML frontmatter must be a mapping")
    return fm, m.group(2)


def load_skill(skill_path: Path) -> Skill:
    """Load and parse a single skill directory."""
    skill_path = Path(skill_path)
    skill_md = skill_path / "SKILL.md"
    if not skill_md.is_file():
        raise SkillFormatError(f"no SKILL.md in {skill_path}")
    raw = skill_md.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(raw)
    return Skill(
        name=str(fm.get("name", skill_path.name)),
        path=skill_path,
        frontmatter=fm,
        body=body,
        raw_text=raw,
    )


def discover_skills(root: Path | None = None) -> list[Skill]:
    """Discover all skills (directories containing a SKILL.md) under ``root``."""
    base = Path(root) if root is not None else skills_dir()
    if not base.is_dir():
        return []
    skills: list[Skill] = []
    for child in sorted(base.iterdir()):
        if child.is_dir() and (child / "SKILL.md").is_file():
            skills.append(load_skill(child))
    return skills
