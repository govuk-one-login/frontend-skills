"""Task-case discovery and parsing.

A task case lives at ``evals/cases/<skill>/<case-id>.yaml`` and defines a single
skill-application evaluation: one **prompt** paired with one **golden example**
(the expected high-quality output for that prompt). Coverage grows by adding
more cases (more prompt/example pairs), not by adding alternative goldens to a
single case.

```yaml
id: text-input-basic              # optional; defaults to the file stem
skill: govuk-accessible-component
prompt: >-
  Build an accessible GOV.UK text input for a user's full name, with a label
  and a hint.
must_contain:                     # deterministic: all must appear in the output
  - aria-describedby
  - 'for="full-name"'
must_not_contain:                 # deterministic: none may appear in the output
  - 'outline: none'
```

The golden example for a case lives at
``evals/golden/<skill>/<case-id>/`` (one or more files; their concatenation is
the single expected output for that prompt). At eval time the current skill is
applied to ``prompt`` to generate fresh output, which is then graded both
deterministically (``must_contain`` / ``must_not_contain``) and by an LLM judge
against the golden.

- ``skill`` must reference an existing skill directory name.
- ``prompt`` is the instruction handed to the local generation model.
- ``must_contain`` / ``must_not_contain`` are optional lists of substrings the
  generated output must / must not contain (checked case-sensitively).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from evals.lib.paths import cases_dir, golden_dir


class CaseFormatError(ValueError):
    """Raised when a task-case YAML is missing required fields or malformed."""


@dataclass
class Case:
    id: str
    skill: str
    prompt: str
    must_contain: list[str] = field(default_factory=list)
    must_not_contain: list[str] = field(default_factory=list)
    path: Path | None = None

    @property
    def golden_path(self) -> Path:
        """Directory holding this case's golden example file(s)."""
        return golden_dir() / self.skill / self.id

    def golden_text(self) -> str:
        """Concatenate all golden files for this case (empty if none)."""
        gdir = self.golden_path
        if not gdir.is_dir():
            return ""
        parts = [
            f.read_text(encoding="utf-8")
            for f in sorted(gdir.rglob("*"))
            if f.is_file()
        ]
        return "\n\n".join(parts)


def _str_list(value: Any, field_name: str, case_path: Path) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise CaseFormatError(
            f"case {case_path}: '{field_name}' must be a list of strings"
        )
    return [v for v in value if v.strip()]


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
    # Accept 'prompt' (current) and fall back to legacy 'task' if present.
    prompt = data.get("prompt") or data.get("task")

    if not skill or not isinstance(skill, str):
        raise CaseFormatError(f"case {case_path} missing string field 'skill'")
    if not prompt or not isinstance(prompt, str):
        raise CaseFormatError(f"case {case_path} missing string field 'prompt'")

    must_contain = _str_list(data.get("must_contain"), "must_contain", case_path)
    must_not_contain = _str_list(
        data.get("must_not_contain"), "must_not_contain", case_path
    )

    return Case(
        id=case_id,
        skill=skill,
        prompt=prompt.strip(),
        must_contain=must_contain,
        must_not_contain=must_not_contain,
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
