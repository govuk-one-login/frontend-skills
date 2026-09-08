# skill-application-evals

Concern B — grade locally-generated agent output produced from a skill.

## ADDED Requirements

### Requirement: Task cases define skill-application evaluations
The system SHALL define task cases under `evals/cases/<skill>/<case-id>.yaml`,
each specifying a task prompt, the skill under evaluation, and the expected
criteria for grading.

#### Scenario: A task case is defined
- **WHEN** a contributor adds `evals/cases/<skill>/<case-id>.yaml`
- **THEN** it specifies the task prompt, the referenced skill, and expected
  grading criteria

### Requirement: Outputs are generated locally and committed as fixtures
The system SHALL require agent outputs to be generated locally by the
developer's own LLM/agent and committed as fixtures under
`evals/fixtures/<skill>/<case-id>/`.

#### Scenario: A generated output is committed
- **WHEN** a developer generates output for a task case locally
- **THEN** the output is written to `evals/fixtures/<skill>/<case-id>/` and
  committed to the repository

### Requirement: DeepEval grades committed fixtures against expected criteria
The system SHALL provide a DeepEval + pytest suite under `evals/application/`
that loads each task case and its committed fixture output and grades it with
DeepEval metrics (e.g., G-Eval correctness/relevance) against the case's
expected criteria.

#### Scenario: A fixture output fails the grading metrics
- **WHEN** a fixture output does not meet the application grading thresholds
- **THEN** the application eval fails

#### Scenario: A fixture output meets the grading metrics
- **WHEN** a fixture output meets all application grading thresholds
- **THEN** the application eval passes for that case

### Requirement: Local runs produce a native report with separated concerns
The system SHALL, when evals are run locally, produce DeepEval's native JSON
report at `evals/results/report.json`, with content-concern and
application-concern results clearly separated and each case carrying a per-case
pass/fail and a concern label.

#### Scenario: Report is produced with separated concerns
- **WHEN** the evals are run locally
- **THEN** `evals/results/report.json` is created as DeepEval's native report and
  contains content and application results as distinct, labelled sections
