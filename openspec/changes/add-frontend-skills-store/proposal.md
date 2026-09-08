# Proposal: Add a frontend agent-skills store with DeepEval evals and a CI gate

## Why

We want a lightweight, version-controlled repository that stores agent skills
focused on frontend engineering and testing (GOV.UK Design System–flavoured),
evaluates them along two separate concerns (skill-content quality and
skill-application quality), and gates pull requests via a GitHub Action.

Because CI has no agent/LLM access and holds no API keys, developers generate
outputs and run the DeepEval suite **locally**, commit the results plus
fixtures, and CI **adjudicates** the committed results with an
integrity/freshness check. This keeps CI fast, deterministic, key-free, and
fork-friendly while still allowing rich LLM-as-judge evaluation locally.

## What changes

This change introduces four new capabilities:

- **skills-store** — a `skills/` directory holding agent skills that conform to
  the open Agent Skills specification, seeded with one GDS-flavoured exemplar
  skill, `govuk-accessible-component`.
- **skill-content-evals** (concern A) — a DeepEval + pytest suite that validates
  the skill documents themselves: deterministic spec-conformance checks plus at
  least one LLM-judge (G-Eval) clarity/completeness metric run locally.
- **skill-application-evals** (concern B) — a DeepEval + pytest suite that grades
  locally-generated agent output (committed as fixtures) against task cases.
- **ci-eval-gate** — a GitHub Action that runs on PRs, reads the committed
  DeepEval native `report.json` and integrity `manifest.json`, verifies freshness
  by recomputing content hashes, and passes/fails the PR — with no agent, LLM, or
  API keys.

## Scope

- **In scope:** repository skeleton, one exemplar skill, both eval suites, the
  local generation/verification tooling, the committed results format, and the
  CI gate.
- **Out of scope (for now):** frontend build tooling; running an agent/LLM in
  CI; more than one seed skill.

## Decisions locked in

| # | Decision |
|---|----------|
| Skill format | Open Agent Skills spec (`SKILL.md` + optional `scripts/`, `references/`, `assets/`). |
| Eval concerns | Two, kept explicitly separate: content (A) and application (B). |
| Stack | Python + DeepEval + pytest. No frontend tooling yet. |
| Fixtures (Q4=A) | Locally-generated outputs committed under `evals/fixtures/`. |
| Run model (Q5) | Generate + run DeepEval locally; CI only adjudicates committed results. |
| Freshness (Q7=A) | `manifest.json` sidecar records content hashes; CI recomputes and compares. |
| Results file (Q8=A) | DeepEval native JSON report kept as-is; hashes live in the sidecar. |
| Seed skills (Q6=c) | One exemplar skill to start. |
| Exemplar (Q9=a) | `govuk-accessible-component`, GDS-flavoured with accessibility expectations. |
