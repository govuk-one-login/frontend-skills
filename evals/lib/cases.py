"""Task-case discovery and parsing.

A task case lives at ``evals/cases/<skill>/<case-id>.yaml`` and defines a single
skill-application evaluation:

```yaml
id: text-input-basic          # optional; defaults to the file stem
skill: govuk-accessible-component
task: >-
  Build an accessible GOV.UK text input for a user's full name, with a label
  and a hint.
expected_criteria:
  - Uses a <label> associated with the input via for/id
  - Associates hint text with the input via aria-describedby
  - Preserves the visible GDS focus style
```

- ``skill`` must reference an existing skill directory name.
- ``task`` is the prompt handed to the local agent.
- ``expected_criteria`` is a non-empty list of grading criteria used by the
  application-eval G-Eval metric.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from evals.lib.paths import cases_dir


class CaseFormatError(ValueError):
    """Raised when a task-case YAML is missing required fields or malformed."""


@dataclass
class Case:
    id: str
    skill: str
    task: str
    expected_criteria: list[str]
    path: Path

    @property
    def expected_criteria_text(self) -> str:
        return "\n".join(f"- {c}" for c in self.expected_criteria)


def load_case(case_path: Path) -> Case:
    case_path = Path(case_path)
    if not case_path.is_file():
        raise CaseFormatError(f"case file not found: {case_path}")
    try:
        data: Any = yaml.safe_load(case_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise CaseFormatError(f"invalid YAML in {case_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise CaseFormatError(f"case {case_path} must be a YAML mapping")

    case_id = str(data.get("id") or case_path.stem)
    skill = data.get("skill")
    task = data.get("task")
    criteria = data.get("expected_criteria")

    if not skill or not isinstance(skill, str):
        raise CaseFormatError(f"case {case_path} missing string field 'skill'")
    if not task or not isinstance(task, str):
        raise CaseFormatError(f"case {case_path} missing string field 'task'")
    if not criteria or not isinstance(criteria, list) or not all(
        isinstance(c, str) and c.strip() for c in criteria
    ):
        raise CaseFormatError(
            f"case {case_path} needs a non-empty list of string 'expected_criteria'"
        )

    return Case(
        id=case_id,
        skill=skill,
        task=task.strip(),
        expected_criteria=[c.strip() for c in criteria],
        path=case_path,
    )


def discover_cases(root: Path | None = None) -> list[Case]:
    """Discover all task cases under ``evals/cases/<skill>/*.yaml``."""
    base = Path(root) if root is not None else cases_dir()
    if not base.is_dir():
        return []
    cases: list[Case] = []
    for skill_dir in sorted(base.iterdir()):
        if not skill_dir.is_dir():
            continue
        for yml in sorted(skill_dir.glob("*.yaml")) + sorted(skill_dir.glob("*.yml")):
            cases.append(load_case(yml))
    return cases
