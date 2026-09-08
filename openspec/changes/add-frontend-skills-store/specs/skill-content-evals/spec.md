# skill-content-evals

Concern A — validate the skill documents themselves.

## ADDED Requirements

### Requirement: Deterministic spec-conformance checks gate skill content
The system SHALL provide a DeepEval + pytest suite under `evals/content/` that
enforces deterministic spec-conformance checks on every skill as hard
assertions, covering required frontmatter fields, `name`/`description`
constraints, name-matches-directory, and size limits.

#### Scenario: A skill violates the spec
- **WHEN** a skill's `SKILL.md` violates a spec-conformance rule (e.g., missing a
  required field or an invalid `name`)
- **THEN** the content eval fails

#### Scenario: A conformant skill passes the deterministic checks
- **WHEN** a skill's `SKILL.md` satisfies all spec-conformance rules
- **THEN** the deterministic content checks pass for that skill

### Requirement: LLM-judge clarity/completeness metric runs locally
The system SHALL include at least one LLM-judge (G-Eval) metric that evaluates a
skill document's clarity and completeness, executed locally using the
developer's own model.

#### Scenario: Clarity/completeness is evaluated locally
- **WHEN** the content evals are run locally
- **THEN** the G-Eval clarity/completeness metric is scored against a threshold
  using the developer's local model

### Requirement: Content outcomes are reported separately
The system SHALL record content-eval outcomes under a distinct "content" concern
in the committed results, separate from application-eval outcomes.

#### Scenario: Content results are labelled by concern
- **WHEN** content evals run and results are recorded
- **THEN** each recorded result is labelled as belonging to the content concern
  and is distinguishable from application-concern results
