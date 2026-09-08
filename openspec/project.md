# Project: frontend-skills

A lightweight, version-controlled store of **agent skills** focused on
**frontend engineering and testing**, with a GOV.UK Design System (GDS) flavour.

## Purpose

- Hold a curated set of agent skills that follow the open
  [Agent Skills specification](https://agentskills.io) (a directory per skill
  with a `SKILL.md` file).
- Evaluate those skills along **two separate concerns**:
  1. **Skill-content quality** — are the skill documents themselves valid,
     clear, complete, and free of contradictions?
  2. **Skill-application quality** — when an agent applies a skill to a task,
     is the produced output good?
- Gate pull requests with a GitHub Action so regressions in either concern
  block a merge.

## Key constraint

CI has **no access to an agent or LLM** and holds **no API keys**. Therefore:

- Developers generate skill outputs and run the DeepEval suite **locally**
  using their own LLM/agent.
- The DeepEval native report plus an integrity manifest are **committed**.
- The GitHub Action only **adjudicates** the committed results (validity,
  freshness/integrity, pass/fail). It never calls an LLM.

## Stack

- Python + [DeepEval](https://deepeval.com) + pytest for evaluation.
- No frontend build tooling for now (may be revisited later).

## Conventions

- Skills live under `skills/<skill-name>/` and conform to the Agent Skills spec.
- Evaluations live under `evals/`, split by concern (`content/`, `application/`).
- Committed results live under `evals/results/` (`report.json` + `manifest.json`).
