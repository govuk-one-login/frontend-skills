# ci-eval-gate

## ADDED Requirements

### Requirement: CI adjudicates without an agent, LLM, or API keys
The system SHALL provide a GitHub Action that runs on pull requests and
adjudicates the committed evaluation results **without** invoking any agent or
LLM and **without** requiring any API keys or secrets.

#### Scenario: CI runs without secrets
- **WHEN** the GitHub Action runs on a pull request (including from a fork)
- **THEN** it completes using only committed artifacts and requires no API keys
  or secrets

### Requirement: CI reads the committed report and manifest
The system SHALL have CI read the committed DeepEval native `report.json` and the
integrity `manifest.json` from `evals/results/` to determine the outcome.

#### Scenario: Committed results are read
- **WHEN** the CI gate executes
- **THEN** it loads `evals/results/report.json` and `evals/results/manifest.json`

#### Scenario: Report is missing
- **WHEN** `evals/results/report.json` is missing or invalid
- **THEN** the PR check fails

### Requirement: Freshness and integrity are enforced via recomputed hashes
The system SHALL verify freshness/integrity by recomputing content hashes of the
current committed skills, task cases, and fixture outputs and comparing them to
the hashes recorded in `manifest.json`, failing on any mismatch.

#### Scenario: Committed content changed without regenerating results
- **WHEN** a committed skill, case, or fixture is changed but the results were
  not regenerated
- **THEN** the recomputed hashes mismatch the manifest and the PR check fails

#### Scenario: Results are fresh
- **WHEN** the recomputed hashes match the manifest for all recorded entries
- **THEN** the freshness/integrity check passes

### Requirement: PR outcome reflects recorded results
The system SHALL fail the PR check if results are missing, invalid, stale, or
tampered, or if any recorded case failed, and SHALL pass the PR check otherwise.

#### Scenario: Fresh results with all cases passing
- **WHEN** committed results are fresh and every recorded case passed
- **THEN** the PR check passes

#### Scenario: A recorded case failed
- **WHEN** any recorded case in `report.json` is a failure
- **THEN** the PR check fails
