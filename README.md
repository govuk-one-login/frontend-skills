# frontend-skills

A lightweight, version-controlled store of **agent skills** for frontend
engineering and testing, with a GOV.UK Design System (GDS) flavour. Skills are
evaluated with [DeepEval](https://deepeval.com) along two separate concerns, and
pull requests are gated by a **key-free** GitHub Action that adjudicates
committed results.

## Why this design

CI has **no agent/LLM access and no API keys**. So the expensive,
non-deterministic work (generating output and running LLM-judge metrics) happens
**locally** with a developer's own model. The results plus an integrity manifest
are **committed**, and CI only performs a fast, deterministic **adjudication**:
it recomputes content hashes to prove freshness and checks that every recorded
case passed. This keeps CI fast, deterministic, and fork-friendly.

## The two eval concerns

Evaluation is split into two explicitly separate concerns:

- **Content quality (concern A)** — are the skill documents themselves valid,
  clear, complete, and free of contradictions? Lives in `evals/content/`.
  - Deterministic spec-conformance checks (hard assertions): required
    frontmatter, `name`/`description` constraints, name-matches-directory, size
    limits. These always run, with or without a model.
  - An LLM-judge (G-Eval) clarity/completeness metric, run locally with your own
    model. Skipped automatically when no model is configured.
- **Application quality (concern B)** — when an agent applies a skill to a task,
  is the produced output good? Lives in `evals/application/`.
  - A deterministic gate requiring a non-empty committed fixture per case.
  - An LLM-judge (G-Eval) metric grading the committed fixture against the
    case's expected criteria. Skipped automatically when no model is configured.

Both concerns are recorded, kept separate, in `evals/results/report.json`.

## Repository layout

```
frontend-skills/
├── skills/<skill-name>/           # agent skills (Agent Skills spec)
│   └── govuk-accessible-component/
│       ├── SKILL.md
│       └── references/
├── evals/
│   ├── content/                   # concern A — skill-document checks
│   ├── application/               # concern B — grades committed fixtures
│   ├── cases/<skill>/<case>.yaml  # task definitions
│   ├── fixtures/<skill>/<case>/   # committed, locally-generated outputs
│   ├── results/
│   │   ├── report.json            # per-case pass/fail, split by concern
│   │   └── manifest.json          # integrity/freshness hashes
│   ├── lib/                       # shared helpers (skills, cases, hashing, manifest, reporting)
│   └── conftest.py                # writes report.json at the end of a run
├── scripts/
│   ├── generate.py                # record local output into fixtures + manifest (no LLM)
│   └── verify_results.py          # CI-side adjudicator (no LLM, no keys)
├── .github/workflows/evals.yml    # the CI gate
├── Makefile                       # install / generate / eval / verify entrypoints
├── requirements-ci.txt            # CI-only deps (no DeepEval)
└── evals/requirements.txt         # full local deps (DeepEval + pytest)
```

## Prerequisites

- Python 3.10+ (the local dev stack was verified on 3.14; CI uses 3.12).
- For LLM-judge metrics locally: a model configured for DeepEval, e.g. by
  setting `OPENAI_API_KEY` (or another provider DeepEval supports). Without a
  model the deterministic gates still run and the G-Eval metrics are skipped.

## Quick start

```bash
make install        # create .venv and install the full local eval stack
make eval           # run both suites; (re)writes evals/results/report.json
make verify         # adjudicate the committed results the same way CI does
```

`make help` lists every target.

## The full local workflow

1. **Author or edit a skill** under `skills/<skill-name>/` (see
   [Adding a new skill](#adding-a-new-skill)).
2. **Define a task case** at `evals/cases/<skill>/<case-id>.yaml`:

   ```yaml
   id: text-input-basic
   skill: govuk-accessible-component
   task: >-
     Build an accessible GOV.UK text input for a user's full name, with a
     label and a hint.
   expected_criteria:
     - Uses a <label> associated with the input via for/id
     - Associates hint text with the input via aria-describedby
     - Uses GOV.UK Design System classes
   ```

3. **Generate the output locally** with your own agent/LLM (this repo does not
   call an LLM for you). Save the output to a file, then record it:

   ```bash
   make generate CASE=evals/cases/govuk-accessible-component/text-input-basic.yaml \
                 OUTPUT=path/to/your_generated_output.md
   # or, piping from your own agent:
   your-agent ... | .venv/bin/python scripts/generate.py \
       --case evals/cases/govuk-accessible-component/text-input-basic.yaml --stdin
   ```

   This copies the output to `evals/fixtures/<skill>/<case-id>/` and records the
   skill, case, and fixture content hashes into `evals/results/manifest.json`.

4. **Run the eval suites locally** (with your model configured so the G-Eval
   metrics actually score):

   ```bash
   make eval
   ```

   This writes `evals/results/report.json` with both concerns' per-case
   pass/fail.

5. **Commit** the skill, the case, the fixture, and the results
   (`report.json` + `manifest.json`).

6. **Open a PR.** The CI gate adjudicates your committed results.

`make all` runs steps 4 and 6's local equivalent (`eval` then `verify`) in one
go.

## How the CI gate works

`.github/workflows/evals.yml` runs on pull requests (and pushes to `main`). It:

1. Checks out the repo and sets up Python.
2. Installs **only** `requirements-ci.txt` — **no DeepEval, no LLM client**.
3. Runs `scripts/verify_results.py`, which:
   - Validates `report.json` (schema, structure).
   - Validates `manifest.json`.
   - **Recomputes** the content hashes of the current committed skills, cases,
     and fixtures and compares them to the manifest.
   - Fails if results are missing, invalid, **stale/tampered** (any hash
     mismatch), or if **any recorded case failed**.

It requires no secrets and works for fork PRs. The pass/fail message is written
to the GitHub job summary.

## The freshness / integrity model

`report.json` is the outcome; `manifest.json` binds that outcome to the exact
content it was produced from. For each skill (content concern) and each case
(application concern), the manifest stores a sha256 content hash of:

- the skill directory (`skills/<skill>/`),
- the task case (`evals/cases/<skill>/<case-id>.yaml`), and
- the fixture output directory (`evals/fixtures/<skill>/<case-id>/`).

Directory hashes are order- and OS-independent (a sha256 over a sorted list of
`relative-path → file-hash` pairs). If you change a skill, case, or fixture but
do not regenerate the results, CI recomputes a different hash than the one in
the manifest and **fails the PR** with a message telling you to regenerate and
re-run the evals locally.

To fix a staleness failure: re-run `make generate` for the affected case (to
refresh the manifest hashes), `make eval` (to refresh `report.json`), then
commit.

## Adding a new skill

1. Create `skills/<skill-name>/SKILL.md` following the open
   [Agent Skills spec](https://agentskills.io):
   - YAML frontmatter with required `name` and `description`.
   - `name` is 1–64 chars, lowercase alphanumeric + hyphens (no leading/trailing
     or consecutive hyphens) and **must match the directory name**.
   - `description` is 1–1024 non-empty characters.
   - Keep `SKILL.md` under ~500 lines; add `references/`, `scripts/`, or
     `assets/` as needed.
2. Add at least one task case under `evals/cases/<skill-name>/`.
3. Follow the [local workflow](#the-full-local-workflow) to generate a fixture,
   run the evals, and commit the results.

The content suite discovers every skill automatically, so the new skill is
immediately subject to the deterministic spec-conformance checks.

## Commands reference

| Command | What it does |
|---|---|
| `make install` | Create `.venv`, install the full local eval stack (DeepEval + pytest). |
| `make install-ci` | Install only the key-free verifier deps (no DeepEval). |
| `make generate CASE=… OUTPUT=…` | Record a locally-generated output into fixtures + manifest. |
| `make eval` | Run both eval suites; (re)write `evals/results/report.json`. |
| `make verify` | Adjudicate committed results exactly as CI does (key-free). |
| `make test` | Run the tooling unit tests (lib, generate, verifier). |
| `make all` | `eval` then `verify`. |

All scripts are reachable from these documented commands — there are no orphaned
entrypoints. `scripts/generate.py` and `scripts/verify_results.py` can also be
invoked directly with `--help`.
